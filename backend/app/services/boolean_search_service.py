"""Boolean search over candidates' skills and resumes.

A query is words and "quoted phrases" joined by AND, OR, NOT and brackets; words side by side mean AND.
    guidewire AND (policycenter OR "claim center") NOT tester
A word that is a skill with known other names (app.constants.skill_synonyms, plus the names the team added:
SkillSynonym) also finds those names; a quoted phrase is matched exactly as written. Matching is on whole words,
any case. Each search says how many candidates each word finds on its own and, when it finds nothing or too much,
how to change it (suggestions: rules only).

What is searched for each candidate: their skills (skill tags and the skills on their record), their job title,
and the text of their resume. The result says where each term was found, so a recruiter sees whether the match
is a recorded skill or only a line in the resume.

Rules only: no model is used, so the search works the same with or without an AI key.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.constants.skill_synonyms import SKILL_SYNONYMS
from app.models.candidate import Candidate
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Users

logger = logging.getLogger(__name__)

MAX_QUERY_CHARS = 2000
MAX_TERMS = 60
MAX_RESULTS = 200
SNIPPET_CHARS = 90
SKILL_WEIGHT, TITLE_WEIGHT, RESUME_WEIGHT = 3, 2, 1
OPERATORS = ("AND", "OR", "NOT")
TOKEN = re.compile(r'"([^"]*)"|(\()|(\))|([^\s()"]+)')
SYNONYMS_BY_NAME = {name.lower(): [name, *others] for name, others in SKILL_SYNONYMS.items()}


class BooleanQueryError(ValueError):
    """The query cannot be read; the message says what to fix."""


# ---- the query ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Term:
    text: str
    exact: bool = False  # a quoted phrase: no other names


@dataclass(frozen=True)
class Not:
    node: object


@dataclass(frozen=True)
class And:
    nodes: Tuple


@dataclass(frozen=True)
class Or:
    nodes: Tuple


def _tokens(query: str) -> List[Tuple[str, str]]:
    if query.count('"') % 2:
        raise BooleanQueryError('A quoted phrase is not closed: add the missing ".')
    tokens = []
    for phrase, opening, closing, word in TOKEN.findall(query):
        if opening or closing:
            tokens.append(("bracket", opening or closing))
        elif word:
            tokens.append(("op", word.upper()) if word.upper() in OPERATORS else ("term", word))
        elif phrase.strip():
            tokens.append(("phrase", " ".join(phrase.split())))
    return tokens


class _Parser:
    """or := and (OR and)* ; and := not ((AND)? not)* ; not := NOT not | ( or ) | term"""

    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens, self.at = tokens, 0

    def _peek(self) -> Optional[Tuple[str, str]]:
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def _take(self) -> Tuple[str, str]:
        token = self.tokens[self.at]
        self.at += 1
        return token

    def parse(self):
        node = self._or()
        if self._peek() is not None:
            raise BooleanQueryError("There is a closing bracket with no opening bracket.")
        return node

    def _or(self):
        nodes = [self._and()]
        while self._peek() == ("op", "OR"):
            self._take()
            nodes.append(self._and())
        return nodes[0] if len(nodes) == 1 else Or(tuple(nodes))

    def _and(self):
        nodes = [self._not()]
        while True:
            token = self._peek()
            if token is None or token == ("op", "OR") or token == ("bracket", ")"):
                break
            if token == ("op", "AND"):
                self._take()
            nodes.append(self._not())
        return nodes[0] if len(nodes) == 1 else And(tuple(nodes))

    def _not(self):
        token = self._peek()
        if token is None:
            raise BooleanQueryError("The search ends with AND, OR or NOT: add the word that follows it.")
        if token == ("op", "NOT"):
            self._take()
            return Not(self._not())
        if token == ("bracket", "("):
            self._take()
            node = self._or()
            if self._peek() != ("bracket", ")"):
                raise BooleanQueryError("A bracket is not closed: add the missing ).")
            self._take()
            return node
        if token[0] == "op":
            raise BooleanQueryError(f"{token[1]} needs a word before it.")
        if token == ("bracket", ")"):
            raise BooleanQueryError("There is an empty pair of brackets, or a closing bracket too early.")
        kind, text = self._take()
        return Term(text, exact=kind == "phrase")


def parse_query(query: str):
    """The query as a tree of And / Or / Not / Term. Raises BooleanQueryError with what to fix."""
    query = (query or "").strip()
    if not query:
        raise BooleanQueryError("Type what to search for, e.g. guidewire AND policycenter.")
    if len(query) > MAX_QUERY_CHARS:
        raise BooleanQueryError(f"The search is too long: keep it under {MAX_QUERY_CHARS} characters.")
    tokens = _tokens(query)
    if not tokens:
        raise BooleanQueryError("Type what to search for, e.g. guidewire AND policycenter.")
    tree = _Parser(tokens).parse()
    terms = all_terms(tree)
    if len(terms) > MAX_TERMS:
        raise BooleanQueryError(f"The search has {len(terms)} terms: the limit is {MAX_TERMS}.")
    if not positive_terms(tree):
        raise BooleanQueryError("A search needs at least one word to find, not only words to leave out.")
    return tree


def all_terms(node) -> List[Term]:
    if isinstance(node, Term):
        return [node]
    if isinstance(node, Not):
        return all_terms(node.node)
    found: List[Term] = []
    for child in node.nodes:
        found += [t for t in all_terms(child) if t not in found]
    return found


def positive_terms(node, negated: bool = False) -> List[Term]:
    """Terms the candidate should have (not under a NOT)."""
    if isinstance(node, Term):
        return [] if negated else [node]
    if isinstance(node, Not):
        return positive_terms(node.node, not negated)
    found: List[Term] = []
    for child in node.nodes:
        found += [t for t in positive_terms(child, negated) if t not in found]
    return found


def to_text(node, top: bool = True) -> str:
    """The tree written back as a query, the way the search box shows it."""
    if isinstance(node, Term):
        return f'"{node.text}"' if node.exact or " " in node.text else node.text
    if isinstance(node, Not):
        return f"NOT {to_text(node.node, False)}"
    joiner = " AND " if isinstance(node, And) else " OR "
    text = joiner.join(to_text(child, False) for child in node.nodes)
    return text if top else f"({text})"


# ---- matching -------------------------------------------------------------------------------------

def synonyms_for(db: Session, tenant_id) -> Dict[str, List[str]]:
    """Every skill's other names for this tenant: the built-in list with the team's own names added."""
    from app.models.job_search import SkillSynonym

    merged = {key: list(names) for key, names in SYNONYMS_BY_NAME.items()}
    if tenant_id is None:
        return merged
    for row in db.query(SkillSynonym).filter(SkillSynonym.tenant_id == tenant_id).all():
        names = merged.setdefault(row.skill_key, [row.skill])
        for other in row.other_names or []:
            if other.lower() not in {n.lower() for n in names}:
                names.append(other)
    return merged


def _names(term: Term, synonyms: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """What to look for in the text: the term, and for a known skill its other names."""
    if term.exact:
        return [term.text]
    return (synonyms if synonyms is not None else SYNONYMS_BY_NAME).get(term.text.lower(), [term.text])


def _pattern(term: Term, synonyms: Optional[Dict[str, List[str]]] = None) -> re.Pattern:
    """Whole words, any case: java does not find javascript, and c++ or .net are found as written."""
    parts = [re.escape(name).replace(r"\ ", r"\s+") for name in _names(term, synonyms)]
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")(?![A-Za-z0-9])", re.IGNORECASE)


@dataclass
class Document:
    """What is searched for one candidate."""
    skills: str = ""
    title: str = ""
    resume: str = ""


@dataclass
class Match:
    found: Dict[str, List[str]] = field(default_factory=dict)  # term -> where: "skills" / "title" / "resume"
    score: int = 0
    snippet: str = ""


def _where(pattern: re.Pattern, document: Document) -> List[str]:
    return [name for name, text in (("skills", document.skills), ("title", document.title), ("resume", document.resume))
            if text and pattern.search(text)]


def _holds(node, found: Dict[Term, List[str]]) -> bool:
    if isinstance(node, Term):
        return bool(found[node])
    if isinstance(node, Not):
        return not _holds(node.node, found)
    results = (_holds(child, found) for child in node.nodes)
    return all(results) if isinstance(node, And) else any(results)


def _snippet(pattern: re.Pattern, text: str) -> str:
    hit = pattern.search(text)
    if hit is None:
        return ""
    start, end = max(hit.start() - SNIPPET_CHARS, 0), min(hit.end() + SNIPPET_CHARS, len(text))
    return ("…" if start else "") + " ".join(text[start:end].split()) + ("…" if end < len(text) else "")


class CompiledQuery:
    """A parsed query ready to test many candidates."""

    def __init__(self, query: str, synonyms: Optional[Dict[str, List[str]]] = None):
        self.tree = parse_query(query)
        self.text = to_text(self.tree)
        self._synonyms = synonyms
        self._patterns = {term: _pattern(term, synonyms) for term in all_terms(self.tree)}
        self._positive = positive_terms(self.tree)

    def expanded(self) -> Dict[str, List[str]]:
        """Each word searched for and every name it also finds (its synonyms)."""
        return {term.text: _names(term, self._synonyms) for term in self._positive}

    def term_counts(self, documents: Iterable[Document]) -> Dict[str, int]:
        """How many of these candidates each word finds on its own."""
        documents = list(documents)
        return {term.text: sum(1 for d in documents if _where(self._patterns[term], d)) for term in self._positive}

    def match(self, document: Document) -> Optional[Match]:
        """How the candidate matches, or None when they do not."""
        found = {term: _where(pattern, document) for term, pattern in self._patterns.items()}
        if not _holds(self.tree, found):
            return None
        match = Match()
        for term in self._positive:
            places = found[term]
            if not places:
                continue  # one side of an OR the candidate does not have
            match.found[term.text] = places
            match.score += (SKILL_WEIGHT if "skills" in places else 0) + (TITLE_WEIGHT if "title" in places else 0) \
                + (RESUME_WEIGHT if "resume" in places else 0)
            if not match.snippet and "resume" in places:
                match.snippet = _snippet(self._patterns[term], document.resume)
        return match


# ---- candidates -----------------------------------------------------------------------------------

def documents_for(db: Session, candidates: Iterable[Candidate]) -> Dict[str, Document]:
    """The searchable text of each candidate, loaded in three queries however many candidates there are."""
    candidates = list(candidates)
    documents = {c.candidateID: Document(skills=c.candidateSkills or "", title=c.candidateJobTitle or "")
                 for c in candidates}
    ids = list(documents)
    if not ids:
        return documents
    for candidate_id, skill in db.query(CandidateSkillTag.candidate_id, CandidateSkillTag.skill_canonical) \
            .filter(CandidateSkillTag.candidate_id.in_(ids)).all():
        documents[candidate_id].skills += f", {skill}"
    for row in db.query(CandidateResumeParsed.candidate_id, CandidateResumeParsed.raw_text,
                        CandidateResumeParsed.skills, CandidateResumeParsed.current_title) \
            .filter(CandidateResumeParsed.candidate_id.in_(ids)).all():
        document = documents[row.candidate_id]
        document.resume = row.raw_text or ""
        if isinstance(row.skills, list):
            document.skills += ", " + ", ".join(str(s.get("name") if isinstance(s, dict) else s) for s in row.skills if s)
        if row.current_title and not document.title:
            document.title = row.current_title
    return documents


def _name(candidate: Candidate) -> str:
    return " ".join(p for p in (candidate.candidateFirstName, candidate.candidateLastName) if p) or candidate.candidateID


MANY_RESULTS = 100


def suggestions(compiled: CompiledQuery, total: int, counts: Dict[str, int], *, filtered: bool) -> List[str]:
    """How to change a search that finds nothing or too much (P908). Rules only."""
    tips = []
    if total == 0:
        missing = [term for term, count in counts.items() if count == 0]
        for term in missing:
            tips.append(f'Nobody here has "{term}": remove it, or add another name it goes by with OR '
                        f'(or add that name to the synonym list).')
        if not missing and len(counts) > 1:
            tips.append("Each word finds candidates, but nobody has them all: join some with OR instead of AND.")
        if filtered:
            tips.append("Try without the experience or location filter.")
    elif total > MANY_RESULTS:
        tips.append(f"{total} candidates match: add a skill they must have (AND), or NOT for what you don't want.")
    return tips


def search_candidates(db: Session, user: Users, query: str, *, min_experience_years: Optional[float] = None,
                      location: Optional[str] = None, include_archived: bool = False, limit: int = 50) -> Dict:
    """Candidates the caller may see who match the query, best first. Raises BooleanQueryError."""
    from app.core.bu_scope import apply_bu_scope_to_candidate_query

    compiled = CompiledQuery(query, synonyms_for(db, user.tenant_id))
    base = db.query(Candidate).filter(Candidate.merged_into_id.is_(None))
    if user.tenant_id is not None:
        base = base.filter(Candidate.tenant_id == user.tenant_id)
    if min_experience_years is not None:
        if min_experience_years < 0:
            raise BooleanQueryError("Experience cannot be negative.")
        base = base.filter(Candidate.total_experience_months >= int(round(min_experience_years * 12)))
    if (location or "").strip():
        base = base.filter(Candidate.candidateCurrentLocation.ilike(f"%{location.strip()}%"))
    if not include_archived:
        from app.models.candidate import CandidateStatus
        from app.services.candidate_contact_policy import ARCHIVED_STATUS

        base = base.filter(~Candidate.candidateID.in_(
            db.query(CandidateStatus.candidateID).filter(CandidateStatus.status == ARCHIVED_STATUS)))
    candidates = apply_bu_scope_to_candidate_query(db, base, user).all()
    documents = documents_for(db, candidates)

    rows = []
    for candidate in candidates:
        match = compiled.match(documents[candidate.candidateID])
        if match is None:
            continue
        rows.append({
            "candidate_id": candidate.candidateID, "name": _name(candidate), "title": candidate.candidateJobTitle,
            "location": candidate.candidateCurrentLocation,
            "experience_years": round(candidate.total_experience_months / 12, 1) if candidate.total_experience_months else None,
            "score": match.score, "found": match.found, "snippet": match.snippet,
            "has_resume": bool(documents[candidate.candidateID].resume),
        })
    rows.sort(key=lambda r: (-r["score"], -(r["experience_years"] or 0), r["name"].lower(), r["candidate_id"]))
    limit = min(max(limit, 1), MAX_RESULTS)
    logger.info(f"[BooleanSearch] {user.UserID}: {len(rows)} of {len(candidates)} candidate(s) match {compiled.text!r}")
    counts = compiled.term_counts(documents.values())
    return {"query": compiled.text, "searched": len(candidates), "total": len(rows), "results": rows[:limit],
            "expanded": compiled.expanded(), "term_counts": counts,
            "suggestions": suggestions(compiled, len(rows), counts,
                                       filtered=min_experience_years is not None or bool((location or "").strip()))}
