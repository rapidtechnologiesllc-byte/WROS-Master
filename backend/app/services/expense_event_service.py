"""
Shared conference/event records for expenses (CEO 2026-10-31): "when we give 1 conference name it
has to also make sure all team members use same or similar details to have the record built into
1 event".

- An event is (tenant, name_key, year): "NAMIC 2026", "Namic-2026" and "namic 2026" are one event.
- Creating an event that already exists returns the existing one; creating one that is close to an
  existing event of the same year ("NAMIC Conf 2026") is refused with the matches, unless the
  person confirms it really is a different event.
- Finance merges two events that turned out to be the same: the expenses move to the target and
  the merged event points at it (it is no longer offered).
- The rollup totals an event's expenses per client (and internal spend) and per person.
"""
import difflib
import re
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.expense import ExpenseEvent, ExpenseRecord

YEAR_TOKEN = re.compile(r"^(19|20)\d{2}$")
NEAR_DUPLICATE_SCORE = 0.85  # same year and this close = probably the same event
SUGGESTION_SCORE = 0.6       # typeahead shows anything at least this close


class ExpenseEventError(Exception):
    pass


class NearDuplicateEventError(ExpenseEventError):
    def __init__(self, message: str, matches: List[ExpenseEvent]):
        super().__init__(message)
        self.matches = matches


def event_key(name: str) -> Tuple[str, Optional[int]]:
    """(name_key, year named in it): lower-case words without punctuation, spaces or the year."""
    tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    years = [int(t) for t in tokens if YEAR_TOKEN.match(t)]
    key = "".join(t for t in tokens if not YEAR_TOKEN.match(t))
    return key, (years[0] if years else None)


def match_score(key: str, other_key: str) -> float:
    """1.0 for the same key; 0.9 when one contains the other ("namic" / "namicannual"); else the
    similarity ratio of the two keys."""
    if not key or not other_key:
        return 0.0
    if key == other_key:
        return 1.0
    if min(len(key), len(other_key)) >= 4 and (key in other_key or other_key in key):
        return 0.9
    return difflib.SequenceMatcher(None, key, other_key).ratio()


def live_event(db: Session, event: Optional[ExpenseEvent]) -> Optional[ExpenseEvent]:
    """Follow merges to the event that is still in use."""
    seen = set()
    while event is not None and event.merged_into_id and event.id not in seen:
        seen.add(event.id)
        event = db.query(ExpenseEvent).filter(ExpenseEvent.id == event.merged_into_id).first()
    return event


def get_event(db: Session, tenant_id: int, event_id: str) -> ExpenseEvent:
    event = db.query(ExpenseEvent).filter(ExpenseEvent.id == event_id, ExpenseEvent.tenant_id == tenant_id).first()
    if event is None:
        raise ExpenseEventError(f"Event {event_id!r} not found.")
    return live_event(db, event)


def search_events(db: Session, tenant_id: int, q: Optional[str] = None, year: Optional[int] = None,
                  limit: int = 20) -> List[Tuple[ExpenseEvent, float]]:
    """The tenant's live events closest to `q` (best first); every event, newest first, without q."""
    query = db.query(ExpenseEvent).filter(ExpenseEvent.tenant_id == tenant_id, ExpenseEvent.merged_into_id.is_(None))
    events = query.all()
    key, named_year = event_key(q or "")
    year = year or named_year
    if year:
        events = [e for e in events if e.year == year]
    if not key:
        return [(e, 1.0) for e in sorted(events, key=lambda e: (-e.year, e.name.lower()))][:limit]
    scored = [(e, match_score(key, e.name_key)) for e in events]
    # a prefix of the name the person is still typing ("nam") counts as a strong match
    scored = [(e, max(score, 0.95 if e.name_key.startswith(key) else 0.0)) for e, score in scored]
    scored = [(e, s) for e, s in scored if s >= SUGGESTION_SCORE]
    return sorted(scored, key=lambda pair: (-pair[1], -pair[0].year, pair[0].name.lower()))[:limit]


def find_or_create_event(db: Session, *, tenant_id: int, name: str, year: Optional[int] = None,
                         start_date: Optional[date] = None, end_date: Optional[date] = None,
                         location: Optional[str] = None, created_by_user_id: Optional[str] = None,
                         confirm_new: bool = False) -> Tuple[ExpenseEvent, bool]:
    """(event, created). The same name and year returns the existing event; a near match of the
    same year is refused (NearDuplicateEventError) unless confirm_new. Flushes, never commits."""
    name = (name or "").strip()
    key, named_year = event_key(name)
    if not key:
        raise ExpenseEventError("The event needs a name.")
    year = year or named_year or (start_date.year if start_date else None)
    if not year:
        raise ExpenseEventError("The event needs a year (in its name, or its dates).")
    if named_year and named_year != year:
        raise ExpenseEventError(f"The name says {named_year} but the year is {year}.")
    if start_date and end_date and end_date < start_date:
        raise ExpenseEventError("The event can't end before it starts.")

    existing = db.query(ExpenseEvent).filter(ExpenseEvent.tenant_id == tenant_id, ExpenseEvent.name_key == key,
                                             ExpenseEvent.year == year).first()
    if existing is not None:
        return live_event(db, existing), False
    if not confirm_new:
        close = [e for e, score in search_events(db, tenant_id, name, year) if score >= NEAR_DUPLICATE_SCORE]
        if close:
            raise NearDuplicateEventError(
                f"{name!r} looks like an event your team already logged: "
                + ", ".join(e.name for e in close) + ". Pick it, or confirm this is a different event.", close)

    event = ExpenseEvent(tenant_id=tenant_id, name=name[:300], name_key=key[:300], year=year,
                         start_date=start_date, end_date=end_date, location=(location or None),
                         created_by_user_id=created_by_user_id)
    db.add(event)
    db.flush()
    logger.info(f"[ExpenseEvent] created {event.id} {event.name!r} ({year}) for tenant {tenant_id}")
    return event, True


def merge_events(db: Session, source: ExpenseEvent, target: ExpenseEvent) -> int:
    """Move every expense of `source` to `target` and retire `source`. Returns expenses moved.
    Commits."""
    target = live_event(db, target)
    if source.tenant_id != target.tenant_id:
        raise ExpenseEventError("Events of different tenants can't be merged.")
    if source.id == target.id or source.merged_into_id:
        raise ExpenseEventError("That event is already merged.")
    moved = db.query(ExpenseRecord).filter(ExpenseRecord.event_id == source.id).update(
        {ExpenseRecord.event_id: target.id, ExpenseRecord.conference_name: target.name}, synchronize_session=False)
    source.merged_into_id = target.id
    db.add(source)
    db.commit()
    logger.info(f"[ExpenseEvent] merged {source.id} into {target.id} ({moved} expenses moved)")
    return moved


def event_rollup(db: Session, event: ExpenseEvent, expenses: List[ExpenseRecord]) -> Dict:
    """Totals for one event over `expenses` (the caller's visible expenses of the event): all
    not-rejected spend, how much is approved vs pending, per client (None = internal) and per
    person."""
    from app.models.client import Client
    from app.models.user import Users
    from app.services.expense_service import expense_shares

    counted = [e for e in expenses if e.manager_approval_status != "REJECTED"]
    shares = expense_shares(counted)
    by_client: Dict[Optional[str], int] = defaultdict(int)
    by_person: Dict[str, int] = defaultdict(int)
    approved = pending = 0
    for expense in counted:
        for client_id, cents in shares[expense.id]:
            by_client[client_id] += cents
        by_person[expense.logged_by_user_id] += expense.amount_usd_cents
        if expense.manager_approval_status == "APPROVED":
            approved += expense.amount_usd_cents
        else:
            pending += expense.amount_usd_cents
    client_ids = [c for c in by_client if c]
    client_names = dict(db.query(Client.id, Client.company_name).filter(Client.id.in_(client_ids)).all()) \
        if client_ids else {}
    people = dict(db.query(Users.UserID, Users.UserName).filter(Users.UserID.in_(list(by_person))).all()) \
        if by_person else {}
    return {
        "event_id": event.id, "name": event.name, "year": event.year, "start_date": event.start_date,
        "end_date": event.end_date, "location": event.location,
        "total_usd_cents": approved + pending, "approved_usd_cents": approved, "pending_usd_cents": pending,
        "expense_count": len(counted),
        "by_client": sorted(({"client_id": c, "company_name": client_names.get(c) if c else "Internal (no client)",
                              "amount_usd_cents": v} for c, v in by_client.items()),
                            key=lambda r: -r["amount_usd_cents"]),
        "by_person": sorted(({"user_id": u, "name": people.get(u) or u, "amount_usd_cents": v}
                             for u, v in by_person.items()), key=lambda r: -r["amount_usd_cents"]),
    }
