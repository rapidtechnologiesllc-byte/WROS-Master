"""A/B selection per cadence step: Beta-Bernoulli Thompson sampling.

Online reward = a positive reply (INTERESTED / QUESTION_*) credited to the
touch within REWARD_WINDOW_DAYS. Hires and 90-day retention are far too rare
and slow to drive the bandit at ~1,000 candidates; they are attributed per
variant in variant_funnel_report() and used to retire variants that get
replies but never hires.
"""
import logging
import random
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.thunder_email import ThunderEmailMessage, ThunderOutreachVariant
from app.services.thunder_mail.reply_classifier import POSITIVE_INTENTS

logger = logging.getLogger(__name__)

REWARD_WINDOW_DAYS = 14
EXPLORATION_FLOOR = 0.10
MIN_SENDS_FOR_EXPLOITATION = 30
OPT_OUT_RETIRE_MULTIPLIER = 2.0


def variant_stats(db: Session, step_family: str, now: Optional[datetime] = None) -> Dict[int, Dict]:
    """{variant_id: {sent, success, failure, opt_out}} over resolved touches."""
    now = now or datetime.utcnow()
    window = timedelta(days=REWARD_WINDOW_DAYS)
    outs = db.query(ThunderEmailMessage).join(
        ThunderOutreachVariant, ThunderEmailMessage.variant_id == ThunderOutreachVariant.id
    ).filter(
        ThunderOutreachVariant.step == step_family,
        ThunderEmailMessage.direction == "OUT",
        ThunderEmailMessage.status == "SENT",
    ).all()
    credited = {
        row.credited_out_id: row for row in db.query(ThunderEmailMessage).filter(
            ThunderEmailMessage.direction == "IN",
            ThunderEmailMessage.credited_out_id.in_([o.id for o in outs] or [""]),
        )
    }
    stats: Dict[int, Dict] = {}
    for out in outs:
        entry = stats.setdefault(out.variant_id, {"sent": 0, "success": 0, "failure": 0, "opt_out": 0})
        entry["sent"] += 1
        reply = credited.get(out.id)
        if reply is not None and reply.received_at and reply.received_at - out.sent_at <= window:
            if reply.intent in POSITIVE_INTENTS:
                entry["success"] += 1
            else:
                entry["failure"] += 1
            if reply.intent == "UNSUBSCRIBE":
                entry["opt_out"] += 1
        elif out.sent_at and now - out.sent_at > window:
            entry["failure"] += 1
    return stats


def _retire_opt_out_outliers(db: Session, variants: List[ThunderOutreachVariant], stats: Dict[int, Dict]) -> None:
    rates = {v.id: stats[v.id]["opt_out"] / stats[v.id]["sent"]
             for v in variants if stats.get(v.id, {}).get("sent", 0) >= MIN_SENDS_FOR_EXPLOITATION}
    if len(rates) < 2:
        return
    median = statistics.median(rates.values())
    for variant in variants:
        rate = rates.get(variant.id)
        if rate is not None and median > 0 and rate > OPT_OUT_RETIRE_MULTIPLIER * median:
            variant.active = False
            variant.retired_reason = f"opt-out rate {rate:.1%} > {OPT_OUT_RETIRE_MULTIPLIER}x step median {median:.1%}"
            db.add(variant)
            logger.warning(f"[ThunderAB] Retired variant {variant.key}: {variant.retired_reason}")


def choose_variant(db: Session, step_family: str, *, rng: Optional[random.Random] = None,
                   job_available: bool = True) -> ThunderOutreachVariant:
    rng = rng or random.Random()
    query = db.query(ThunderOutreachVariant).filter(
        ThunderOutreachVariant.step == step_family, ThunderOutreachVariant.active.is_(True),
    )
    if not job_available:
        query = query.filter(ThunderOutreachVariant.requires_job.is_(False))
    variants = query.order_by(ThunderOutreachVariant.id).all()
    if not variants:
        raise ValueError(f"No active approved variant for step {step_family}")
    if len(variants) == 1:
        return variants[0]

    stats = variant_stats(db, step_family)
    _retire_opt_out_outliers(db, variants, stats)
    variants = [v for v in variants if v.active] or variants

    under_sampled = [v for v in variants if stats.get(v.id, {}).get("sent", 0) < MIN_SENDS_FOR_EXPLOITATION]
    rng.shuffle(under_sampled)
    for variant in under_sampled:
        if rng.random() < EXPLORATION_FLOOR:
            return variant

    def draw(variant):
        entry = stats.get(variant.id, {"success": 0, "failure": 0})
        return rng.betavariate(1 + entry["success"], 1 + entry["failure"])

    return max(variants, key=draw)


def variant_funnel_report(db: Session) -> List[Dict]:
    """Per variant: sends, positive replies, and the downstream hire/retain funnel of
    the candidates it touched (interview, accepted offer, joined, retained 90 days)."""
    from app.models.employee import Employee
    from app.models.offer import Offer
    from app.models.user import Interview

    rows = []
    for variant in db.query(ThunderOutreachVariant).order_by(ThunderOutreachVariant.step, ThunderOutreachVariant.key):
        candidate_ids = [cid for (cid,) in db.query(ThunderEmailMessage.candidate_id).filter(
            ThunderEmailMessage.variant_id == variant.id, ThunderEmailMessage.status == "SENT",
        ).distinct()]
        stats = variant_stats(db, variant.step).get(variant.id, {"sent": 0, "success": 0})
        if not candidate_ids:
            rows.append({"variant": variant.key, "step": variant.step, "sent": 0})
            continue
        today = datetime.utcnow().date()
        joined = [e for e in db.query(Employee).filter(Employee.candidate_id.in_(candidate_ids))
                  if e.joining_date and e.joining_date <= today]
        retained = [e for e in joined if (today - e.joining_date).days >= 90
                    and (e.exit_date is None or (e.exit_date - e.joining_date).days > 90)]
        rows.append({
            "variant": variant.key, "step": variant.step, "active": variant.active,
            "sent": stats["sent"], "positive_replies": stats["success"],
            "interviewed": db.query(Interview.candidate_id).filter(
                Interview.candidate_id.in_(candidate_ids)).distinct().count(),
            "offers_accepted": db.query(Offer.candidate_id).filter(
                Offer.candidate_id.in_(candidate_ids), Offer.status == "ACCEPTED").distinct().count(),
            "joined": len(joined),
            "retained_90d": len(retained),
        })
    return rows

