# Automated GitHub Issue Creation & Project Board Workflow

## Current Status

✅ **250 file-based issues being created**
- Issue #85-#334 (one per file with code quality issues)
- Each includes severity, counts, action items
- All created automatically via REST API

❌ **Project board addition blocked**
- GraphQL ProjectV2 API requires `projects:write` scope
- Fine-grained PAT tokens don't support this scope
- Token error: "Resource not accessible by personal access token"

## Solution: Use GitHub CLI for Full Automation

GitHub CLI (`gh`) has native support for adding issues to projects via `gh project item-add`.

### Step 1: Install GitHub CLI (if not already installed)

**Windows:**
```bash
# Via winget
winget install GitHub.cli

# Via chocolatey
choco install gh

# Via scoop
scoop install gh
```

**Verify installation:**
```bash
gh --version
```

### Step 2: Authenticate GitHub CLI

```bash
gh auth login
# Follow prompts to authenticate with your GitHub account
# When asked about GitHub API, select the PAT token option if needed
```

### Step 3: Run Automated Project Board Population Script

```bash
python add_issues_via_gh_cli.py
```

This script will:
1. ✅ Get list of all created issues (#85+)
2. ✅ Use GitHub CLI to add each to project board
3. ✅ No token permission issues
4. ✅ Completely automated

## Why GitHub CLI Works

- GitHub CLI is the official automation tool by GitHub
- Has built-in project board support
- Authenticates via `gh auth login` (full OAuth)
- No fine-grained PAT scope limitations

## Files Created

1. **create_all_issues_v2.py** - Creates all 250 GitHub issues ✅
2. **add_issues_via_gh_cli.py** - Adds issues to project via `gh` CLI ⏳ (new)
3. **AUTOMATED_ISSUE_WORKFLOW.md** - This file

## Full Automation Sequence

```bash
# 1. Create all issues (already done)
python create_all_issues_v2.py

# 2. Install GitHub CLI (one-time)
winget install GitHub.cli

# 3. Authenticate (one-time)
gh auth login

# 4. Add all to project board (fully automated)
python add_issues_via_gh_cli.py

# Result: 250+ issues on project board, completely automated
```

## No Manual Steps Required

✅ Issue creation: Fully automated
✅ Project board add: Fully automated (via `gh` CLI)
✅ Total: **Zero manual work**

---

**Next:** Create and run `add_issues_via_gh_cli.py` to complete the workflow.
