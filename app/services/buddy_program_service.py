"""
S-364/HRMS-0520 -- 30-Day Buddy Program: 35-KPI Framework & Tracking.

KPI_DEFINITIONS is fixed platform config (BU-Head-approved, never
recruiter-adjustable per the story's own Not-In-Scope section) -- a
Python constant, not an app-editable table.

"Buddy Engineer Cannot Score Their Own Employee" (the BR's title) is
clearer than its own literal field spec ("buddy_engineer_user_id cannot
match scored_by on any BUDDY KPI row"), which read literally would
forbid the buddy from ever submitting the BUDDY-category scores that
are explicitly their job to submit -- self-contradictory as written.
This module follows the BR's own plain-language restatement instead:
"Buddy cannot self-score" -- enforced at record creation, rejecting a
buddy_engineer_user_id that matches the employee's own linked
Users account, not at score-submission time.

Per the story's own Step 3 ("All scores write to buddy_kpi_scores AND
via PerformanceStoreWriter to employee_performance_events with
event_type=BUDDY_KPI"), submit_weekly_scores() now also writes to the
performance store (HRMS-0515, built alongside S-360 in the same
session) -- this wiring was originally deferred when the Buddy Program
was first built, since that table didn't exist yet.
"""
import json
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.buddy_program import BuddyKPIScore, BuddyProgramRecord
from app.models.employee import Employee
from app.services.performance_store_service import write_performance_event

# kpi_number -> (category, name), per S-364's Step 2 seed data.
KPI_DEFINITIONS: Dict[int, tuple] = {
    1: ("HR", "timesheet_punctuality"),
    2: ("HR", "hr_email_response_time"),
    3: ("HR", "onboarding_task_completion"),
    4: ("HR", "it_setup_speed"),
    5: ("HR", "benefits_enrollment"),
    6: ("HR", "policy_signoff_rate"),
    7: ("HR", "background_check_responsiveness"),
    8: ("HR", "contract_execution_speed"),
    9: ("HR", "training_module_completion"),
    10: ("HR", "meeting_attendance"),
    11: ("HR", "calendar_responsiveness"),
    12: ("HR", "written_communication_tone"),
    13: ("BUDDY", "technical_knowledge_depth"),
    14: ("BUDDY", "requirements_understanding"),
    15: ("BUDDY", "adhoc_problem_solving"),
    16: ("BUDDY", "learning_speed"),
    17: ("BUDDY", "work_quality"),
    18: ("BUDDY", "documentation_discipline"),
    19: ("BUDDY", "question_quality"),
    20: ("BUDDY", "mistake_ownership"),
    21: ("BUDDY", "initiative_level"),
    22: ("BUDDY", "team_integration_speed"),
    23: ("BUDDY", "communication_clarity"),
    24: ("BUDDY", "deadline_reliability"),
    25: ("BUDDY", "escalation_judgement"),
    26: ("BUDDY", "pressure_behaviour"),
    27: ("BUDDY", "peer_interaction_quality"),
    28: ("RM", "timesheet_accuracy"),
    29: ("RM", "standup_quality"),
    30: ("RM", "proactive_communication"),
    31: ("RM", "sprint_velocity"),
    32: ("RM", "rm_check_in_responsiveness"),
    33: ("RM", "interview_participation"),
    34: ("RM", "interview_quality_score"),
    35: ("RM", "bench_responsibility"),
}
ALL_KPI_NUMBERS = frozenset(KPI_DEFINITIONS.keys())
CATEGORY_WEIGHTS = {"HR": 0.34, "BUDDY": 0.43, "RM": 0.23}  # Step 3's Week-4 composite weighting
LOW_SCORE_THRESHOLD = 2.0
LOW_SCORE_CONSECUTIVE_WEEKS = 2
TOTAL_WEEKS = 4


class SelfBuddyNotAllowed(Exception):
    """A buddy engineer cannot be assigned to their own buddy program record."""


class InvalidKPISubmission(Exception):
    pass


def create_buddy_program_record(
    db: Session,
    employee: Employee,
    *,
    buddy_engineer_user_id: str,
    program_start_date: date,
    expected_end_date: date,
    tenant_id=None,
) -> BuddyProgramRecord:
    if employee.wros_user_id is not None and buddy_engineer_user_id == employee.wros_user_id:
        raise SelfBuddyNotAllowed(
            f"Employee {employee.id}'s own linked user account cannot be assigned as their buddy engineer."
        )

    record = BuddyProgramRecord(
        tenant_id=tenant_id, employee_id=employee.id, buddy_engineer_user_id=buddy_engineer_user_id,
        program_start_date=program_start_date, expected_end_date=expected_end_date, status="IN_PROGRESS",
    )
    db.add(record)
    db.flush()
    return record


def submit_weekly_scores(
    db: Session,
    record: BuddyProgramRecord,
    *,
    scores: Dict[int, int],
    scored_by: str,
    week_number: int,
    scored_date: Optional[date] = None,
) -> List[BuddyKPIScore]:
    """
    Accepts any subset of the 35 KPI numbers -- a caller submitting only
    their own category's KPIs (HR submits 1-12, Buddy submits 13-27, RM
    submits 28-35) is the normal weekly flow, per Step 3. Completeness
    for the WEEK as a whole (all 35 across all three roles) is checked
    separately by is_week_complete() -- "partial submissions are saved
    as drafts but not counted... until complete" doesn't mean any single
    role's submission is itself incomplete.
    """
    if not (1 <= week_number <= TOTAL_WEEKS):
        raise InvalidKPISubmission(f"week_number must be 1-{TOTAL_WEEKS}, got {week_number}.")

    scored_date = scored_date or date.today()
    rows = []
    for kpi_number, score in scores.items():
        if kpi_number not in KPI_DEFINITIONS:
            raise InvalidKPISubmission(f"Unknown kpi_number {kpi_number}.")
        if not (1 <= score <= 5):
            raise InvalidKPISubmission(f"KPI {kpi_number} score must be 1-5, got {score}.")

        category, name = KPI_DEFINITIONS[kpi_number]
        # Upsert -- resubmitting the same (record, kpi, week) corrects
        # rather than duplicates, since a scorer may revise before the
        # week is marked complete.
        existing = (
            db.query(BuddyKPIScore)
            .filter(
                BuddyKPIScore.buddy_record_id == record.id,
                BuddyKPIScore.kpi_number == kpi_number,
                BuddyKPIScore.week_number == week_number,
            )
            .first()
        )
        if existing:
            existing.score = score
            existing.scored_by = scored_by
            existing.scored_date = scored_date
            db.add(existing)
            rows.append(existing)
        else:
            row = BuddyKPIScore(
                tenant_id=record.tenant_id, buddy_record_id=record.id,
                kpi_number=kpi_number, kpi_category=category, kpi_name=name,
                score=score, scored_by=scored_by, scored_date=scored_date, week_number=week_number,
            )
            db.add(row)
            rows.append(row)

        write_performance_event(
            db, employee_id=record.employee_id, tenant_id=record.tenant_id,
            event_type="BUDDY_KPI",
            event_data={
                "buddy_record_id": record.id, "kpi_number": kpi_number, "kpi_name": name,
                "kpi_category": category, "score": score, "week_number": week_number, "scored_by": scored_by,
            },
        )

    return rows


def is_week_complete(db: Session, record: BuddyProgramRecord, week_number: int) -> bool:
    """BR: all 35 KPIs must be scored for a week to count -- a partial
    submission stays a draft, per the story's own wording."""
    scored_numbers = {
        row.kpi_number for row in
        db.query(BuddyKPIScore)
        .filter(BuddyKPIScore.buddy_record_id == record.id, BuddyKPIScore.week_number == week_number)
        .all()
    }
    return scored_numbers == ALL_KPI_NUMBERS


def check_low_kpi_alert(db: Session, record: BuddyProgramRecord, kpi_number: int, *, through_week: int) -> bool:
    """
    BR: a single KPI averaging below 2.0 for two consecutive weeks
    triggers an RM alert. "Average" here is the single scored value for
    that KPI in a given week (one scorer per KPI per week, per the
    submission model) -- checked across the two most recent weeks up to
    through_week.
    """
    if through_week < LOW_SCORE_CONSECUTIVE_WEEKS:
        return False

    recent_weeks = range(through_week - LOW_SCORE_CONSECUTIVE_WEEKS + 1, through_week + 1)
    scores = (
        db.query(BuddyKPIScore)
        .filter(
            BuddyKPIScore.buddy_record_id == record.id,
            BuddyKPIScore.kpi_number == kpi_number,
            BuddyKPIScore.week_number.in_(list(recent_weeks)),
        )
        .all()
    )
    if len(scores) < LOW_SCORE_CONSECUTIVE_WEEKS:
        return False  # not yet scored for both weeks -- nothing to alert on
    return all(row.score < LOW_SCORE_THRESHOLD for row in scores)


def compute_day30_scorecard(db: Session, record: BuddyProgramRecord) -> dict:
    """
    Step 4 -- per-KPI scores, category averages, weighted overall score,
    trajectory (Week 1 vs Week 4), lowest-scoring KPIs flagged. Only
    complete weeks are included in category/overall averages, per the
    "not counted until complete" rule -- incomplete weeks are reported
    separately, not silently treated as zero or excluded without a trace.
    """
    complete_weeks = [w for w in range(1, TOTAL_WEEKS + 1) if is_week_complete(db, record, w)]
    incomplete_weeks = [w for w in range(1, TOTAL_WEEKS + 1) if w not in complete_weeks]

    all_scores = (
        db.query(BuddyKPIScore)
        .filter(BuddyKPIScore.buddy_record_id == record.id, BuddyKPIScore.week_number.in_(complete_weeks))
        .all()
    ) if complete_weeks else []

    per_kpi_averages: Dict[int, float] = {}
    for kpi_number in ALL_KPI_NUMBERS:
        values = [row.score for row in all_scores if row.kpi_number == kpi_number]
        if values:
            per_kpi_averages[kpi_number] = round(sum(values) / len(values), 2)

    category_averages: Dict[str, Optional[float]] = {}
    for category in ("HR", "BUDDY", "RM"):
        kpi_numbers_in_category = [n for n, (c, _) in KPI_DEFINITIONS.items() if c == category]
        values = [per_kpi_averages[n] for n in kpi_numbers_in_category if n in per_kpi_averages]
        category_averages[category] = round(sum(values) / len(values), 2) if values else None

    weighted_overall = None
    if all(category_averages[c] is not None for c in CATEGORY_WEIGHTS):
        weighted_overall = round(
            sum(category_averages[c] * weight for c, weight in CATEGORY_WEIGHTS.items()), 2,
        )

    trajectory = None
    if 1 in complete_weeks and TOTAL_WEEKS in complete_weeks:
        week1_scores = [row.score for row in all_scores if row.week_number == 1]
        week4_scores = [row.score for row in all_scores if row.week_number == TOTAL_WEEKS]
        week1_avg = sum(week1_scores) / len(week1_scores)
        week4_avg = sum(week4_scores) / len(week4_scores)
        trajectory = "IMPROVING" if week4_avg > week1_avg else ("DECLINING" if week4_avg < week1_avg else "STABLE")

    lowest_scoring = sorted(per_kpi_averages.items(), key=lambda item: item[1])[:5]

    return {
        "buddy_record_id": record.id,
        "complete_weeks": complete_weeks,
        "incomplete_weeks": incomplete_weeks,
        "per_kpi_averages": per_kpi_averages,
        "category_averages": category_averages,
        "weighted_overall_score": weighted_overall,
        "trajectory": trajectory,
        "lowest_scoring_kpis": [
            {"kpi_number": n, "kpi_name": KPI_DEFINITIONS[n][1], "average": avg} for n, avg in lowest_scoring
        ],
    }
