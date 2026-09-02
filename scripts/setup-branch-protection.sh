#!/bin/bash

# GitHub Branch Protection Rules Setup
# Configures multi-layer protection for all branches
# Usage: GITHUB_TOKEN=xxx bash scripts/setup-branch-protection.sh

set -e

# Configuration
REPO_OWNER="rapidtechnologiesllc-byte"
REPO_NAME="WROS-Master"
GITHUB_API="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validate token
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}ERROR: GITHUB_TOKEN environment variable not set${NC}"
    echo "Usage: GITHUB_TOKEN=your_token bash scripts/setup-branch-protection.sh"
    exit 1
fi

echo -e "${YELLOW}=== GitHub Branch Protection Setup ===${NC}"
echo "Repository: ${REPO_OWNER}/${REPO_NAME}"
echo "Configuring protection for ALL branches..."
echo ""

# Function to create/update branch protection rule
configure_protection() {
    local branch_pattern=$1
    local dismiss_stale_reviews=$2
    local required_approving_reviews=$3
    local require_code_owner_reviews=$4
    local require_status_checks=$5
    local strict=$6

    echo -e "${YELLOW}Configuring: ${branch_pattern}${NC}"

    # Build the JSON payload
    read -r -d '' PAYLOAD << EOF || true
{
  "required_status_checks": {
    "strict": ${strict},
    "contexts": [
      "Code Review Gate - All Branches"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": ${dismiss_stale_reviews},
    "require_code_owner_reviews": ${require_code_owner_reviews},
    "required_approving_review_count": ${required_approving_reviews}
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "require_branches_to_be_up_to_date": true
}
EOF

    # Send request to GitHub API
    RESPONSE=$(curl -s -X PUT \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${GITHUB_API}/branches/${branch_pattern}/protection" \
        -d "${PAYLOAD}")

    # Check if response contains an error
    if echo "${RESPONSE}" | grep -q '"message"'; then
        ERROR_MSG=$(echo "${RESPONSE}" | grep -o '"message":"[^"]*' | cut -d'"' -f4)
        if [[ "${ERROR_MSG}" == *"Branch not found"* ]]; then
            echo -e "${YELLOW}  ⚠️  Branch pattern '${branch_pattern}' not found (wildcard patterns need special handling)${NC}"
            return 1
        else
            echo -e "${RED}  ✗ Error: ${ERROR_MSG}${NC}"
            return 1
        fi
    else
        echo -e "${GREEN}  ✓ Protection configured successfully${NC}"
        return 0
    fi
}

# Configure protection for main branch (strictest)
echo -e "${YELLOW}Layer 3: Branch Protection Rules${NC}"
echo ""

echo "Step 1: Configure MAIN branch (strictest settings)"
configure_protection "main" "true" "2" "false" "true" "true"
MAIN_RESULT=$?

echo ""
echo "Step 2: Configure MASTER branch"
configure_protection "master" "true" "1" "false" "true" "true"
MASTER_RESULT=$?

echo ""
echo "Step 3: Configure DEVELOP branch (if exists)"
configure_protection "develop" "true" "1" "false" "true" "true"
DEV_RESULT=$?

echo ""
echo "Step 4: Configure all other branches with * pattern"
echo -e "${YELLOW}Attempting to configure wildcard protection...${NC}"

# For wildcard patterns, we need to use the exact branch name or iterate through branches
# GitHub API doesn't support wildcard patterns directly in the protection endpoint
# So we'll get all branches and protect them

BRANCHES_JSON=$(curl -s \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "${GITHUB_API}/branches?per_page=100")

# Extract branch names (excluding already protected ones)
BRANCH_NAMES=$(echo "${BRANCHES_JSON}" | grep -o '"name":"[^"]*' | cut -d'"' -f4 | grep -v -E '^(main|master|develop)$')

PROTECTED_COUNT=0
for branch in $BRANCH_NAMES; do
    echo -n "  Protecting ${branch}... "

    read -r -d '' PAYLOAD << EOF || true
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Code Review Gate - All Branches"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "require_branches_to_be_up_to_date": true
}
EOF

    RESPONSE=$(curl -s -X PUT \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${GITHUB_API}/branches/${branch}/protection" \
        -d "${PAYLOAD}")

    if echo "${RESPONSE}" | grep -q '"message"'; then
        echo -e "${RED}✗${NC}"
    else
        echo -e "${GREEN}✓${NC}"
        ((PROTECTED_COUNT++))
    fi
done

echo ""
echo -e "${YELLOW}=== Summary ===${NC}"
echo -e "${GREEN}✓ Main branch: $([ $MAIN_RESULT -eq 0 ] && echo 'Protected' || echo 'Failed')${NC}"
echo -e "${GREEN}✓ Master branch: $([ $MASTER_RESULT -eq 0 ] && echo 'Protected' || echo 'Failed')${NC}"
echo -e "${GREEN}✓ Develop branch: $([ $DEV_RESULT -eq 0 ] && echo 'Protected' || echo 'Failed/Not Found')${NC}"
echo -e "${GREEN}✓ Other branches protected: ${PROTECTED_COUNT}${NC}"
echo ""

# Verify GitHub Actions check is registered
echo -e "${YELLOW}Step 5: Verifying GitHub Actions workflow is active...${NC}"

WORKFLOWS=$(curl -s \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "${GITHUB_API}/actions/workflows")

if echo "${WORKFLOWS}" | grep -q "code-gate.yml"; then
    echo -e "${GREEN}✓ code-gate.yml workflow found${NC}"
else
    echo -e "${YELLOW}⚠️  code-gate.yml workflow not yet indexed${NC}"
    echo "    (It may take a few minutes for GitHub to index new workflows)"
fi

echo ""
echo -e "${GREEN}=== Branch Protection Setup Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Go to: https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/branches"
echo "2. Verify protection rules are applied"
echo "3. Test: Try pushing code with violations (should be blocked)"
echo ""
