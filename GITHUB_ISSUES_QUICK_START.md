# GitHub Issues - Quick Start Guide

## 🎯 IMMEDIATE ACTION REQUIRED

Create 26 GitHub issues for orphaned endpoints + 1 parent issue.

---

## Step 1: Get GitHub Token

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token"
3. Create "Fine-grained personal access token" with scopes:
   - `repo` (full control)
   - `project` (read/write)
4. Copy the token (keep it safe!)

---

## Step 2: Create the Issues

### Option A: Automated (Using Scripts)

```bash
cd WROS-Master/scripts

# Create all 26 orphaned endpoint issues
bash create_orphaned_endpoint_issues.sh ghp_YOUR_TOKEN_HERE

# Note the issue numbers created (e.g., #100, #101, #102...)
```

### Option B: Manual (Web Interface)

1. Go to: https://github.com/rapidtechnologiesllc-byte/WROS-Master/issues
2. Click "New Issue"
3. Use template from: `GITHUB_ISSUE_TEMPLATE_ORPHANED_ENDPOINT.md`
4. Create one issue per file:
   - agent_config.py
   - bi_explorer.py
   - bu_head_dashboard.py
   - (... repeat for all 26 files)

---

## Step 3: Add Issues to Project Board

### Option A: Automated (Using Scripts)

```bash
cd WROS-Master/scripts

# Add all issues to project (replace numbers with actual issue numbers)
bash add_issues_to_project.sh ghp_YOUR_TOKEN_HERE PVT_kwHOD2fGNs4BgS1H 100 101 102 103 ...
```

### Option B: Manual (Web Interface)

1. Go to: https://github.com/users/rapidtechnologiesllc-byte/projects/1
2. Click "Add item"
3. Search for each issue number (e.g., #100)
4. Click to add to project
5. Repeat for all 26 issues

---

## Step 4: Create Parent Issue

Create one issue for: **"Backlog: Clean Up 26 Orphaned Endpoint Files"**

Body:
```
## Status: Epic / Parent Issue

26 endpoint files exist but are NOT registered in app/api/v1/routes.py

**Impact:**
- Frontend 404 errors
- Dead code maintenance burden
- Gate false positives (40% of security issues)

**Related Issues:**
- #100: Backlog: agent_config endpoint
- #101: Backlog: bi_explorer endpoint
- #102: Backlog: bu_head_dashboard endpoint
... (all 26)

**Decision Tracking:**
- [ ] agent_config: Delete/Register/Archive
- [ ] bi_explorer: Delete/Register/Archive
... (for each file)

**Progress:** 0/26 decided
```

---

## Step 5: Track Real Issues

After orphaned code is cleaned up:

**Run scan:**
```bash
cd backend/scripts
python scan_codebase.py
```

**Create issues for real violations:**
- 128 missing error messages
- 24 silent exception catches
- 170 missing null checks
- 6 magic numbers
- ~300 missing permission checks (active code only)

---

## File Reference

| Document | Purpose |
|----------|---------|
| GITHUB_ISSUE_TEMPLATE_ORPHANED_ENDPOINT.md | Template for creating issues |
| BACKLOG_ORPHANED_ENDPOINTS.md | List of all 26 files + decisions |
| GATE_ACCURACY_REPORT.md | Full accuracy assessment |
| scripts/create_orphaned_endpoint_issues.sh | Automated issue creation |
| scripts/add_issues_to_project.sh | Automated project board addition |

---

## GitHub Project Details

| Field | Value |
|-------|-------|
| Name | WROS Project |
| URL | https://github.com/users/rapidtechnologiesllc-byte/projects/1 |
| Project ID | PVT_kwHOD2fGNs4BgS1H |
| Repo | rapidtechnologiesllc-byte/WROS-Master |

---

## Going Forward Policy

✅ **NEW POLICY (Starting 2026-09-02):**

When finding issues:
1. Create GitHub issues FIRST
2. Add to project board IMMEDIATELY
3. Update markdown LAST
4. Reference in commits: `Closes #123`

**GitHub project is now the primary tracking system.**
Markdown files are just documentation backups.

---

## Need Help?

- Gate issues? See: `GATE_ACCURACY_REPORT.md`
- Orphaned files? See: `BACKLOG_ORPHANED_ENDPOINTS.md`
- Create issues? See: `GITHUB_ISSUE_TEMPLATE_ORPHANED_ENDPOINT.md`
- API scripting? See: `scripts/create_orphaned_endpoint_issues.sh`

---

## Status Checklist

- [ ] Generate GitHub token
- [ ] Create 26 orphaned endpoint issues
- [ ] Create 1 parent epic issue
- [ ] Add all issues to project board
- [ ] Team reviews and decides on each
- [ ] Cleanup orphaned files (delete/register/archive)
- [ ] Re-scan for accurate baseline
- [ ] Fix real architectural violations

**Timeline:** 1-2 days for setup, 1-2 weeks for cleanup and fixes
