"""Merge two candidate records of one person (CEO 2026-11-04: "THE SAME CANDIDATE GOT created twice").

Everything attached to the duplicate moves to the record kept: every table with a foreign key to candidates, the
tables that hold a candidate id without one, and the records addressed by entity or subject. The duplicate is not
deleted: it is archived with merged_into_id set, so its email and phone keep leading to the kept record
(resolve_merged) and its old link opens the kept record. Audit logs are not rewritten: they say what happened.

A row that cannot move because the kept record already has its unique counterpart (one cadence, one status) stays on
the archived record, and the kept record's own row wins.
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.candidate import Candidate, CandidateStatus
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
                "merged_into_id", "tenant_id"}
MIN_LOCAL_PART = 5
CADENCE_RANK = {"STOPPED": 0, "ACTIVE": 1, "NURTURE": 2, "HANDOFF": 3}


class CandidateMergeError(ValueError):
    """The merge cannot go ahead; the message says why."""


def last_digits(phone: Optional[str]) -> str:
    """The national number: "+91 89103 53068" and "8910353068" are one phone."""
    return re.sub(r"\D", "", phone or "")[-10:]


def resolve_merged(db: Session, candidate: Optional[Candidate]) -> Optional[Candidate]:
    """The record to use: the one this was merged into, else this one."""
    seen = set()
    while candidate is not None and candidate.merged_into_id and candidate.candidateID not in seen:
        seen.add(candidate.candidateID)
        candidate = db.get(Candidate, candidate.merged_into_id) or candidate
    return candidate


def _candidate_columns() -> List:
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
            kept += 1
    return {"moved": moved, "kept": kept}


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


def merge_candidates(db: Session, source: Candidate, target: Candidate, *, merged_by: str,
                     merged_by_name: Optional[str] = None) -> Dict:
    """Merge source (archived) into target (kept). Commits."""
    from app.models.employee import Employee
    from app.models.thunder_email import ThunderCadenceState

    if source.candidateID == target.candidateID:
        raise CandidateMergeError("Pick a different candidate: this is the same record.")
    if source.merged_into_id or target.merged_into_id:
        raise CandidateMergeError("One of these records was already merged: open the record it was merged into.")
    if source.tenant_id != target.tenant_id:
        raise CandidateMergeError("These candidates belong to different organisations.")
    if db.query(Employee.id).filter(Employee.candidate_id == source.candidateID).first() \
            and db.query(Employee.id).filter(Employee.candidate_id == target.candidateID).first():
        raise CandidateMergeError("Both records are employees: an employee record cannot be merged here.")

    source_id, target_id = source.candidateID, target.candidateID
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
    for table, column, type_column in _candidate_columns():
        result = _move(db, table, column, type_column, source_id, target_id)
        moved += result["moved"]
        kept += result["kept"]
    db.expire_all()

    # Earlier merges into the duplicate now lead to the kept record
    db.query(Candidate).filter(Candidate.merged_into_id == source_id).update({"merged_into_id": target_id},
                                                                             synchronize_session=False)
    source = db.get(Candidate, source_id)
    target = db.get(Candidate, target_id)
    source.merged_into_id, source.thunder_enabled = target_id, False
    status = db.query(CandidateStatus).filter(CandidateStatus.candidateID == source_id).first()
    if status is None:
        db.add(CandidateStatus(candidateID=source_id, status="Inactive"))
    else:
        status.status = "Inactive"
    for state in db.query(ThunderCadenceState).filter(ThunderCadenceState.candidate_id == source_id).all():
        _carry_live_cadence(state, db.get(ThunderCadenceState, target_id))
        state.stage, state.stop_reason = "STOPPED", f"Merged into {target_id}"
        state.next_step, state.next_action_at = None, None

    other = ", ".join(v for v in (source.candidateEmail, source.candidateMobile) if v)
    db.add(CandidateHistory(candidateID=target_id, event_type="Custom", performed_by_id=merged_by,
                            performed_by_name=merged_by_name, event_at=datetime.utcnow(),
                            note=f"Merged a duplicate record ({source_id}) into this one. Its contact details stay on file: {other}."))
    db.commit()
    logger.info(f"[CandidateMerge] {source_id} -> {target_id} by {merged_by}: {moved} moved, {kept} kept on the duplicate")
    return {"kept_candidate_id": target_id, "archived_candidate_id": source_id, "records_moved": moved,
            "records_left_on_duplicate": kept, "fields_filled": copied}


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
