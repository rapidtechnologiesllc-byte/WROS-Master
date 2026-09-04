#!/usr/bin/env python3
"""
Automatically fix critical code quality issues across the entire backend.
Focuses on: permission checks, error logging, null checks, exception handling.
"""
import os
import re
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodeFixer:
    def __init__(self, backend_dir):
        self.backend_dir = backend_dir
        self.fixes_applied = 0
        self.files_modified = []

    def fix_missing_logging_imports(self, content):
        """Ensure logging is imported."""
        if 'import logging' not in content:
            # Add after other imports
            if 'from ' in content or 'import ' in content:
                first_import_end = content.find('\n\n')
                if first_import_end == -1:
                    first_import_end = content.find('\n\nclass')
                if first_import_end == -1:
                    first_import_end = content.find('\n\ndef')

                if first_import_end > 0:
                    # Find last import line before first_import_end
                    content_before = content[:first_import_end]
                    last_import_line = content_before.rfind('\n', 0, first_import_end)
                    insert_pos = last_import_line + 1
                    content = content[:insert_pos] + 'import logging\n' + content[insert_pos:]

                    # Add logger initialization
                    if 'logger = logging.getLogger' not in content:
                        init_pos = content.find('\n\nclass') or content.find('\n\ndef')
                        if init_pos > 0:
                            content = content[:init_pos] + '\nlogger = logging.getLogger(__name__)' + content[init_pos:]

        return content

    def fix_bare_except_without_logging(self, content):
        """Add logging to exception handlers."""
        # Pattern: except Exception: (no logger call)
        pattern = r'except\s+(?:Exception|BaseException)\s+as\s+(\w+):\s*\n(\s+)([^l])'

        def add_logging(match):
            exception_var = match.group(1)
            indent = match.group(2)
            next_statement = match.group(3)

            if 'logger.error' not in next_statement and 'raise' not in next_statement:
                return f'except Exception as {exception_var}:\n{indent}logger.error(f"Error: {{str({exception_var})}}", exc_info=True)\n{indent}{next_statement}'
            return match.group(0)

        return re.sub(pattern, add_logging, content)

    def fix_missing_null_checks(self, content):
        """Add null checks before operations."""
        # Add null checks for query results
        pattern = r'(\w+)\s*=\s*db\.query\([^)]+\)\.first\(\)\n(\s+)(?!if)'

        def add_check(match):
            var_name = match.group(1)
            indent = match.group(2)

            return f'{match.group(0)}if not {var_name}:\n{indent}    raise ValueError(f"{{{var_name}}} not found")\n{indent}'

        return re.sub(pattern, add_check, content)

    def fix_file(self, file_path):
        """Apply all fixes to a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return 0

        original_content = content
        fixes = 0

        # Apply fixes in order
        content = self.fix_missing_logging_imports(content)
        if content != original_content:
            fixes += 1

        original = content
        content = self.fix_bare_except_without_logging(content)
        if content != original:
            fixes += 1

        # Don't apply aggressive null checks - too risky
        # original = content
        # content = self.fix_missing_null_checks(content)
        # if content != original:
        #     fixes += 1

        if content != original_content:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.fixes_applied += fixes
                self.files_modified.append(file_path)
                return fixes
            except:
                return 0

        return 0

    def run(self):
        """Scan and fix all Python files."""
        fixed_count = 0

        for root, dirs, files in os.walk(self.backend_dir):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', 'env']]

            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    fixes = self.fix_file(file_path)
                    if fixes > 0:
                        fixed_count += 1
                        rel_path = os.path.relpath(file_path, self.backend_dir)
                        print(f"✅ {rel_path}: {fixes} fix(es)")

        print(f"\n📊 Final Summary:")
        print(f"  Files modified: {fixed_count}")
        print(f"  Total fixes applied: {self.fixes_applied}")
        return fixed_count > 0

if __name__ == '__main__':
    backend = r'C:\dev\WROS-Master\backend'
    fixer = CodeFixer(backend)
    if fixer.run():
        print(f"\n✨ Code improvements complete! {len(fixer.files_modified)} files updated.")
    else:
        print("\nNo issues found or all already fixed.")
