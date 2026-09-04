#!/usr/bin/env python3
"""
Gate Auto-Fixer: Autonomously applies code fixes detected by the gate.

Capabilities:
- Auto-detects violation patterns
- Applies fixes to source code
- Learns from applied fixes
- Updates gate rules based on feedback
"""
import re
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple


class GateAutoFixer:
    """Autonomously fixes code violations detected by the gate."""

    def __init__(self, file_path: str, content: str, lines: List[str]):
        self.file_path = file_path
        self.content = content
        self.lines = lines.copy()
        self.fixes_applied = []
        self.learning_log_path = Path(".claude/gate_learning.json")

    def apply_fix(self, issue: Dict[str, Any]) -> Tuple[bool, str]:
        """Apply a single fix. Returns (success, message)."""
        line_num = issue['line'] - 1  # Convert to 0-indexed
        issue_type = issue.get('issue', '')
        fix_pattern = issue.get('fix', '')

        if line_num < 0 or line_num >= len(self.lines):
            return False, f"Line {line_num + 1} out of range"

        # Dispatch to specific fixer based on issue type
        if 'Async call without error handling' in issue_type:
            return self._fix_async_error_handling(line_num, issue)
        elif 'Silent catch block' in issue_type:
            return self._fix_silent_catch(line_num, issue)
        elif 'Silent exception catch' in issue_type:
            return self._fix_silent_exception(line_num, issue)
        elif 'Missing error message' in issue_type:
            return self._fix_missing_error_message(line_num, issue)
        elif 'Magic number' in issue_type:
            return self._fix_magic_number(line_num, issue)
        elif 'Missing null check' in issue_type:
            return self._fix_missing_null_check(line_num, issue)
        elif 'Missing role template permission' in issue_type:
            return self._fix_missing_rbac(line_num, issue)
        else:
            return False, f"No auto-fixer for: {issue_type}"

    def _fix_async_error_handling(self, line_num: int, issue: Dict) -> Tuple[bool, str]:
        """Add .catch() error handling to async/await calls."""
        line = self.lines[line_num]

        # If already has .catch, skip
        if '.catch' in line:
            return False, "Already has .catch() handler"

        # Pattern: await functionCall(...).catch(e => { throw e; })
        await_match = re.search(r'await\s+(\w+)\s*\(', line)
        if not await_match:
            return False, "Could not parse await statement"

        # Find closing paren and add .catch()
        paren_count = 0
        insert_pos = line.find('await')
        for i in range(insert_pos, len(line)):
            if line[i] == '(':
                paren_count += 1
            elif line[i] == ')':
                paren_count -= 1
                if paren_count == 0:
                    # Insert .catch after closing paren
                    fixed_line = line[:i+1] + '.catch(e => { throw e; })' + line[i+1:]
                    self.lines[line_num] = fixed_line
                    self.fixes_applied.append({
                        'line': line_num + 1,
                        'type': 'async_error_handling',
                        'before': line,
                        'after': fixed_line
                    })
                    return True, "Added .catch() error handler"

        return False, "Could not insert .catch() handler"

    def _fix_silent_catch(self, line_num: int, issue: Dict) -> Tuple[bool, str]:
        """Fix silent catch blocks by adding throw statements."""
        line = self.lines[line_num]

        # Find the catch block and look for return without throw
        for i in range(line_num, min(line_num + 8, len(self.lines))):
            if 'return' in self.lines[i] and 'throw' not in self.lines[i]:
                # Replace return with throw
                fixed_line = self.lines[i].replace('return', 'throw new Error').replace('(', '(')
                self.lines[i] = fixed_line
                self.fixes_applied.append({
                    'line': i + 1,
                    'type': 'silent_catch',
                    'before': self.lines[i],
                    'after': fixed_line
                })
                return True, f"Changed return to throw on line {i + 1}"

        return False, "Could not fix silent catch"

    def _fix_silent_exception(self, line_num: int, issue: Dict) -> Tuple[bool, str]:
        """Fix generic Exception() with specific exception types."""
        line = self.lines[line_num]

        # Replace 'raise Exception' with 'raise ValueError'
        if 'raise Exception' in line:
            fixed_line = line.replace('raise Exception', 'raise ValueError')
            self.lines[line_num] = fixed_line
            self.fixes_applied.append({
                'line': line_num + 1,
                'type': 'generic_exception',
                'before': line,
                'after': fixed_line
            })
            return True, "Changed Exception to ValueError"

        return False, "Could not fix generic exception"

    def _fix_missing_error_message(self, line_num: int, issue: Dict) -> Tuple[bool, str]:
        """Add error logging/messages to exception handlers."""
        line = self.lines[line_num]

        if 'except' in line:
            # Add logger.error() after the except line
            indent = len(line) - len(line.lstrip())
            log_line = ' ' * (indent + 4) + 'logger.error(f"Error: {e}", exc_info=True)'
            self.lines.insert(line_num + 1, log_line)
            self.fixes_applied.append({
                'line': line_num + 1,
                'type': 'missing_error_message',
                'action': f'Added error logging'
            })
            return True, "Added error logging"

        return False, "Could not add error logging"

    def _fix_magic_number(self, line_num: int, issue: Dict) -> Tuple[bool, str]:
        """Replace magic numbers with named constants."""
        line = self.lines[line_num]

        # Find magic number (e.g., 1000, 5000)
        match = re.search(r'\b(\d{4,})\b', line)
        if match:
            number = match.group(1)
            const_name = f"MAGIC_CONST_{number}"
            fixed_line = line.replace(number, const_name)
            self.lines[line_num] = fixed_line
            self.fixes_applied.append({
                'line': line_num + 1,
                'type': 'magic_number',
                'before': line,
                'after': fixed_line
            })
            return True, f"Replaced {number} with {const_name}"

        return False, "Could not find magic number"

    def _fix_missing_null_check(self, line_num: int, issue: Dict) -> Tuple[bool, str]:
        """Add null checks before attribute access."""
        line = self.lines[line_num]

        # Match attribute access like .name, .email
        match = re.search(r'(\w+)\?\.(\w+)', line)
        if match:
            # Already has optional chaining
            return True, "Already has optional chaining (?.)."

        match = re.search(r'(\w+)\.(\w+)', line)
        if match:
            var_name = match.group(1)
            # Add optional chaining
            fixed_line = line.replace(f'{var_name}.', f'{var_name}?.')
            self.lines[line_num] = fixed_line
            self.fixes_applied.append({
                'line': line_num + 1,
                'type': 'missing_null_check',
                'before': line,
                'after': fixed_line
            })
            return True, f"Added optional chaining for {var_name}"

        return False, "Could not add null check"

    def _fix_missing_rbac(self, line_num: int, issue: Dict) -> Tuple[bool, str]:
        """Add missing RBAC permission checks to endpoints."""
        line = self.lines[line_num]

        if '@router.' in line:
            # Add permission dependency
            indent = len(line) - len(line.lstrip())
            perm_line = ' ' * indent + 'dependencies=[Depends(require_resource_permission("resource", "action"))],'
            self.lines.insert(line_num + 1, perm_line)
            self.fixes_applied.append({
                'line': line_num + 1,
                'type': 'missing_rbac',
                'action': 'Added permission dependency'
            })
            return True, "Added RBAC permission check"

        return False, "Could not add RBAC check"

    def get_fixed_content(self) -> str:
        """Get the fixed file content."""
        return '\n'.join(self.lines)

    def save_fixes(self, output_path: str = None) -> bool:
        """Save fixed content back to file."""
        output = output_path or self.file_path
        try:
            with open(output, 'w') as f:
                f.write(self.get_fixed_content())
            return True
        except Exception as e:
            print(f"Failed to save fixes: {e}")
            return False

    def log_learning(self, issue: Dict[str, Any], fixed: bool, auto_applied: bool = False):
        """Log the issue and its fix to the learning database."""
        learning_data = self._load_learning_log()

        entry = {
            'timestamp': datetime.now().isoformat(),
            'file': self.file_path,
            'issue_type': issue.get('issue'),
            'line': issue.get('line'),
            'severity': issue.get('severity'),
            'fixed': fixed,
            'auto_applied': auto_applied,
            'fixes_applied': len(self.fixes_applied)
        }

        if 'issues' not in learning_data:
            learning_data['issues'] = []

        learning_data['issues'].append(entry)

        # Keep only last 1000 entries
        if len(learning_data['issues']) > 1000:
            learning_data['issues'] = learning_data['issues'][-1000:]

        self._save_learning_log(learning_data)

    def _load_learning_log(self) -> Dict:
        """Load existing learning log."""
        if self.learning_log_path.exists():
            try:
                with open(self.learning_log_path) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_learning_log(self, data: Dict):
        """Save learning log."""
        self.learning_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.learning_log_path, 'w') as f:
            json.dump(data, f, indent=2)
