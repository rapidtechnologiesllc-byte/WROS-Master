# Strict Commit Gate Enforcement

## Overview

This document describes the enforcement mechanism that prevents developers from bypassing the code review gate with `--no-verify` and ensures 100% code quality compliance.

## Policy

**GOLDEN RULE:** No --no-verify. Ever.

```
Every commit must:
✅ Pass code review gate (0 errors, 0 warnings)
✅ Include GitHub issue references where applicable
✅ Be signed by the developer
❌ NEVER use --no-verify
❌ NEVER commit with violations (new OR pre-existing)
```

## Enforcement Components

### 1. Pre-Commit Hook (code-review-gate.sh)

**Location:** `.git/hooks/pre-commit`

**Behavior:**
- Runs automatically on every `git commit`
- Analyzes changed files for code violations
- BLOCKS commit if violations found (non-zero exit code)
- Shows detailed violation list with fix suggestions
- Cannot be skipped without `--no-verify` (which is forbidden)

**Example output when violations found:**
```
============================================================
CODE REVIEW GATE - PRE-COMMIT VALIDATION
============================================================

Reviewing: backend/app/api/endpoints/users.py
FAIL CODE REVIEW REJECTED

[CRITICAL #1] Missing null check on line 45
[HIGH #2] Silent exception catch on line 128
...

Fix these issues, stage files, and commit again.
```

### 2. Git Commit Wrapper (git-commit-wrapper.sh)

**Location:** `scripts/git-commit-wrapper.sh`

**Setup:**
```bash
# Add to your ~/.bash_profile or ~/.zshrc:
alias git='~/path/to/WROS-Master/scripts/git-commit-wrapper.sh'
```

**Behavior:**
- Intercepts all `git commit` calls
- Detects `--no-verify` flag in arguments
- If found: BLOCKS commit immediately
- Logs violation attempt to `~/.wros/commit-violations.log`
- Shows message explaining consequences
- Allows all normal commits to proceed

**Example output when --no-verify detected:**
```
╔════════════════════════════════════════════════════════════════╗
║                 🚨 COMMIT GATE BYPASS BLOCKED 🚨              ║
╚════════════════════════════════════════════════════════════════╝

❌ ERROR: --no-verify flag is NOT ALLOWED

This bypass attempt has been LOGGED and will be escalated to team lead.

THE RIGHT WAY:
  $ git diff --cached | ./scripts/code-review-gate.sh
  $ (fix the issues)
  $ git commit -m "fix: ..."  ← No --no-verify
```

### 3. Violation Logging

**Log Location:** `~/.wros/commit-violations.log`

**What gets logged:**
```
[2026-09-03 14:32:15 UTC] ⚠️  BYPASS ATTEMPT BLOCKED
  Developer: John Doe <john@example.com>
  Branch: feature/my-feature
  Command: git commit --no-verify
  Status: REJECTED
  Consequence: Developer flagged, escalation pending
```

**Who sees it:**
- Developer (when running wrapper)
- Team lead (via weekly escalation report)
- CI/CD logs (if git action used)

## Consequences of Violations

### First Violation
- ✅ Commit BLOCKED (doesn't go through)
- ✅ Developer LOGGED
- ✅ 24-hour cooldown activated
- ℹ️ Warning email sent

### Second Violation (within 30 days)
- ✅ All above PLUS
- ✅ PR blocked (cannot merge until reviewed)
- ✅ Escalation to team lead
- ✅ Mandatory code review training required

### Third Violation (within 30 days)
- ✅ All above PLUS
- ✅ Code review assignment (all commits reviewed by 2+ people)
- ✅ Escalation to manager
- ✅ Performance note added to record

## The Correct Workflow

### Scenario 1: Code Passes Gate ✅

```bash
$ git add src/feature.py
$ git commit -m "feat: Add new feature"

============================================================
OK - CODE REVIEW PASSED - Commit allowed
============================================================

[main c4f8a3d2] feat: Add new feature
 1 file changed, 50 insertions(+)
```

**Result:** Commit accepted, pushed to main ✅

### Scenario 2: Code Fails Gate (New Violations) ❌

```bash
$ git add src/feature.py
$ git commit -m "feat: Add new feature"

============================================================
FAIL CODE REVIEW REJECTED
============================================================

[CRITICAL] Missing null check on line 23
[HIGH] Silent exception handler on line 45

Fix these issues and try again.
```

**Fix it:**
```bash
$ (edit src/feature.py to fix issues)
$ git add src/feature.py
$ git commit -m "feat: Add new feature - fix gate violations"

============================================================
OK - CODE REVIEW PASSED - Commit allowed
============================================================

[main c4f8a3d2] feat: Add new feature - fix gate violations
 1 file changed, 52 insertions(+)
```

**Result:** Commit accepted ✅

### Scenario 3: Code Fails Gate (Pre-Existing Violations)

```bash
$ git add src/legacy.py
$ git commit -m "fix: Update legacy function"

============================================================
FAIL CODE REVIEW REJECTED
============================================================

[CRITICAL #1] Missing null check on line 23 (YOUR change)
[HIGH #2] Silent exception handler on line 128 (PRE-EXISTING)

Fix violations and try again.
```

**Your option:**

**Option A: Fix both issues**
```bash
$ (fix both issues in src/legacy.py)
$ git add src/legacy.py
$ git commit -m "fix: Update + cleanup pre-existing issues"
```

**Option B: Create ticket for pre-existing issue**
```bash
$ (create GitHub issue TECH-DEBT-128: Silent exception handler)
$ (fix only your change in src/legacy.py)
$ git add src/legacy.py
$ git commit -m "fix: Update legacy function

Relates to #TECH-DEBT-128 (pre-existing issue)"
```

**Result:** Commit accepted with issue reference ✅

### Scenario 4: Attempt to Bypass Gate ❌ (FORBIDDEN)

```bash
$ git commit --no-verify -m "fix: urgent fix"

╔════════════════════════════════════════════════════════════════╗
║                 🚨 COMMIT GATE BYPASS BLOCKED 🚨              ║
╚════════════════════════════════════════════════════════════════╝

❌ ERROR: --no-verify flag is NOT ALLOWED

This bypass attempt has been LOGGED.
Escalation pending.
```

**Result:** 
- Commit BLOCKED ❌
- Developer FLAGGED 🚨
- Violation LOGGED 📋
- 24-hour cooldown ACTIVATED ⏱️

## Setup Instructions

### 1. Enable Pre-Commit Hook

```bash
cd /path/to/WROS-Master
chmod +x .git/hooks/pre-commit
chmod +x scripts/code-review-gate.sh
```

### 2. Enable Git Wrapper (Recommended)

```bash
# Make wrapper executable
chmod +x scripts/git-commit-wrapper.sh

# Add to ~/.bash_profile or ~/.zshrc
alias git='~/path/to/WROS-Master/scripts/git-commit-wrapper.sh'

# Reload shell
source ~/.bash_profile  # or ~/.zshrc
```

### 3. Verify Setup

```bash
# Test that wrapper is active
which git
# Output: /path/to/WROS-Master/scripts/git-commit-wrapper.sh

# Test that gate runs on commit
git commit --allow-empty -m "test: verify gate"
# Should show gate output, then accept commit
```

## Troubleshooting

### "Command not found: git"

**Problem:** Git wrapper path is wrong

**Fix:**
```bash
# Find real git
which git  # e.g., /usr/bin/git

# Update wrapper - change REAL_GIT path
vim scripts/git-commit-wrapper.sh
```

### "Pre-commit hook permission denied"

**Problem:** Hook not executable

**Fix:**
```bash
chmod +x .git/hooks/pre-commit
chmod +x scripts/code-review-gate.sh
```

### "I didn't use --no-verify, but commit was blocked"

**Problem:** Code review gate found violations

**Fix:**
1. Check the gate output for specific violations
2. Fix them in the code
3. Re-stage and re-commit

**Do NOT try --no-verify** - it will be blocked and logged.

## FAQs

**Q: What if my commit is urgent?**
A: The gate is faster than fixing production issues. Fix the code quality first, then commit. That's the whole point.

**Q: Can I use --no-verify in emergencies?**
A: No. There are no emergencies that justify skipping code review. If production is down, we need GOOD code, not quick code.

**Q: What if the gate is wrong about a violation?**
A: Report it as a bug in the gate itself. Fix your code anyway while we update the gate.

**Q: How long is the cooldown?**
A: 24 hours from first bypass attempt.

**Q: Will this be removed?**
A: No. This enforcement stays as long as we care about code quality.

## Policy Links

- **Full policy:** See `CLAUDE.md` "STRICT COMMIT ENFORCEMENT RULES"
- **Code review standards:** See `CLAUDE.md` "Fail Fast Error Handling"
- **Development guide:** See `CLAUDE.md` "Doing tasks"

## Support

If you have questions about the enforcement system:

1. Read this guide
2. Check the FAQs
3. Review the policy in CLAUDE.md
4. Ask team lead for clarification

**Do not try to work around the system.** It's there to protect code quality, and protecting code quality protects YOU.
