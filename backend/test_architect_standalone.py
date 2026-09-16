#!/usr/bin/env python
"""
Standalone test of Autonomous Architect (no pytest required)
Tests core functionality without external dependencies
"""

import asyncio
import tempfile
from pathlib import Path
import sys
import traceback

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.autonomous_architect import (
    CodeAnalyzer,
    FindingsGenerator,
    AutonomousArchitectService,
    Finding,
    SeverityLevel,
    IssueType,
)


async def test_analyzer_basic():
    """Test basic analyzer functionality"""
    print("[TEST] Analyzer basic functionality...")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        backend = repo / "backend" / "app"
        backend.mkdir(parents=True)

        # Create test files
        (backend / "test1.py").write_text("def foo(): return []")
        (backend / "test2.py").write_text("try: pass\nexcept: return []")

        analyzer = CodeAnalyzer(repo)
        findings = await analyzer.analyze_all()

        assert isinstance(findings, list)
        print(f"  ✓ Found {len(findings)} issues")
        return True


async def test_analyzer_empty_repo():
    """Test analyzer with empty repo"""
    print("[TEST] Analyzer with empty repo...")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)

        analyzer = CodeAnalyzer(repo)
        findings = await analyzer.analyze_all()

        assert isinstance(findings, list)
        print(f"  ✓ Handled empty repo gracefully")
        return True


async def test_analyzer_bad_python():
    """Test analyzer with syntax errors"""
    print("[TEST] Analyzer with syntax errors...")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        backend = repo / "backend" / "app"
        backend.mkdir(parents=True)

        # Create file with syntax error
        (backend / "bad.py").write_text("def foo(: pass")

        analyzer = CodeAnalyzer(repo)
        findings = await analyzer.analyze_all()

        assert isinstance(findings, list)
        print(f"  ✓ Handled syntax errors gracefully")
        return True


async def test_analyzer_large_file():
    """Test analyzer skips very large files"""
    print("[TEST] Analyzer with large files...")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        backend = repo / "backend" / "app"
        backend.mkdir(parents=True)

        # Create "large" file
        (backend / "large.py").write_text("x" * (CodeAnalyzer.MAX_FILE_SIZE + 1))

        analyzer = CodeAnalyzer(repo)
        findings = await analyzer.analyze_all()

        assert isinstance(findings, list)
        print(f"  ✓ Skipped large files without crashing")
        return True


async def test_findings_generator():
    """Test findings generator"""
    print("[TEST] Findings generator...")

    findings = [
        Finding(
            severity=SeverityLevel.CRITICAL_BLOCKING,
            issue_type=IssueType.SILENT_EXCEPTION,
            title="Test issue",
            file="test.py",
            line=42
        )
    ]

    # Test categorization
    categorized = FindingsGenerator.categorize_findings(findings)
    assert isinstance(categorized, dict)

    # Test spec generation
    spec = FindingsGenerator.generate_sdlc_spec(findings)
    assert isinstance(spec, dict)
    assert "critical_issues" in spec

    # Test report generation
    report = FindingsGenerator.generate_report(findings)
    assert isinstance(report, str)
    assert "CRITICAL_BLOCKING" in report or "Test issue" in report

    print(f"  ✓ Findings generator working correctly")
    return True


async def test_service_lifecycle():
    """Test service start/stop lifecycle"""
    print("[TEST] Service lifecycle...")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service = AutonomousArchitectService(repo)

        # Start
        assert service.running == False
        await service.start()
        assert service.running == True

        # Get findings
        findings = await service.get_latest_findings()
        assert isinstance(findings, list)

        # Stop
        await asyncio.sleep(0.1)
        await service.stop()
        assert service.running == False

        print(f"  ✓ Service lifecycle working correctly")
        return True


async def test_service_with_code():
    """Test service with actual code to analyze"""
    print("[TEST] Service analyzing actual code...")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        backend = repo / "backend" / "app"
        backend.mkdir(parents=True)

        # Create files with various issues
        (backend / "silent_catch.py").write_text("""
def process():
    try:
        risky_operation()
    except:
        return []  # Silent failure!
""")

        (backend / "hardcoded.py").write_text("""
QUEUE_TYPES = ['THUNDER', 'EMAIL']  # Should be from API
ROLES = ['Admin', 'User']  # Should be from database
""")

        (backend / "good_code.py").write_text("""
def safe_process():
    try:
        safe_operation()
    except Exception as e:
        raise ValueError(f"Failed: {e}")
""")

        service = AutonomousArchitectService(repo)
        await service.start()

        # Wait for first analysis
        await asyncio.sleep(1)

        findings = await service.get_latest_findings()

        await service.stop()

        print(f"  ✓ Service found {len(findings)} issues in sample code")
        return True


async def test_edge_cases():
    """Test edge cases that could crash"""
    print("[TEST] Edge cases...")

    test_cases = [
        (None, "None repo"),
        (Path("/nonexistent/path"), "Nonexistent path"),
    ]

    for repo, desc in test_cases:
        try:
            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()
            assert isinstance(findings, list)
            print(f"  ✓ Handled {desc}")
        except Exception as e:
            print(f"  ✗ Failed on {desc}: {e}")
            return False

    return True


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("AUTONOMOUS ARCHITECT - STANDALONE TEST SUITE")
    print("="*70 + "\n")

    tests = [
        test_analyzer_basic,
        test_analyzer_empty_repo,
        test_analyzer_bad_python,
        test_analyzer_large_file,
        test_findings_generator,
        test_service_lifecycle,
        test_service_with_code,
        test_edge_cases,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
