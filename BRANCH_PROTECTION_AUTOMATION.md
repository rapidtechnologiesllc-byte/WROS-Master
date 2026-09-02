# Autonomous Branch Protection Setup Guide

**Status:** ✅ Ready to execute  
**Scripts Created:** 2 (Python + Bash)  
**Requirement:** GitHub Personal Access Token

---

## 🚀 Quick Start

### Option 1: Using Python Script (Recommended)

**Step 1: Get GitHub Token**

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Name: `Branch Protection Setup`
4. Scopes needed:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `admin:repo_hook` (Write access to hooks)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again)

**Step 2: Run Python Script**

```bash
# Windows PowerShell
$env:GITHUB_TOKEN = 'your_token_here'
python scripts/setup_branch_protection.py

# Linux/Mac
export GITHUB_TOKEN='your_token_here'
python3 scripts/setup_branch_protection.py
```

**Step 3: Verify in GitHub UI**

- Go to: https://github.com/rapidtechnologiesllc-byte/WROS-Master/settings/branches
- Confirm protection rules are applied to all branches
- Status badge should show: ✅ Protected

---

### Option 2: Using Bash Script

```bash
# Windows (Git Bash)
export GITHUB_TOKEN='your_token_here'
bash scripts/setup-branch-protection.sh

# Linux/Mac
export GITHUB_TOKEN='your_token_here'
bash scripts/setup-branch-protection.sh
```

---

## 📋 What the Script Does

### Configuration Applied to ALL Branches

**For `main` branch (strictest):**
- ✅ Require 2 pull request reviews
- ✅ Dismiss stale reviews
- ✅ Require status checks: "Code Review Gate - All Branches"
- ✅ Require branches up to date
- ✅ No force pushes allowed
- ✅ No branch deletions allowed
- ✅ Require conversation resolution
- ✅ Enforce rules on administrators

**For all other branches:**
- ✅ Require 1 pull request review
- ✅ Dismiss stale reviews
- ✅ Require status checks: "Code Review Gate - All Branches"
- ✅ Require branches up to date
- ✅ No force pushes allowed
- ✅ No branch deletions allowed
- ✅ Require conversation resolution
- ✅ Enforce rules on administrators

---

## 🔐 Getting a GitHub Token

### Method 1: GitHub Web UI (Easiest)

1. Navigate to: https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Fill in details:
   - **Token name:** `Branch Protection Setup`
   - **Expiration:** 30 days (or custom)
   - **Select scopes:**
     - ✅ `repo` - Full control of private repositories
     - ✅ `admin:repo_hook` - Write access to hooks
     - ✅ `workflow` - Update GitHub Actions workflows
4. Click **"Generate token"**
5. **COPY TOKEN IMMEDIATELY** - You won't see it again!
6. Save securely (password manager or temporary file)

### Method 2: GitHub CLI (If Installed)

```bash
# Install GitHub CLI first
# Then authenticate
gh auth login

# Get token (stores in credentials)
gh auth token
```

### Method 3: GitHub App (Advanced)

- Create a GitHub App with repository admin permissions
- Use app credentials instead of personal token

---

## ⚙️ Script Details

### Python Script: `scripts/setup_branch_protection.py`

**Features:**
- ✅ Validates GitHub token before proceeding
- ✅ Fetches all branches dynamically
- ✅ Applies protection to all branches
- ✅ Verifies GitHub Actions workflow status
- ✅ Detailed colored output with progress
- ✅ Error handling and retry logic
- ✅ Summary report at end

**Requirements:**
- Python 3.6+
- `requests` library

**Install requests:**
```bash
pip install requests
```

**Execution:**
```bash
python scripts/setup_branch_protection.py
```

---

### Bash Script: `scripts/setup-branch-protection.sh`

**Features:**
- ✅ Uses curl for API calls
- ✅ Configures main, master, develop specifically
- ✅ Iterates through all other branches
- ✅ Validates protection is applied
- ✅ Error messages for troubleshooting

**Requirements:**
- Bash 4.0+
- curl command-line tool
- GitHub token in `GITHUB_TOKEN` environment variable

**Execution:**
```bash
bash scripts/setup-branch-protection.sh
```

---

## 🧪 Testing After Setup

### Test 1: Verify Protection on main

```bash
# Try to force-push to main (should fail)
git push --force-with-lease origin main

# Expected result:
# fatal: Push rejected
# remote: error: protected branch
```

### Test 2: Verify Gate Check Works

```bash
# Create PR with code violations
git checkout -b test/gate-check
# (add code with RBAC violations)
git commit -am "test: Attempt merge with violations"
git push origin test/gate-check

# Go to GitHub, create PR
# Result: Merge button should be DISABLED
# Message: "1 check is failing - Code Review Gate"
```

### Test 3: Verify Approval Requirement

```bash
# Try to merge PR without approvals
# Result: Merge button DISABLED
# Message: "1 of 2 required reviews"
```

---

## 🚨 Troubleshooting

### Error: "GITHUB_TOKEN not set"

**Solution:**
```bash
# Windows PowerShell
$env:GITHUB_TOKEN = 'your_token'

# Linux/Mac/Bash
export GITHUB_TOKEN='your_token'
```

### Error: "Invalid token"

**Solution:**
1. Check token is copied correctly (no extra spaces)
2. Verify token has correct scopes: `repo`, `admin:repo_hook`
3. Token might be expired (check expiration date)
4. Generate a new token and try again

### Error: "Branch not found"

**Solution:**
- This is normal for wildcard patterns
- Script will automatically handle individual branches
- All branches will still be protected

### Error: "Insufficient permissions"

**Solution:**
1. Verify token has `repo` scope
2. Verify token has `admin:repo_hook` scope
3. Verify you're the repository owner/admin
4. Token permissions cannot be modified - generate new token with correct scopes

### Workflow Not Found

**Solution:**
- GitHub indexes workflows after ~5 minutes
- Script shows warning if workflow not yet indexed
- Workflow IS still active even if not indexed yet
- Status checks will work once indexed

---

## 📊 What Gets Protected

### Before Setup
- ❌ `main` branch: No protection
- ❌ `master` branch: No protection
- ❌ Feature branches: No protection
- ❌ Orphaned branches: No protection
- ✅ Local pre-commit hook: Working

### After Setup
- ✅ `main` branch: 2 reviews required + gate check + status checks
- ✅ `master` branch: 1 review required + gate check + status checks
- ✅ ALL feature branches: 1 review required + gate check + status checks
- ✅ ALL orphaned branches: Protected (no direct pushes allowed)
- ✅ No force-pushes allowed on ANY branch
- ✅ No branch deletions allowed on ANY branch
- ✅ GitHub Actions gate runs on every push

---

## ✅ Success Criteria

After running the script:

- [ ] Script completes without errors
- [ ] Terminal shows: `✓ Protected branches: X`
- [ ] No token/permission errors
- [ ] Go to GitHub Settings → Branches
- [ ] All branches show protection rule
- [ ] "Code Review Gate" shows as required check
- [ ] Merge button disabled until checks pass
- [ ] Force-push rejected with permission error

---

## 🔄 Reverting Protection (If Needed)

To remove branch protection and start over:

```bash
# Via GitHub web UI:
1. Go to: https://github.com/rapidtechnologiesllc-byte/WROS-Master/settings/branches
2. Click the rule
3. Click "Delete"
4. Then re-run the script to re-apply
```

---

## 📞 Support

**If you encounter issues:**

1. Check that GitHub token has correct scopes
2. Verify token is not expired
3. Run with `--verbose` flag (if available in script)
4. Check GitHub API status: https://www.githubstatus.com/
5. Contact repository admin

---

## 🎯 Next Steps

1. **Generate GitHub token** (see "Getting a GitHub Token" above)
2. **Run Python script:** `python scripts/setup_branch_protection.py`
3. **Verify in GitHub UI** at: https://github.com/rapidtechnologiesllc-byte/WROS-Master/settings/branches
4. **Test protection** by trying to merge code with violations
5. **Confirm:** Merge button is disabled until violations fixed

---

**All branch protection rules will be autonomous after setup. No manual GitHub UI configuration needed!**

Status: ✅ READY TO DEPLOY
