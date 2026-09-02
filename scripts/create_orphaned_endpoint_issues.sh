#!/bin/bash
# Create GitHub Issues for 26 Orphaned Endpoints
# Usage: ./create_orphaned_endpoint_issues.sh GITHUB_TOKEN PROJECT_ID

set -e

GITHUB_TOKEN="${1:-}"
PROJECT_ID="${2:-PVT_kwHOD2fGNs4BgS1H}"
REPO="rapidtechnologiesllc-byte/WROS-Master"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GitHub token required"
    echo "Usage: $0 GITHUB_TOKEN [PROJECT_ID]"
    echo ""
    echo "Get token: https://github.com/settings/tokens"
    echo "Create with scopes: repo, project"
    exit 1
fi

# Array of orphaned endpoint files
ORPHANED_FILES=(
    "agent_config"
    "bi_explorer"
    "bu_head_dashboard"
    "candidate_ranking"
    "candidate_rejection"
    "complete_workflow"
    "conversions"
    "crud"
    "doctor_traces_dashboard"
    "employee_conversion"
    "hiring_manager_validation"
    "interview_decision"
    "invoices_s316"
    "offers"
    "onboarding_orchestrator"
    "onboarding_workflow"
    "queue"
    "queue_dashboard"
    "queues"
    "resume_versions"
    "revenue_recognition"
    "spartan_forecasting"
    "spartan_integration"
    "strategic_consul"
    "system_health"
    "training_dashboards"
)

echo "================================================"
echo "Creating GitHub Issues for Orphaned Endpoints"
echo "================================================"
echo ""
echo "Repository: $REPO"
echo "Project ID: $PROJECT_ID"
echo "Files to create: ${#ORPHANED_FILES[@]}"
echo ""

ISSUE_IDS=()
CREATED_COUNT=0

for filename in "${ORPHANED_FILES[@]}"; do
    echo -n "Creating issue for $filename.py... "

    TITLE="Backlog: $filename endpoint - Not registered (orphaned code)"

    BODY="## Status: Orphaned / Not Registered

**File:** \`backend/app/api/v1/endpoints/$filename.py\`

**Issue:** This endpoint file exists in the codebase but is NOT registered in \`app/api/v1/routes.py\`.

This causes:
- Frontend screens trying to call it get 404 errors
- Dead code that appears complete but doesn't run
- Gate reports false positives for security issues

## Decision Required

**Choose ONE option:**

### Option A: DELETE
Remove the file if it's truly dead code.

\`\`\`bash
git rm backend/app/api/v1/endpoints/$filename.py
git commit -m \"remove: Delete orphaned endpoint $filename\"
\`\`\`

### Option B: REGISTER
Register in routes.py if it should be active.

1. Open \`backend/app/api/v1/routes.py\`
2. Add import: \`from app.api.v1.endpoints.$filename import router as ${filename}_router\`
3. Add router: \`router.include_router(${filename}_router)\`

### Option C: ARCHIVE
Move to backlog if might need later.

\`\`\`bash
mkdir -p backend/backlog/endpoints
git mv backend/app/api/v1/endpoints/$filename.py backend/backlog/endpoints/
\`\`\`

**Related Issues:**
- Parent: Backlog: Clean Up 26 Orphaned Endpoint Files
- See: GATE_ACCURACY_REPORT.md"

    # Create issue via GitHub API
    RESPONSE=$(curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$REPO/issues" \
        -d "{
            \"title\": \"$TITLE\",
            \"body\": \"$BODY\",
            \"labels\": [\"backlog\", \"backend\", \"cleanup\", \"orphaned-code\"]
        }")

    # Extract issue number
    ISSUE_NUMBER=$(echo "$RESPONSE" | grep -o '"number": [0-9]*' | head -1 | grep -o '[0-9]*')

    if [ -z "$ISSUE_NUMBER" ]; then
        echo "❌ FAILED"
        echo "Response: $RESPONSE"
        continue
    fi

    echo "✅ #$ISSUE_NUMBER"
    ISSUE_IDS+=("$ISSUE_NUMBER")
    CREATED_COUNT=$((CREATED_COUNT + 1))
done

echo ""
echo "================================================"
echo "Created: $CREATED_COUNT issues"
echo "================================================"
echo ""
echo "Issue Numbers: ${ISSUE_IDS[@]}"
echo ""
echo "Next Step: Add issues to GitHub Project"
echo "Project: github.com/users/rapidtechnologiesllc-byte/projects/1"
echo ""
echo "You can now add these issues to the project board:"
echo "1. Go to the project: https://github.com/users/rapidtechnologiesllc-byte/projects/1"
echo "2. Click 'Add item'"
echo "3. Search for each issue number from above"
echo ""
echo "Or use GitHub Projects API to add automatically (see add_to_project.sh)"
