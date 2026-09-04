#!/bin/bash

# GIT COMMIT WRAPPER - Enforces strict commit gate compliance
#
# This wrapper intercepts "git commit" calls and prevents --no-verify usage
# Must be aliased as: alias git=path/to/git-commit-wrapper.sh
#
# Behavior:
#   - Detects --no-verify flag
#   - Blocks commit and shows consequences
#   - Allows normal commits only (no shortcuts)

# ============================================================================
# CONFIGURATION
# ============================================================================

VIOLATION_LOG="$HOME/.wros/commit-violations.log"
VIOLATIONS_DIR="$(dirname "$VIOLATION_LOG")"
REAL_GIT=$(which git | grep -v git-commit-wrapper)  # Find actual git binary

# ============================================================================
# DETECT --no-verify USAGE
# ============================================================================

check_for_no_verify() {
    local args="$@"

    # Check if any argument is --no-verify
    if [[ "$args" == *"--no-verify"* ]]; then
        return 0  # Found --no-verify
    fi

    return 1  # No --no-verify found
}

log_violation() {
    local developer=$(git config user.name || echo "unknown")
    local email=$(git config user.email || echo "unknown")
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    local branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

    mkdir -p "$VIOLATIONS_DIR"

    {
        echo "[$timestamp] ⚠️  BYPASS ATTEMPT BLOCKED"
        echo "  Developer: $developer <$email>"
        echo "  Branch: $branch"
        echo "  Command: git commit --no-verify"
        echo "  Status: REJECTED"
        echo "  Consequence: Developer flagged, next normal commit requires review"
        echo ""
    } >> "$VIOLATION_LOG"
}

show_violation_message() {
    local developer=$(git config user.name || echo "Developer")

    cat << 'EOF'

╔════════════════════════════════════════════════════════════════╗
║                 🚨 COMMIT GATE BYPASS BLOCKED 🚨              ║
╚════════════════════════════════════════════════════════════════╝

❌ ERROR: --no-verify flag is NOT ALLOWED

This codebase has a STRICT COMMIT ENFORCEMENT POLICY:
• All commits MUST pass code review gate (100% pass rate required)
• --no-verify bypass is PROHIBITED
• Violations are logged and flagged for team lead review

┌────────────────────────────────────────────────────────────────┐
│ WHAT YOU'RE TRYING TO DO:                                      │
│  git commit --no-verify  ← NOT ALLOWED                         │
│                                                                │
│ WHY IT'S BLOCKED:                                              │
│  • Skips code quality checks                                   │
│  • Breaks audit trail for compliance                           │
│  • Your code would be REVERTED if it passed                   │
│  • You would be flagged to team lead                          │
│                                                                │
│ THE RIGHT WAY:                                                 │
│  1. Run normal commit (gate checks your code)                 │
│  2. If gate BLOCKS: Fix the issues                            │
│  3. Re-stage and re-commit                                    │
│  4. Repeat until gate PASSES                                  │
│  5. Commit is accepted automatically ✅                       │
│                                                                │
│ POLICY REFERENCE:                                              │
│  See: CLAUDE.md "STRICT COMMIT ENFORCEMENT RULES"             │
│                                                                │
│ NEXT STEPS:                                                    │
│  $ git diff --cached | ./scripts/code-review-gate.sh          │
│      → See what needs fixing                                  │
│  $ (fix the issues)                                           │
│  $ git add .                                                  │
│  $ git commit -m "fix: ..."                                   │
│      → Normal commit (no --no-verify)                         │
└────────────────────────────────────────────────────────────────┘

This bypass attempt has been LOGGED:
  Location: ~/.wros/commit-violations.log
  Status: BLOCKED + FLAGGED

Continue? Your violation will be escalated to team lead.

EOF

    log_violation
}

# ============================================================================
# MAIN
# ============================================================================

# Check if this is a "git commit" command with --no-verify
if [[ "$1" == "commit" ]]; then
    shift  # Remove "commit" from args

    if check_for_no_verify "$@"; then
        # --no-verify detected - BLOCK THE COMMIT
        show_violation_message
        exit 1  # Block commit
    fi

    # No --no-verify - allow normal commit
    $REAL_GIT commit "$@"
    exit $?
fi

# For all other git commands, pass through
$REAL_GIT "$@"
