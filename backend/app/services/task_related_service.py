"""What a task is about, for the "Related to" column of My Tasks (CEO 2026-11-02: "we need to add a
related to column to say which candidate or user it is related to").

annotate_related(db, tasks) sets three plain attributes on each task (not columns): related_kind
("Candidate", "Interview", "Expense", "Invoice"), related_name and related_link (the in-app path
that opens the record). One query per kind for the whole list, never one per task.
"""
from typing import Iterable, List

from sqlalchemy.orm import Session

from app.models.candidate import Candidate


def _candidate_name(candidate: Candidate) -> str:
    return " ".join(p for p in (candidate.candidateFirstName, candidate.candidateLastName) if p) \
        or candidate.candidateEmail or candidate.candidateID


def annotate_related(db: Session, tasks: Iterable) -> List:
    from app.models.expense import ExpenseRecord
    from app.models.invoice import Invoice
    from app.models.user import Interview

    tasks = list(tasks)
    interviews = {i.id: i for i in db.query(Interview).filter(
        Interview.id.in_({t.interview_id for t in tasks if t.interview_id} or {-1}))}
    candidate_ids = {t.candidate_id for t in tasks if t.candidate_id}
    candidate_ids |= {i.candidate_id for i in interviews.values() if i.candidate_id}
    candidates = {c.candidateID: c for c in db.query(Candidate).filter(
        Candidate.candidateID.in_(candidate_ids or {"-"}))}
    invoices = {i.id: i for i in db.query(Invoice).filter(
        Invoice.id.in_({t.invoice_id for t in tasks if t.invoice_id} or {"-"}))}
    expenses = {e.id: e for e in db.query(ExpenseRecord).filter(
        ExpenseRecord.id.in_({t.expense_id for t in tasks if t.expense_id} or {"-"}))}

    for task in tasks:
        kind = name = link = None
        interview = interviews.get(task.interview_id) if task.interview_id else None
        candidate_id = task.candidate_id or (interview.candidate_id if interview else None)
        candidate = candidates.get(candidate_id) if candidate_id else None
        if candidate is not None:
            kind, name, link = ("Interview" if interview and not task.candidate_id else "Candidate",
                                _candidate_name(candidate), f"/candidates/{candidate.candidateID}")
        elif task.invoice_id in invoices:
            invoice = invoices[task.invoice_id]
            kind, name, link = "Invoice", invoice.invoice_number or invoice.id, task.link
        elif task.expense_id in expenses:
            expense = expenses[task.expense_id]
            kind, name, link = "Expense", (expense.description or "Expense")[:80], task.link
        task.related_kind, task.related_name, task.related_link = kind, name, link
    return tasks
