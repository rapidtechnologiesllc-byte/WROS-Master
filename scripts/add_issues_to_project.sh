#!/bin/bash
# Add GitHub Issues to Project Board
# Usage: ./add_issues_to_project.sh GITHUB_TOKEN PROJECT_ID ISSUE_NUMBERS...

set -e

GITHUB_TOKEN="${1:-}"
PROJECT_ID="${2:-PVT_kwHOD2fGNs4BgS1H}"
shift 2
ISSUE_NUMBERS=("$@")

if [ -z "$GITHUB_TOKEN" ] || [ ${#ISSUE_NUMBERS[@]} -eq 0 ]; then
    echo "❌ Token and issue numbers required"
    echo "Usage: $0 GITHUB_TOKEN PROJECT_ID ISSUE_NUMBER [ISSUE_NUMBER...]"
    echo ""
    echo "Example:"
    echo "  $0 ghp_xxxxx PVT_kwHO... 1 2 3 4 5"
    exit 1
fi

REPO="rapidtechnologiesllc-byte/WROS-Master"

echo "================================================"
echo "Adding Issues to GitHub Project"
echo "================================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Issues: ${ISSUE_NUMBERS[@]}"
echo ""

for ISSUE_NUM in "${ISSUE_NUMBERS[@]}"; do
    echo -n "Adding issue #$ISSUE_NUM to project... "

    # Get issue details
    ISSUE_RESPONSE=$(curl -s -X GET \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$REPO/issues/$ISSUE_NUM")

    ISSUE_ID=$(echo "$ISSUE_RESPONSE" | grep -o '"id": [0-9]*' | head -1 | grep -o '[0-9]*')

    if [ -z "$ISSUE_ID" ]; then
        echo "❌ FAILED (couldn't get issue ID)"
        continue
    fi

    # Add to project
    ADD_RESPONSE=$(curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/graphql" \
        -d "{
            \"query\": \"mutation { addProjectV2ItemById(input: {projectId: \\\"$PROJECT_ID\\\", contentId: \\\"$ISSUE_ID\\\"}) { item { id } } }\"
        }")

    if echo "$RESPONSE" | grep -q "errors"; then
        echo "❌ FAILED"
        echo "Response: $RESPONSE"
    else
        echo "✅ Added"
    fi
done

echo ""
echo "================================================"
echo "✅ All issues added to project"
echo "================================================"
echo ""
echo "View project: https://github.com/users/rapidtechnologiesllc-byte/projects/1"
