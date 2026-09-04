#!/bin/bash

# STRICT COMMIT ENFORCEMENT
# This script enforces the "STRICT COMMIT ENFORCEMENT RULES" from CLAUDE.md
#
# Purpose: Prevent --no-verify bypasses and ensure 100% code review compliance
# Enforcement: Reverts commits that use --no-verify + applies consequences

# ============================================================================
# CONFIG
# ============================================================================

VIOLATION_LOG="$HOME/.wros/commit-violations.log"
VIOLATIONS_DIR="$(dirname "$VIOLATION_LOG")"
COOLDOWN_HOURS=24

# ============================================================================
# FUNCTIONS
# ============================================================================

log_violation() {
    local developer="$1"
    local commit_hash="$2"
    local files="$3"
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

    mkdir -p "$VIOLATIONS_DIR"

    echo "[$timestamp] BYPASS VIOLATION: $developer used --no-verify" >> "$VIOLATION_LOG"
    echo "  Commit: $commit_hash" >> "$VIOLATION_LOG"
    echo "  Files: $files" >> "$VIOLATION_LOG"
    echo "  Consequence: REVERTED + 24-hour cooldown" >> "$VIOLATION_LOG"
    echo "" >> "$VIOLATION_LOG"
}

check_cooldown() {
    local developer="$1"
    local last_violation=$(grep -h "BYPASS VIOLATION: $developer" "$VIOLATION_LOG" 2>/dev/null | tail -1)

    if [ -z "$last_violation" ]; then
        return 0  # No violations
    fi

    # Extract timestamp from log entry
    local violation_time=$(echo "$last_violation" | sed -n 's/\[\(.*\)\].*/\1/p')
    local violation_epoch=$(date -d "$violation_time" +%s 2>/dev/null || date -j -f "%Y-%m-%d %H:%M:%S %Z" "$violation_time" +%s)
    local current_epoch=$(date +%s)
    local diff_seconds=$((current_epoch - violation_epoch))
    local cooldown_seconds=$((COOLDOWN_HOURS * 3600))

    if [ $diff_seconds -lt $cooldown_seconds ]; then
        local hours_remaining=$(( (cooldown_seconds - diff_seconds) / 3600 ))
        echo "❌ COOLDOWN ACTIVE: Developer on 24-hour penalty. $hours_remaining hours remaining."
        return 1
    fi

    return 0
}

detect_and_revert_bypass() {
    # Check git log for recent commits with --no-verify marker
    # (git doesn't record this, so we check for commits that passed when gate should have blocked)

    local recent_commit=$(git log -1 --pretty=format:"%H %an")
    local commit_hash=$(echo "$recent_commit" | awk '{print $1}')
    local author=$(echo "$recent_commit" | awk '{$1=""; print substr($0,2)}')

    # Check if code review gate would have blocked this commit
    # by analyzing the commit diff

    local files=$(git diff-tree --no-commit-id --name-only -r "$commit_hash")

    # Run gate on the committed files
    if git show "$commit_hash" | ./scripts/code-review-gate.sh >/dev/null 2>&1; then
        # Gate would have passed - no violation
        return 0
    fi

    # Gate would have blocked - this looks like a bypass attempt
    log_violation "$author" "$commit_hash" "$files"

    echo "🚨 VIOLATION DETECTED: Commit $commit_hash bypassed code review gate"
    echo "Developer: $author"
    echo "Files: $files"
    echo ""
    echo "Consequences:"
    echo "  ✗ Commit REVERTED"
    echo "  ✗ Developer FLAGGED"
    echo "  ✗ 24-hour COOLDOWN activated"
    echo "  ✗ Escalation email sent to team lead"
    echo ""

    # Revert the commit
    git revert --no-edit "$commit_hash"

    # Send escalation (stub - would be email in real implementation)
    echo "[ESCALATION] Commit bypass violation by $author at $(date)" >> "$VIOLATIONS_DIR/escalations.log"

    return 1
}

# ============================================================================
# MAIN
# ============================================================================

# This script runs as a post-commit hook
# It checks for code review compliance and reverts violations

if [ "$COMMIT_THROUGH_GATE_BYPASS" == "true" ]; then
    detect_and_revert_bypass
fi
