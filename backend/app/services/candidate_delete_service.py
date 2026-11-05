"""Deleting a candidate record (CEO 2026-11-05: "delete record only available to CEO and superuser ... i can delete some
of the junk candidates"). Permanent, so: only those two, never someone who became an employee, every record attached
goes with it (the same tables a merge moves), and the audit log keeps who deleted whom.
"""
import logging
from typing import Dict

from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.employee import Employee

logger = logging.getLogger(__name__)

MAX_PASSES = 6  # child tables go first: a row that is still referenced waits for the next pass


class CandidateDeleteError(ValueError):
    """The record cannot be deleted; the message says why."""


def _children_cleared(db: Session, table, ids) -> None:
    """Rows in other tables that point at these rows: gone with them, or unlinked when the link is optional."""
    from sqlalchemy import update

    from app.models.base import Base

    key = next(iter(table.primary_key.columns))
    for child in Base.metadata.sorted_tables:
        for column in child.columns:
            if not any(fk.column is key for fk in column.foreign_keys):
                continue
            if column.nullable:
                db.execute(update(child).where(column.in_(ids)).values({column.name: None}))
            else:
                db.execute(child.delete().where(column.in_(ids)))


def delete_candidate(db: Session, candidate: Candidate, *, deleted_by: str) -> Dict:
    """Delete the candidate and everything attached. All or nothing. Commits."""
    from app.services.candidate_merge_service import _candidate_columns

    candidate_id = candidate.candidateID
    if db.query(Employee.id).filter(Employee.candidate_id == candidate_id).first():
        raise CandidateDeleteError("This candidate became an employee: the employee record depends on them.")
    snapshot = (f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''} | {candidate.candidateEmail} | "
                f"{candidate.candidateMobile or ''} | source {candidate.candidateSource or ''}")
    tenant_id = candidate.tenant_id
    remaining = [(t, c, kind) for t, c, kind in _candidate_columns() if t.name != "employees"]
    removed, blocked = 0, None
    for _ in range(MAX_PASSES):
        if not remaining:
            break
        waiting = []
        for table, column, kind in remaining:
            condition = column == candidate_id
            if kind is not None:
                condition = condition & (kind == "candidate")
            try:
                with db.begin_nested():
                    keys = list(table.primary_key.columns)
                    ids = [r[0] for r in db.execute(table.select().with_only_columns(keys[0]).where(condition)).all()] if len(keys) == 1 else []
                    if ids:
                        _children_cleared(db, table, ids)
                    removed += db.execute(table.delete().where(condition)).rowcount
            except ProgrammingError as exc:  # a table this database does not have
                logger.error(f"[CandidateDelete] {table.name} could not be read: {exc}", exc_info=True)
            except IntegrityError as exc:
                blocked = f"{table.name}: {str(exc.orig)[:200]}"
                waiting.append((table, column, kind))
        remaining = waiting
    if remaining:
        db.rollback()
        logger.error(f"[CandidateDelete] {candidate_id} blocked by {blocked}")
        raise CandidateDeleteError(f"Records still depend on this candidate ({remaining[0][0].name}). Nothing was deleted.")
    db.query(Candidate).filter(Candidate.merged_into_id == candidate_id).update({"merged_into_id": None}, synchronize_session=False)
    db.expire_all()
    db.delete(db.get(Candidate, candidate_id))
    db.add(AuditLog(tenant_id=tenant_id, entity_type="candidate", entity_id=candidate_id, action="delete", user_id=deleted_by,
                    old_value=snapshot))
    db.commit()
    logger.info(f"[CandidateDelete] {candidate_id} deleted by {deleted_by}: {removed} attached record(s)")
    return {"records_removed": removed}
