"""Candidate replies are read by rules, not by an AI (CEO 2026-11-02: "we shouldnt depend on gemini
to get the answer and save it on candidate record"). Our emails list each missing detail by label;
answers written against those labels are saved without any AI. The AI reader only tries what the
rules could not read, and only when a key is configured; its failure never loses what the rules read."""
import pytest

from app.services.ai_conversation_service import (
    CANDIDATE_CORE_FIELDS, INFO_FORM_FIELDS, _core_value, askable_employment_type, extract_fields_from_reply,
    notice_period_days, parse_labelled_answers,
)

ALL_MISSING = [{"field": f, "label": l, "source": "candidate"} for f, l in CANDIDATE_CORE_FIELDS + INFO_FORM_FIELDS]

REPLY = """Dear HR team,
Please see the details below:

  *   Date of Birth (YYYY-MM-DD) - 1980-08-27
  *   Years of Experience - 22+ years IT; 1 year non-IT
  *   Employment Type you are looking for (full-time or contract) - Full time
  *   Notice Period (in days) - 2/3 weeks
  *   Earliest Available Start Date (YYYY-MM-DD) 2026-12-07
  *   Current Salary (amount, and per hour or per year) - $232,000 per year + (25-30% bonus) + 176 hours PTO
  *   Expected Salary (amount, and per hour or per year) - Industry Standard for my experience
  *   Marital Status - Married
  *   Nationality - U.S. Citizen
  *   Permanent Address (City, State, Country only -- no street address needed) Naperville, Illinois, USA

Best Regards,
Sent from my iPhone

On Oct 30, 2026, at 3:37 PM, Helpdesk_HRMS <helpdesk_hrms@blitzenx.com> wrote:

  *   Date of Birth (YYYY-MM-DD)
  *   Years of Experience
"""


def test_labelled_reply_is_read_without_ai():
    assert parse_labelled_answers(REPLY, ALL_MISSING) == {
        "candidateDateOfBirth": "1980-08-27",
        "candidateExperience": "22",
        "employment_type": "Full time",
        "candidate_notice_period": "2/3 weeks",
        "candidateJoiningDate": "2026-12-07",
        "candidateCurrentSalary": "232000",
        "candidateCurrentSalaryType": "$/Year",
        "candidateExpectedSalary": "Industry Standard for my experience",
        "marital_status": "Married",
        "nationality": "U.S. Citizen",
        "permanent_address": "Naperville, Illinois, USA",
    }


def test_answer_on_the_next_line_and_colon_separators():
    reply = "Notice Period:\n60 days\nCurrent Salary: 85k per hour\nMarital Status: unmarried\nGender - F"
    found = parse_labelled_answers(reply, ALL_MISSING)
    assert found["candidate_notice_period"] == "60 days"
    assert found["candidateCurrentSalary"] == "85000"
    assert found["candidateCurrentSalaryType"] == "$/Hour"
    assert found["marital_status"] == "Single"
    assert found["candidateGender"] == "Female"


def test_label_without_an_answer_is_not_read():
    reply = "Date of Birth (YYYY-MM-DD)\nYears of Experience - NA"
    assert parse_labelled_answers(reply, ALL_MISSING) == {}


@pytest.mark.parametrize("written,days", [
    ("30", 30), ("45 days", 45), ("2 months", 60), ("2/3 weeks", 21), ("2-3 weeks", 21),
    ("Immediately", 0), ("serving notice", 0), ("soon", None),
])
def test_notice_period_days(written, days):
    assert notice_period_days(written) == days


@pytest.mark.parametrize("written,kind", [
    ("Full time", "FULLTIME"), ("full-time", "FULLTIME"), ("Permanent", "FULLTIME"), ("W2", "FULLTIME"),
    ("Contract", "CONTRACT"), ("contract to hire", "CONTRACT"), ("C2C", None), ("contract (C2C)", None),
    ("1099", None), ("whatever", None),
])
def test_employment_type(written, kind):
    assert askable_employment_type(written) == kind
    assert _core_value("employment_type", written) == kind


def test_no_ai_key_keeps_rule_answers_and_raises_nothing(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    found = extract_fields_from_reply(REPLY, ALL_MISSING)
    assert found["candidateDateOfBirth"] == "1980-08-27"
    assert "candidateSkills" not in found


def test_ai_only_asked_for_what_rules_missed_and_its_failure_keeps_rule_answers():
    asked = []

    def failing_llm(prompt):
        asked.append(prompt)
        raise RuntimeError("model unavailable")

    found = extract_fields_from_reply(REPLY, ALL_MISSING, llm_call=failing_llm)
    assert found["nationality"] == "U.S. Citizen"
    assert len(asked) == 1
    assert "candidateSkills" in asked[0] and "candidateDateOfBirth" not in asked[0]


def test_ai_failure_with_nothing_read_by_rules_is_raised():
    def failing_llm(prompt):
        raise RuntimeError("model unavailable")

    with pytest.raises(RuntimeError):
        extract_fields_from_reply("I am interested, call me.", ALL_MISSING, llm_call=failing_llm)
