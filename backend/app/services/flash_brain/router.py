"""Intent routing for phrasings Flash's rules do not recognise. A model may only pick one of the
known intents and extract a short query -- it never answers; every answer is a real DB lookup.
The small (parsing) model routes when it is up, else the large one; any failure means "not
routed" and the caller gives its honest "unsupported" reply."""
import logging
from typing import Dict, List, Optional

from app.services.flash_brain.llm import BrainUnavailable, Brains

logger = logging.getLogger(__name__)

ROUTE_PURPOSE = "intent"
MAX_QUERY_CHARS = 200


def _schema(intents: Dict[str, str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["intent", "query"],
            "properties": {"intent": {"type": "string", "enum": sorted(intents) + ["unknown"]},
                           "query": {"type": "string"}}}


def route_intent(brains: Brains, message: str, *, intents: Dict[str, str], history: Optional[List[Dict]] = None,
                 tenant_id) -> Optional[Dict]:
    """{"intent", "query", "routed_by"} for one of `intents`, or None when no brain can route it."""
    listing = "\n".join(f"- {name}: {desc}" for name, desc in intents.items())
    system = ("You route questions for BlitzenX's internal staffing assistant. You never answer them. "
              "Pick the intent that fits the question (\"unknown\" if none does) and a short search query.\n"
              f"Intents:\n{listing}")
    recent = "\n".join(f"Q: {t.get('question', '')}\nA: {str(t.get('reply', ''))[:200]}" for t in (history or []))
    user = (f"Recent conversation:\n{recent}\n\n" if recent else "") + f"Question: {message}"
    for which, brain in (("small", brains.small), ("large", brains.large)):
        if brain is None:
            continue
        try:
            parsed = brain.extract_json(purpose=ROUTE_PURPOSE, system=system, user=user,
                                        schema=_schema(intents), tenant_id=tenant_id)
        except BrainUnavailable as exc:
            logger.warning(f"[Flash] {which} brain could not route: {exc}")
            continue
        if parsed["intent"] not in intents:
            return None
        return {"intent": parsed["intent"], "query": str(parsed["query"])[:MAX_QUERY_CHARS].strip(),
                "routed_by": which}
    return None
