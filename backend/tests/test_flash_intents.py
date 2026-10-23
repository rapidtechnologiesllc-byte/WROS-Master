"""Flash's in-house intent classifier (no external call): realistic staff questions reach the
right lookup. Before 2026-10-14, 7 of these 15 were "can't answer" and 2 went to the wrong one."""
import os

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789abcdef")

from app.services.flash_service import classify_internal_query  # noqa: E402

CASES = [
    ("find me guidewire policycenter developers", "sourcing", "guidewire policycenter developers"),
    ("who can do java spring boot in india", "sourcing", None),
    ("where is Priya Sharma in the process", "candidate_status", "Priya Sharma"),
    ("any update on Rahul?", "candidate_status", "Rahul"),
    ("who is on the bench right now", "bench_availability", ""),
    ("show available QA engineers", "bench_availability", "QA"),
    ("anyone free who knows kafka?", "bench_availability", "kafka"),
    ("what's our margin this month", "finance_pnl", None),
    ("how is AXION doing financially", "finance_pnl", "AXION"),
    ("which invoices are overdue", "ar_aging", None),
    ("what do I need to do today", "my_tasks", None),
    ("did I submit my timesheet", "my_timesheets", None),
    ("create a job for a senior BA in Dallas", "job_create", None),
    ("open a req for 3 guidewire billingcenter devs", "job_create", None),
    ("how many candidates do we have in interview stage", "pipeline_summary", ""),
    ("what's the pipeline for client Acme", "pipeline_summary", "Acme"),
]


@pytest.mark.parametrize("question,intent,query", CASES)
def test_question_reaches_the_right_lookup(question, intent, query):
    result = classify_internal_query(question)
    assert result["intent"] == intent
    if query is not None:
        assert result["query"].lower() == query.lower()
