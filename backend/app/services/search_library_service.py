"""What recruiters keep for boolean search (CEO 2026-11-16, open requirements P902 and P911).

Saved searches -- a person's own searches, by name, to run again; each run through one records when and how many
                  matched, so the list doubles as the search history.
Skill synonyms -- the other names a skill goes by that the team adds (SkillSynonym), on top of the platform's own
                  list (app.constants.skill_synonyms, which only changes with a code review). Searching the skill
                  finds every one of its names, in candidate search and in every job's search criteria.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.job_search import SavedCandidateSearch, SkillSynonym
from app.models.user import Users
from app.services.boolean_search_service import SYNONYMS_BY_NAME, CompiledQuery

logger = logging.getLogger(__name__)

MAX_NAME_CHARS = 200
MAX_OTHER_NAMES = 20


class SynonymError(ValueError):
    """The names can't be kept; the message says why."""


# ---- saved searches -----------------------------------------------------------------------------------------

def saved_searches(db: Session, user: Users) -> List[SavedCandidateSearch]:
    """Your saved searches, the one run last first."""
    rows = db.query(SavedCandidateSearch).filter(SavedCandidateSearch.user_id == user.UserID).all()
    return sorted(rows, key=lambda r: (r.last_run_at or r.created_at or datetime.min), reverse=True)


def save_search(db: Session, user: Users, *, name: str, query: str, min_experience_years: Optional[float] = None,
                location: Optional[str] = None) -> SavedCandidateSearch:
    """Keeps the search under its name (the same name replaces it). Raises BooleanQueryError for a query that
    can't be read, or a missing name."""
    from app.services.boolean_search_service import BooleanQueryError

    name = (name or "").strip()[:MAX_NAME_CHARS]
    if not name:
        raise BooleanQueryError("Give the search a name.")
    if min_experience_years is not None and min_experience_years < 0:
        raise BooleanQueryError("Experience cannot be negative.")
    text = CompiledQuery(query).text
    row = db.query(SavedCandidateSearch).filter(SavedCandidateSearch.user_id == user.UserID,
                                                SavedCandidateSearch.name == name).first()
    if row is None:
        row = SavedCandidateSearch(tenant_id=user.tenant_id, user_id=user.UserID, name=name, query=text)
        db.add(row)
    row.query, row.min_experience_years = text, min_experience_years
    row.location = (location or "").strip() or None
    db.commit()
    db.refresh(row)
    return row


def record_run(db: Session, user: Users, saved_id: int, total: int) -> None:
    """When one of your saved searches ran and how many it found; someone else's id changes nothing."""
    row = db.query(SavedCandidateSearch).filter(SavedCandidateSearch.id == saved_id,
                                                SavedCandidateSearch.user_id == user.UserID).first()
    if row is None:
        return
    row.last_run_at, row.last_result_count = datetime.utcnow(), total
    db.commit()


def delete_saved(db: Session, user: Users, saved_id: int) -> bool:
    row = db.query(SavedCandidateSearch).filter(SavedCandidateSearch.id == saved_id,
                                                SavedCandidateSearch.user_id == user.UserID).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


# ---- skill synonyms -----------------------------------------------------------------------------------------

def _rewrite_job_searches(db: Session, tenant_id) -> None:
    """Jobs on the system's search pick up the change at once (job_search_service.rewrite_system_criteria)."""
    from app.services.job_search_service import rewrite_system_criteria

    rewrite_system_criteria(db, tenant_id)


def _built_in(skill_key: str) -> List[str]:
    names = SYNONYMS_BY_NAME.get(skill_key, [])
    return names[1:] if names else []


def _item(skill: str, built_in: List[str], row: Optional[SkillSynonym], db: Session) -> Dict:
    added = list(row.other_names or []) if row else []
    editor = db.get(Users, row.updated_by) if row and row.updated_by else None
    return {"skill": skill, "built_in": built_in, "added": added, "other_names": built_in + added,
            "updated_by_name": (editor.UserName or editor.UserEmail) if editor else None,
            "updated_at": row.updated_at if row else None}


def synonym_library(db: Session, tenant_id) -> List[Dict]:
    """Every skill that has other names, the platform's and the team's, by skill name."""
    rows = {r.skill_key: r for r in db.query(SkillSynonym).filter(SkillSynonym.tenant_id == tenant_id).all()}
    items = {key: _item(names[0], names[1:], rows.get(key), db) for key, names in SYNONYMS_BY_NAME.items()}
    for key, row in rows.items():
        if key not in items:
            items[key] = _item(row.skill, [], row, db)
    return sorted(items.values(), key=lambda i: i["skill"].lower())


def save_synonym(db: Session, user: Users, skill: str, other_names: List[str]) -> Dict:
    """The team's names for a skill, replacing what the team added before. Raises SynonymError."""
    skill = " ".join((skill or "").split())
    if not skill or len(skill) > MAX_NAME_CHARS:
        raise SynonymError("Name the skill.")
    if '"' in skill:
        raise SynonymError("A skill name can't contain quotes.")
    if " " in skill or skill.upper() in ("AND", "OR", "NOT"):
        # a search word is one word; a phrase in quotes is matched exactly as written, never by its other names
        raise SynonymError("The skill is the one word people search for (e.g. PolicyCenter); its other names can be "
                           "several words.")
    key = skill.lower()
    taken = {key, *(n.lower() for n in _built_in(key))}
    names = []
    for name in other_names or []:
        name = " ".join(str(name).split())
        if not name:
            continue
        if '"' in name or len(name) > MAX_NAME_CHARS:
            raise SynonymError(f"{name[:40]!r} can't be used as a name (no quotes, at most {MAX_NAME_CHARS} characters).")
        if name.lower() not in taken:
            taken.add(name.lower())
            names.append(name)
    if not names:
        raise SynonymError("Add at least one other name this skill goes by (one the list doesn't have yet).")
    if len(names) > MAX_OTHER_NAMES:
        raise SynonymError(f"At most {MAX_OTHER_NAMES} other names per skill.")
    row = db.query(SkillSynonym).filter(SkillSynonym.tenant_id == user.tenant_id, SkillSynonym.skill_key == key).first()
    if row is None:
        row = SkillSynonym(tenant_id=user.tenant_id, skill=skill, skill_key=key, other_names=names)
        db.add(row)
    row.other_names, row.updated_by, row.updated_at = names, user.UserID, datetime.utcnow()
    db.flush()
    _rewrite_job_searches(db, user.tenant_id)
    db.commit()
    db.refresh(row)
    logger.info("[SearchLibrary] %s set the other names of %r: %s", user.UserID, skill, names)
    return _item(SYNONYMS_BY_NAME.get(key, [skill])[0], _built_in(key), row, db)


def delete_synonym(db: Session, user: Users, skill: str) -> bool:
    """Removes the names the team added for a skill; the platform's own names stay."""
    row = db.query(SkillSynonym).filter(SkillSynonym.tenant_id == user.tenant_id,
                                        SkillSynonym.skill_key == " ".join((skill or "").split()).lower()).first()
    if row is None:
        return False
    db.delete(row)
    db.flush()
    _rewrite_job_searches(db, user.tenant_id)
    db.commit()
    logger.info("[SearchLibrary] %s removed the team's names for %r", user.UserID, row.skill)
    return True
