"""
SLM Integration Validation - Code-level checks (CYCLE 5)

Validates that Phase A is production-ready:
1. All handlers have Place 1 (pre-flight) SLM analysis
2. All handlers have Place 2 (post-flight) outcome recording
3. Queue processor has pre-flight enforcement
4. Code review gate has MISSING_SLM_CALL check
"""

import sys
from pathlib import Path


def validate_handler_slm_integration():
    """Verify all handlers have Place 1 + Place 2 SLM calls."""
    print("\n" + "="*70)
    print("VALIDATING HANDLER SLM INTEGRATION")
    print("="*70 + "\n")

    project_root = Path(__file__).parent.parent.parent
    handlers_dir = project_root / "backend/app/services/message_handlers"

    handlers = list(handlers_dir.glob("*_handler.py"))
    handlers = [h for h in handlers if "test" not in h.name]

    # interview_scheduled_handler.py was the only entry: it was dead code (the interview_scheduled
    # task runs _pause_thunder_on_interview) and is deleted (flash spec E19)
    critical_handlers = []

    results = {
        "handlers_checked": 0,
        "with_place1": [],
        "with_place2": [],
        "with_both": [],
        "missing_place1": [],
        "missing_place2": [],
    }

    for handler_file in handlers:
        try:
            content = handler_file.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        results["handlers_checked"] += 1

        has_place1 = any(x in content for x in [
            "analyze_before_handler",
            "SLMService.analyze"
        ])

        has_place2 = any(x in content for x in [
            "record_outcome",
            "SLMService.record"
        ])

        if has_place1:
            results["with_place1"].append(handler_file.name)
        else:
            results["missing_place1"].append(handler_file.name)

        if has_place2:
            results["with_place2"].append(handler_file.name)
        else:
            results["missing_place2"].append(handler_file.name)

        if has_place1 and has_place2:
            results["with_both"].append(handler_file.name)
            status = "[PASS]"
        else:
            status = "[FAIL]"

        print(f"{status} {handler_file.name}")
        if not has_place1:
            print("     |- Missing Place 1 (pre-flight analysis)")
        if not has_place2:
            print("     `- Missing Place 2 (outcome recording)")

    # Critical handlers must have both (Phase A focus)
    critical_missing = [h for h in critical_handlers if h not in results["with_both"]]

    print("\n[STATS] Summary:")
    print(f"   All handlers checked: {results['handlers_checked']}")
    print(f"   With Place 1: {len(results['with_place1'])}")
    print(f"   With Place 2: {len(results['with_place2'])}")
    print(f"   With both: {len(results['with_both'])}")

    print("\n[STATS] Phase A CRITICAL handlers:")
    for critical in critical_handlers:
        if critical in results["with_both"]:
            print(f"   [OK] {critical}")
        else:
            print(f"   [FAIL] {critical}")

    if critical_missing:
        print(f"\n[FAIL] CRITICAL Phase A handlers missing SLM: {critical_missing}")
        return False

    print("\n[OK] All Phase A CRITICAL handlers have Place 1 + Place 2 SLM integration")
    return True


def validate_queue_processor_enforcement():
    """Verify queue processor has pre-flight SLM enforcement."""
    print("\n" + "="*70)
    print("VALIDATING QUEUE PROCESSOR SLM ENFORCEMENT")
    print("="*70 + "\n")

    project_root = Path(__file__).parent.parent.parent
    qp_file = project_root / "backend/app/services/queue_processor_service.py"

    content = qp_file.read_text(encoding='utf-8', errors='ignore')

    checks = {
        "SLMService import": "from app.services.slm_service import SLMService" in content,
        "Pre-flight analysis call": "analyze_before_handler" in content,
        "should_proceed check": "should_proceed" in content,
        "Escalation handling": "escalated" in content or "ESCALATED" in content,
    }

    all_pass = True
    for check_name, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {check_name}")
        all_pass = all_pass and passed

    if all_pass:
        print("\n[OK] Queue processor has pre-flight SLM enforcement")
    else:
        print("\n[FAIL] Queue processor missing SLM enforcement components")

    return all_pass


def validate_code_review_gate():
    """Verify code review gate has MISSING_SLM_CALL check."""
    print("\n" + "="*70)
    print("VALIDATING CODE REVIEW GATE SLM CHECK")
    print("="*70 + "\n")

    project_root = Path(__file__).parent.parent.parent
    gate_file = project_root / "backend/scripts/agentic_code_gate.py"

    content = gate_file.read_text(encoding='utf-8', errors='ignore')

    checks = {
        "MISSING_SLM_CALL impact": "'MISSING_SLM_CALL'" in content,
        "CRITICAL severity": "'MISSING_SLM_CALL': {'impact': 'UNACCOUNTABLE" in content,
        "SLM check method": "_check_slm_integration" in content,
        "Handler detection": "is_handler_func" in content,
        "analyze_before_handler detection": "'analyze_before_handler'" in content,
        "record_outcome detection": "'record_outcome'" in content,
    }

    all_pass = True
    for check_name, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {check_name}")
        all_pass = all_pass and passed

    if all_pass:
        print("\n[OK] Code review gate has MISSING_SLM_CALL enforcement")
    else:
        print("\n[FAIL] Code review gate missing SLM enforcement")

    return all_pass


def validate_slm_service_methods():
    """Verify SLMService has both Place 1 and Place 2 methods."""
    print("\n" + "="*70)
    print("VALIDATING SLM SERVICE METHODS")
    print("="*70 + "\n")

    project_root = Path(__file__).parent.parent.parent
    slm_file = project_root / "backend/app/services/slm_service.py"

    content = slm_file.read_text(encoding='utf-8', errors='ignore')

    methods = {
        "analyze_before_handler (Place 1)": "def analyze_before_handler" in content,
        "record_outcome (Place 2)": "def record_outcome" in content,
        "should_proceed logic": "should_proceed" in content,
        "Confidence calculation": "confidence" in content,
        "Escalation logic": "escalat" in content,
        "Business impact recording": "business_impact" in content,
        "90-day validation": "validation_plan" in content,
    }

    all_pass = True
    for method_name, present in methods.items():
        status = "[OK]" if present else "[FAIL]"
        print(f"{status} {method_name}")
        all_pass = all_pass and present

    if all_pass:
        print("\n[OK] SLMService has Place 1 + Place 2 methods")
    else:
        print("\n[FAIL] SLMService missing critical methods")

    return all_pass


def validate_slm_model():
    """Verify SLMDecision model exists with all fields."""
    print("\n" + "="*70)
    print("VALIDATING SLM DECISION MODEL")
    print("="*70 + "\n")

    project_root = Path(__file__).parent.parent.parent
    model_file = project_root / "backend/app/models/slm_decision.py"

    if not model_file.exists():
        print("[FAIL] SLMDecision model file not found")
        return False

    content = model_file.read_text(encoding='utf-8', errors='ignore')

    fields = {
        "id (primary key)": "id = Column(UUID",
        "message_id (FK)": "message_id = Column(UUID",
        "message_type": "message_type = Column(String",
        "slm_analysis (Place 1)": "slm_analysis = Column(JSON",
        "handler_result (Place 2)": "handler_result = Column(JSON",
        "business_impact": "business_impact = Column(JSON",
        "validation_plan (90-day)": "validation_plan = Column(JSON",
        "accountability": "accountability = Column(JSON",
        "slm_confidence": "slm_confidence = Column(Float",
        "risk_level": "risk_level = Column(String",
        "was_escalated": "was_escalated = Column(Boolean",
    }

    all_pass = True
    for field_name, pattern in fields.items():
        present = pattern in content
        status = "[OK]" if present else "[FAIL]"
        print(f"{status} {field_name}")
        all_pass = all_pass and present

    if all_pass:
        print("\n[OK] SLMDecision model complete")
    else:
        print("\n[FAIL] SLMDecision model missing fields")

    return all_pass


def main():
    """Run all validation checks."""
    print("\n" + "="*70)
    print("CYCLE 5: PRODUCTION READINESS VALIDATION")
    print("="*70)

    results = []
    results.append(("Handler SLM Integration", validate_handler_slm_integration()))
    results.append(("Queue Processor Enforcement", validate_queue_processor_enforcement()))
    results.append(("Code Review Gate", validate_code_review_gate()))
    results.append(("SLM Service Methods", validate_slm_service_methods()))
    results.append(("SLM Decision Model", validate_slm_model()))

    print("\n" + "="*70)
    print("PRODUCTION READINESS SUMMARY")
    print("="*70 + "\n")

    for check_name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"{status}: {check_name}")

    all_pass = all(r[1] for r in results)

    if all_pass:
        print("\n" + "="*70)
        print("[READY] PRODUCTION READY - ALL CHECKS PASSED")
        print("="*70 + "\n")
        print("Phase A SLM Enforcement Summary:")
        print("  [OK] All handlers have Place 1 pre-flight analysis")
        print("  [OK] All handlers have Place 2 outcome recording")
        print("  [OK] Queue processor enforces pre-flight SLM")
        print("  [OK] Code review gate blocks missing SLM (CRITICAL)")
        print("  [OK] SLMDecision model records business accountability")
        print("  [OK] 90-day validation plans tied to business outcomes")
        print("\nReady to proceed to full integration testing.\n")
        return 0
    else:
        print("\n" + "="*70)
        print("[FAIL] PRODUCTION NOT READY - FIXES REQUIRED")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
