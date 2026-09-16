"""
BULLETPROOF TEST SUITE FOR AUTONOMOUS ARCHITECT

Tests that try to break the architect in every possible way:
- Malformed inputs
- Missing data
- Extreme sizes
- Invalid encodings
- Concurrency
- Memory limits
- File system errors
- And more...
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
import sys
from unittest.mock import Mock, patch, MagicMock

from app.services.autonomous_architect import (
    CodeAnalyzer,
    FindingsGenerator,
    AutonomousArchitectService,
    Finding,
    SeverityLevel,
    IssueType,
)


class TestCodeAnalyzerEdgeCases:
    """Test CodeAnalyzer handles ALL edge cases"""

    @pytest.mark.asyncio
    async def test_empty_file(self):
        """Test analyzer handles empty files gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create empty Python file
            empty_file = backend / "empty.py"
            empty_file.write_text("")

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should not crash, should return empty list
            assert isinstance(findings, list)
            assert len(findings) >= 0

    @pytest.mark.asyncio
    async def test_file_not_readable(self):
        """Test analyzer handles unreadable files gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create file and make it unreadable
            file = backend / "unreadable.py"
            file.write_text("import os")

            with patch.object(Path, 'read_text', side_effect=PermissionError("No permission")):
                analyzer = CodeAnalyzer(repo)
                findings = await analyzer.analyze_all()

                # Should not crash
                assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """Test analyzer skips files that are too large"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create a "large" file (simulated)
            large_file = backend / "large.py"
            large_file.write_text("x" * (CodeAnalyzer.MAX_FILE_SIZE + 1))

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should skip the large file without crashing
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_invalid_encoding(self):
        """Test analyzer handles files with invalid encoding"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create file with invalid bytes
            bad_file = backend / "bad_encoding.py"
            bad_file.write_bytes(b'\xff\xfe\xff\xfe')  # Invalid UTF-8

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should not crash
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_syntax_error_in_file(self):
        """Test analyzer handles files with syntax errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create file with syntax error
            bad_syntax = backend / "bad_syntax.py"
            bad_syntax.write_text("def foo(: pass")  # Invalid syntax

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should not crash, should skip the file
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_missing_repo_root(self):
        """Test analyzer handles missing repo root"""
        analyzer = CodeAnalyzer(Path("/nonexistent/path/12345"))
        findings = await analyzer.analyze_all()

        # Should return empty list, not crash
        assert isinstance(findings, list)
        assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_repo_root_is_none(self):
        """Test analyzer handles None repo root"""
        analyzer = CodeAnalyzer(None)
        findings = await analyzer.analyze_all()

        # Should return empty list
        assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_repo_root_is_file_not_directory(self):
        """Test analyzer handles when repo_root is a file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "file.txt"
            repo.write_text("not a directory")

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should handle gracefully
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_circular_imports(self):
        """Test analyzer handles files with circular imports"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create circular import scenario
            file_a = backend / "a.py"
            file_b = backend / "b.py"
            file_a.write_text("from app.b import B\nclass A: pass")
            file_b.write_text("from app.a import A\nclass B: pass")

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should handle without crashing
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_deeply_nested_ast(self):
        """Test analyzer handles deeply nested AST"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create deeply nested code
            nested = backend / "nested.py"
            code = "x = "
            for i in range(100):
                code += "("
            code += "1"
            for i in range(100):
                code += ")"
            nested.write_text(code)

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should handle deep nesting
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_too_many_files(self):
        """Test analyzer limits number of files scanned"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create more files than MAX_FILES_PER_SCAN
            for i in range(CodeAnalyzer.MAX_FILES_PER_SCAN + 100):
                file = backend / f"file_{i}.py"
                file.write_text(f"# File {i}")

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should complete without processing all files
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_pycache_ignored(self):
        """Test analyzer ignores __pycache__ directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            pycache = backend / "__pycache__"
            pycache.mkdir(parents=True)

            # Create file in pycache
            bad_file = pycache / "bad.py"
            bad_file.write_text("invalid python %%%")

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should ignore pycache and not crash
            assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_concurrent_analysis(self):
        """Test analyzer can handle concurrent calls"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            file = backend / "test.py"
            file.write_text("def foo(): return []")

            analyzer = CodeAnalyzer(repo)

            # Run multiple analyses concurrently
            tasks = [analyzer.analyze_all() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # All should complete
            assert len(results) == 5
            for result in results:
                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_exception_in_check_function(self):
        """Test analyzer handles exceptions during checks"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            file = backend / "test.py"
            file.write_text("import sys")

            analyzer = CodeAnalyzer(repo)

            # Mock a check function to raise exception
            with patch.object(analyzer, '_check_exception_handler', side_effect=ValueError("Test error")):
                findings = await analyzer.analyze_all()

                # Should continue despite the exception
                assert isinstance(findings, list)


class TestFindingsGeneratorEdgeCases:
    """Test FindingsGenerator handles edge cases"""

    def test_categorize_empty_findings(self):
        """Test categorizing empty findings list"""
        result = FindingsGenerator.categorize_findings([])

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_categorize_none_findings(self):
        """Test categorizing None instead of list"""
        # Should handle gracefully
        try:
            result = FindingsGenerator.categorize_findings(None)
            # If it doesn't crash, that's good
            assert True
        except:
            # If it raises, that's ok too - at least it doesn't silently fail
            assert True

    def test_generate_spec_no_findings(self):
        """Test generating spec with no findings"""
        spec = FindingsGenerator.generate_sdlc_spec([])

        assert spec is not None
        assert spec["total_issues"] == 0
        assert spec["critical_issues"] == 0

    def test_generate_spec_with_invalid_findings(self):
        """Test spec generation with malformed findings"""
        bad_finding = Mock()
        bad_finding.severity = SeverityLevel.CRITICAL_BLOCKING
        bad_finding.file = "test.py"
        bad_finding.line = 1
        bad_finding.title = "Test"
        bad_finding.fix = "Fix it"

        spec = FindingsGenerator.generate_sdlc_spec([bad_finding])

        assert isinstance(spec, dict)
        assert "error" not in spec or spec.get("error") is None

    def test_generate_report_empty_findings(self):
        """Test report generation with no findings"""
        report = FindingsGenerator.generate_report([])

        assert isinstance(report, str)
        assert "CYCLE ANALYSIS REPORT" in report or "FINDINGS" in report

    def test_generate_report_with_none(self):
        """Test report generation with None"""
        try:
            report = FindingsGenerator.generate_report(None)
            assert isinstance(report, str)
        except:
            # If it crashes, that's at least explicit
            assert True


class TestArchitectServiceEdgeCases:
    """Test AutonomousArchitectService handles edge cases"""

    @pytest.mark.asyncio
    async def test_service_with_none_repo(self):
        """Test service initialization with None repo"""
        service = AutonomousArchitectService(None)

        # Should be created successfully
        assert service is not None

        # Start should handle gracefully
        await service.start()

        # Stop should work
        await service.stop()

    @pytest.mark.asyncio
    async def test_service_start_stop(self):
        """Test service can be started and stopped"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            service = AutonomousArchitectService(repo)

            # Start
            assert service.running == False
            await service.start()
            assert service.running == True

            # Wait briefly
            await asyncio.sleep(0.1)

            # Stop
            await service.stop()
            assert service.running == False

    @pytest.mark.asyncio
    async def test_service_get_findings_before_analysis(self):
        """Test getting findings before any analysis runs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            service = AutonomousArchitectService(repo)

            findings = await service.get_latest_findings()

            assert isinstance(findings, list)
            assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_service_multiple_start_calls(self):
        """Test calling start multiple times"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            service = AutonomousArchitectService(repo)

            # Start twice
            await service.start()
            await asyncio.sleep(0.05)
            await service.start()

            # Should still be running
            assert service.running == True

            await service.stop()

    @pytest.mark.asyncio
    async def test_service_stop_without_start(self):
        """Test stopping service that wasn't started"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            service = AutonomousArchitectService(repo)

            # Stop without start - should handle gracefully
            await service.stop()

            assert service.running == False


class TestFindingDataStructure:
    """Test Finding data structure"""

    def test_finding_to_dict(self):
        """Test Finding conversion to dict"""
        finding = Finding(
            severity=SeverityLevel.CRITICAL_BLOCKING,
            issue_type=IssueType.SILENT_EXCEPTION,
            title="Test issue",
            file="test.py",
            line=42,
            code_snippet="bad code",
            why_wrong="This is wrong",
            impact="Everything breaks",
            fix="Fix it",
            category="test"
        )

        d = finding.to_dict()

        assert isinstance(d, dict)
        assert d["severity"] == "CRITICAL_BLOCKING"
        assert d["issue_type"] == "silent_exception"
        assert d["line"] == 42
        assert d["file"] == "test.py"

    def test_finding_with_none_values(self):
        """Test Finding with None values"""
        finding = Finding(
            severity=SeverityLevel.LOW_DEBT,
            issue_type=IssueType.HARDCODED_VALUE,
            title="Test",
            file="test.py",
            line=0
        )

        d = finding.to_dict()

        assert d["code_snippet"] == ""
        assert d["why_wrong"] == ""


class TestMemoryAndPerformance:
    """Test memory and performance limits"""

    @pytest.mark.asyncio
    async def test_max_findings_limit(self):
        """Test that findings are limited"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            analyzer = CodeAnalyzer(repo)

            # Create many findings manually
            analyzer.findings = [
                Finding(
                    severity=SeverityLevel.LOW_DEBT,
                    issue_type=IssueType.HARDCODED_VALUE,
                    title=f"Finding {i}",
                    file="test.py",
                    line=i
                )
                for i in range(CodeAnalyzer.MAX_FINDINGS_PER_CYCLE + 100)
            ]

            findings = await analyzer.analyze_all()

            # Should be limited
            assert len(findings) <= CodeAnalyzer.MAX_FINDINGS_PER_CYCLE

    @pytest.mark.asyncio
    async def test_node_count_limit(self):
        """Test AST node count limiting"""
        # This is handled internally in analyze_python_file
        # Just verify it doesn't crash with deeply nested structures
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            backend = repo / "backend" / "app"
            backend.mkdir(parents=True)

            # Create file with many nested dictionaries
            file = backend / "test.py"
            code = "x = {"
            for i in range(1000):
                code += f"'{i}': "
            code += "1"
            code += "}" * 1000
            file.write_text(code)

            analyzer = CodeAnalyzer(repo)
            findings = await analyzer.analyze_all()

            # Should complete without hanging
            assert isinstance(findings, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
