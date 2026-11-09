"""Merge two candidate records of one person (CEO 2026-11-04: "THE SAME CANDIDATE GOT created twice").

Everything attached to the duplicate moves to the record kept: every table with a foreign key to candidates, the
tables that hold a candidate id without one, and the records addressed by entity or subject. Then the duplicate is
removed (CEO 2026-11-09: "only 1 record that is active", not one active and one archived): a CandidateMerge row keeps
its id, emails and phones, so its old link, its replies and duplicate checks all lead to the record kept, and the kept
record's history shows both as one. Audit logs are not rewritten: they say what happened.

A one-per-candidate row the kept record already has (its status, its cadence) is combined: what only the duplicate's
row knows fills the kept one's blanks, the live conversation carries over, and the duplicate's row goes. A second open
hiring pipeline is closed and moved, so its events stay on the record. The merge is all or nothing: if anything still
points at the duplicate, nothing changes and the error says what.
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.candidate import Candidate, CandidateMerge, CandidateStatus
from app.models.candidate_history import CandidateHistory

logger = logging.getLogger(__name__)

# Hold a candidate id without a foreign key
EXTRA_COLUMNS = {"candidate_intelligence_profiles": "candidate_id", "email_tracking": "candidate_id",
                 "employee_referrals": "referred_candidate_id", "linkedin_candidate_pipeline": "candidate_id",
                 "queue_doctor_state": "candidate_id", "thunder_learning_metrics": "candidate_id"}
# Address a candidate by entity: (table, id column, type column)
ENTITY_COLUMNS = (("activity_timeline", "entity_id", "entity_type"), ("file_uploads", "entity_id", "entity_type"),
                  ("consent_records", "subject_id", "subject_type"))
NEVER_COPIED = {"candidateID", "candidateEmail", "candidatePassword", "candidateTempPassword", "candidateCreatedAt",
                "merged_into_id", "tenant_id", "candidateSecondaryEmail", "candidateSecondaryMobile"}
# One per candidate, settled after the move: the kept record's status wins, the conversation is carried over
SETTLED_AFTER_MOVE = {"candidate_status", "thunder_cadence_state"}
MIN_LOCAL_PART = 5
CADENCE_RANK = {"STOPPED": 0, "ACTIVE": 1, "NURTURE": 2, "HANDOFF": 3}


class CandidateMergeError(ValueError):
    """The merge cannot go ahead; the message says why."""


def last_digits(phone: Optional[str]) -> str:
    """The national number: "+91 89103 53068" and "8910353068" are one phone."""
    return re.sub(r"\D", "", phone or "")[-10:]


def resolve_merged(db: Session, candidate: Optional[Candidate]) -> Optional[Candidate]:
    """The record to use: the one this was merged into, else this one (merged_into_id is only on records
    archived before 2026-11-09, until the startup migration folds them in)."""
    seen = set()
    while candidate is not None and candidate.merged_into_id and candidate.candidateID not in seen:
        seen.add(candidate.candidateID)
        candidate = db.get(Candidate, candidate.merged_into_id) or candidate
    return candidate


def kept_record_for_id(db: Session, candidate_id: str) -> Optional[str]:
    """A removed duplicate's id -> the id of the record it was merged into."""
    row = db.get(CandidateMerge, candidate_id)
    return row.kept_id if row is not None else None


def kept_record_for_contact(db: Session, email: Optional[str] = None, mobile: Optional[str] = None) -> Optional[Candidate]:
    """The record kept for a removed duplicate's email or phone."""
    query = db.query(CandidateMerge)
    row = None
    if email:
        email = email.strip().lower()
        row = query.filter(or_(func.lower(CandidateMerge.email) == email,
                               func.lower(CandidateMerge.secondary_email) == email)).first()
    digits = last_digits(mobile)
    if row is None and len(digits) >= 7:
        row = next((m for m in query.filter(or_(CandidateMerge.mobile.isnot(None), CandidateMerge.secondary_mobile.isnot(None)))
                    if digits in (last_digits(m.mobile), last_digits(m.secondary_mobile))), None)
    return db.get(Candidate, row.kept_id) if row is not None else None


def _database_only_columns(db: Session, known) -> List:
    """Foreign keys to candidates the database has but the models don't (older tables): read from the database, so a
    merge moves their rows too instead of being blocked by them or losing them to a cascade."""
    from sqlalchemy import MetaData, Table, text

    if db.bind is None or db.bind.dialect.name != "postgresql":
        return []
    rows = db.execute(text("""
        SELECT c.conrelid::regclass::text, a.attname
        FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f' AND c.confrelid = to_regclass('app_schema.candidates')""")).all()
    columns, metadata = [], MetaData()
    for qualified, column_name in rows:
        schema, _, name = qualified.rpartition(".")
        if name == Candidate.__tablename__ or (name, column_name) in known:
            continue
        table = Table(name, metadata, schema=schema or None, autoload_with=db.connection())
        columns.append((table, table.c[column_name], None))
    return columns


def _candidate_columns(db: Optional[Session] = None) -> List:
    columns = []
    for table in Base.metadata.sorted_tables:
        if table.name == Candidate.__tablename__:
            continue
        for column in table.columns:
            if any(fk.target_fullname.endswith("candidates.candidateID") for fk in column.foreign_keys) \
                    or EXTRA_COLUMNS.get(table.name) == column.name:
                columns.append((table, column, None))
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    for name, id_column, type_column in ENTITY_COLUMNS:
        if name in tables:
            columns.append((tables[name], tables[name].c[id_column], tables[name].c[type_column]))
    if db is not None:
        columns += _database_only_columns(db, {(table.name, column.name) for table, column, _ in columns})
    return columns


def _move(db: Session, table, column, type_column, source_id: str, target_id: str) -> Dict[str, int]:
    """Move one column's rows; when the kept record already holds a unique counterpart, row by row, leaving that one."""
    condition = column == source_id
    if type_column is not None:
        condition = condition & (func.lower(type_column) == "candidate")
    try:
        with db.begin_nested():
            return {"moved": db.execute(update(table).where(condition).values({column.name: target_id})).rowcount, "kept": 0}
    except ProgrammingError as exc:  # a table this database does not have: nothing of it to move
        logger.error(f"[CandidateMerge] {table.name} could not be read: {exc}", exc_info=True)
        return {"moved": 0, "kept": 0}
    except IntegrityError:
        pass
    keys = list(table.primary_key.columns)
    moved = kept = 0
    for row in db.execute(table.select().where(condition)).mappings().all():
        one = condition
        for key in keys:
            one = one & (key == row[key.name])
        try:
            with db.begin_nested():
                db.execute(update(table).where(one).values({column.name: target_id}))
            moved += 1
        except IntegrityError:
            if _absorb(db, table, column, row, one, target_id):
                moved += 1
            else:
                kept += 1
    return {"moved": moved, "kept": kept}


def _absorb(db: Session, table, column, row, this_row, target_id: str) -> bool:
    """The kept record already has this one-per-candidate row: what only the duplicate's row knows goes onto it, and
    the duplicate's row goes. False when it has to stay."""
    if table.name in SETTLED_AFTER_MOVE:
        return False
    key_columns = set(table.primary_key.columns)
    same = column == target_id
    for shared in ("job_id", "demand_id"):  # one row per candidate and job
        if shared in table.c and row[shared] is not None:
            same = same & (table.c[shared] == row[shared])
    kept_row = db.execute(table.select().where(same)).mappings().first()
    if kept_row is None:
        return False
    blanks = {c.name: row[c.name] for c in table.columns
              if c not in key_columns and c is not column and kept_row[c.name] is None and row[c.name] is not None}
    try:
        with db.begin_nested():
            if blanks:
                one = same
                for key in key_columns:
                    one = one & (key == kept_row[key.name])
                db.execute(update(table).where(one).values(blanks))
            db.execute(table.delete().where(this_row))
        return True
    except IntegrityError as exc:  # something still points at the duplicate's row
        logger.warning(f"[CandidateMerge] {table.name} row stays on the duplicate: {exc}")
        return False


def _carry_live_cadence(source, target) -> None:
    """Both records had a cadence: the kept record continues the conversation furthest along, so a person already
    talking to Thunder on the duplicate never gets a cold follow-up on the record kept."""
    if target is None:
        return
    moments = [m for m in (source.last_inbound_at, target.last_inbound_at) if m]
    source_leads = (source.last_inbound_at == max(moments) if moments
                    else CADENCE_RANK.get(source.stage, 0) > CADENCE_RANK.get(target.stage, 0))
    if source_leads and (not moments or source.last_inbound_at != target.last_inbound_at):
        target.job_id, target.cadence_seq = source.job_id or target.job_id, source.cadence_seq
        target.stage, target.next_step, target.next_action_at = source.stage, source.next_step, source.next_action_at
        target.stop_reason = source.stop_reason
    target.touches_sent = (target.touches_sent or 0) + (source.touches_sent or 0)
    outbound = [m for m in (source.last_outbound_at, target.last_outbound_at) if m]
    target.last_outbound_at = max(outbound) if outbound else None
    target.last_inbound_at = max(moments) if moments else None


def _keep_contact_details(source: Candidate, target: Candidate) -> None:
    """The duplicate's email and phone become the kept record's secondary ones (the kept record's stay primary)."""
    emails = {(target.candidateEmail or "").lower(), (target.candidateSecondaryEmail or "").lower()}
    for email in (source.candidateEmail, source.candidateSecondaryEmail):
        if email and email.lower() not in emails and not target.candidateSecondaryEmail:
            target.candidateSecondaryEmail = email
            emails.add(email.lower())
    phones = {last_digits(target.candidateMobile), last_digits(target.candidateSecondaryMobile)}
    for phone in (source.candidateMobile, source.candidateSecondaryMobile):
        if phone and last_digits(phone) not in phones and not target.candidateSecondaryMobile:
            target.candidateSecondaryMobile = phone
            phones.add(last_digits(phone))


def merge_candidates(db: Session, source: Candidate, target: Candidate, *, merged_by: str,
                     merged_by_name: Optional[str] = None) -> Dict:
    """Fold source into target (kept) and remove source. Commits; on any failure nothing changes."""
    from app.models.employee import Employee

    if source.candidateID == target.candidateID:
        raise CandidateMergeError("Pick a different candidate: this is the same record.")
    if source.merged_into_id or target.merged_into_id:
        raise CandidateMergeError("One of these records was already merged: open the record it was merged into.")
    if source.tenant_id != target.tenant_id:
        raise CandidateMergeError("These candidates belong to different organisations.")
    if db.query(Employee.id).filter(Employee.candidate_id == source.candidateID).first() \
            and db.query(Employee.id).filter(Employee.candidate_id == target.candidateID).first():
        raise CandidateMergeError("Both records are employees: an employee record cannot be merged here.")
    try:
        result = fold_into(db, source, target, merged_by=merged_by, merged_by_name=merged_by_name)
    except Exception:
        db.rollback()
        raise
    db.commit()
    logger.info(f"[CandidateMerge] {result['removed_candidate_id']} -> {result['kept_candidate_id']} by {merged_by}: "
                f"{result['records_moved']} moved")
    return result


def fold_into(db: Session, source: Candidate, target: Candidate, *, merged_by: str,
              merged_by_name: Optional[str] = None, carry_conversation: bool = True) -> Dict:
    """Move everything from source to target, settle the one-per-candidate rows, record the merge and remove source.
    Flushes, does not commit. carry_conversation=False for a record archived before 2026-11-09, whose conversation
    was carried over then."""
    from app.models.hiring_pipeline import HiringPipeline
    from app.models.thunder_email import ThunderCadenceState

    source_id, target_id = source.candidateID, target.candidateID
    source_name = " ".join(p for p in (source.candidateFirstName, source.candidateLastName) if p) or None
    contact = {"email": source.candidateEmail, "secondary_email": source.candidateSecondaryEmail,
               "mobile": source.candidateMobile, "secondary_mobile": source.candidateSecondaryMobile}
    # the kept record's status wins (one per candidate, though the table allows more): the duplicate's goes first
    if db.query(CandidateStatus.id).filter(CandidateStatus.candidateID == target_id).first():
        db.query(CandidateStatus).filter(CandidateStatus.candidateID == source_id).delete(synchronize_session=False)
    # a second open pipeline can't sit beside the kept record's open one: closed, it moves with its history
    if db.query(HiringPipeline.id).filter(HiringPipeline.candidate_id == target_id, HiringPipeline.closed_at.is_(None)).first():
        db.query(HiringPipeline).filter(HiringPipeline.candidate_id == source_id, HiringPipeline.closed_at.is_(None)) \
            .update({"closed_at": datetime.utcnow()}, synchronize_session=False)
    copied = []
    for column in Candidate.__table__.columns:
        if column.name in NEVER_COPIED:
            continue
        for attribute in Candidate.__mapper__.column_attrs:
            if attribute.columns[0] is column:
                if getattr(target, attribute.key) in (None, "") and getattr(source, attribute.key) not in (None, ""):
                    setattr(target, attribute.key, getattr(source, attribute.key))
                    copied.append(attribute.key)
                break
    db.flush()

    moved = kept = 0
    for table, column, type_column in _candidate_columns(db):
        result = _move(db, table, column, type_column, source_id, target_id)
        moved += result["moved"]
        kept += result["kept"]
    db.expire_all()

    # Earlier merges into the duplicate now lead to the kept record
    db.query(Candidate).filter(Candidate.merged_into_id == source_id).update({"merged_into_id": target_id},
                                                                             synchronize_session=False)
    db.query(CandidateMerge).filter(CandidateMerge.kept_id == source_id).update({"kept_id": target_id},
                                                                                synchronize_session=False)
    source = db.get(Candidate, source_id)
    target = db.get(Candidate, target_id)
    _keep_contact_details(source, target)
    # the conversation the kept record already had: the live one carries over, the duplicate's goes
    for state in db.query(ThunderCadenceState).filter(ThunderCadenceState.candidate_id == source_id).all():
        if carry_conversation:
            _carry_live_cadence(state, db.get(ThunderCadenceState, target_id))
        db.delete(state)
    db.flush()

    left = _still_pointing_at(db, source_id)
    if left:  # nothing may lose its candidate: the whole merge is undone by the caller
        raise CandidateMergeError("These records could not be moved to the record kept, so nothing was merged: "
                                  + ", ".join(f"{table} ({count})" for table, count in sorted(left.items())))
    db.add(CandidateMerge(merged_id=source_id, kept_id=target_id, tenant_id=target.tenant_id, name=source_name,
                          merged_by=merged_by, merged_by_name=merged_by_name, records_moved=moved, **contact))
    other = ", ".join(v for v in (contact["email"], contact["mobile"]) if v)
    db.add(CandidateHistory(candidateID=target_id, event_type="Custom", performed_by_id=merged_by,
                            performed_by_name=merged_by_name, event_at=datetime.utcnow(),
                            note=f"Merged {source_name or 'a duplicate record'} ({source_id}) into this record: {moved} "
                                 f"record{'' if moved == 1 else 's'} moved and both histories shown here as one. "
                                 f"Its contact details stay on file: {other}."))
    db.delete(source)
    db.flush()
    return {"kept_candidate_id": target_id, "removed_candidate_id": source_id, "records_moved": moved,
            "fields_filled": copied}


def _still_pointing_at(db: Session, candidate_id: str) -> Dict[str, int]:
    left = {}
    for table, column, type_column in _candidate_columns(db):
        condition = column == candidate_id
        if type_column is not None:
            condition = condition & (func.lower(type_column) == "candidate")
        try:
            with db.begin_nested():
                count = db.execute(table.select().with_only_columns(func.count()).where(condition)).scalar()
        except ProgrammingError:  # a table this database does not have
            continue
        if count:
            left[table.name] = count
    return left


def finish_archived_merges(db: Session) -> int:
    """Records archived by a merge before 2026-11-09 are folded into the record kept and removed. Flushes."""
    done = 0
    for source in db.query(Candidate).filter(Candidate.merged_into_id.isnot(None)).all():
        target = resolve_merged(db, source)
        if target is None or target.candidateID == source.candidateID:
            continue
        source.merged_into_id = None
        db.flush()
        fold_into(db, source, target, merged_by="system", merged_by_name="Merge clean-up (one record per person)",
                  carry_conversation=False)
        done += 1
    return done


def possible_duplicates(db: Session, candidate: Candidate, query: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """Likely the same person: same phone, LinkedIn, email name, or the name typed into the search."""
    base = db.query(Candidate).filter(Candidate.tenant_id == candidate.tenant_id, Candidate.candidateID != candidate.candidateID,
                                      Candidate.merged_into_id.is_(None))
    found: Dict[str, Dict] = {}

    def add(rows, reason):
        for row in rows:
            found.setdefault(row.candidateID, {
                "id": row.candidateID, "reason": reason, "email": row.candidateEmail, "phone": row.candidateMobile,
                "name": " ".join(p for p in (row.candidateFirstName, row.candidateLastName) if p),
                "source": row.candidateSource, "linkedin_url": row.linkedin_url,
                "created_at": row.candidateCreatedAt.isoformat() if row.candidateCreatedAt else None})

    phone = last_digits(candidate.candidateMobile)
    if len(phone) >= 10:
        add(base.filter(func.right(func.regexp_replace(Candidate.candidateMobile, r"\D", "", "g"), 10) == phone).limit(limit), "Same phone")
    if candidate.linkedin_url:
        add(base.filter(func.lower(func.rtrim(Candidate.linkedin_url, "/")) == candidate.linkedin_url.rstrip("/").lower()).limit(limit), "Same LinkedIn")
    local = (candidate.candidateEmail or "").split("@")[0].lower()
    if len(local) >= MIN_LOCAL_PART:
        add(base.filter(func.lower(Candidate.candidateEmail).like(f"{local}@%")).limit(limit), "Same email name")
    if candidate.candidateLastName and candidate.candidateFirstName:
        add(base.filter(func.lower(Candidate.candidateLastName) == candidate.candidateLastName.lower(),
                        func.lower(Candidate.candidateFirstName).like(f"{candidate.candidateFirstName[:3].lower()}%")).limit(limit),
            "Similar name")
    term = (query or "").strip().lower()
    if len(term) >= 2:
        like = f"%{term}%"
        add(base.filter(or_(func.lower(Candidate.candidateEmail).like(like), func.lower(Candidate.candidateFirstName).like(like),
                            func.lower(Candidate.candidateLastName).like(like),
                            func.lower(Candidate.candidateFirstName + " " + Candidate.candidateLastName).like(like))).limit(limit), "Search")
    return list(found.values())[:limit]
