# GitHub Branch Protection Rules - Setup Guide

**Status:** CRITICAL - Must be configured to prevent code violations from entering ANY branch

**Repository:** https://github.com/rapidtechnologiesllc-byte/WROS-Master

---

## 🔐 Multi-Layer Protection Strategy

### Layer 1: Local Gate (Pre-Commit Hook)
- ✅ Deployed: Pre-commit hook blocks commits locally
- Location: `.git/hooks/pre-commit`
- Runs: On every git commit
- Can be bypassed: `git commit --no-verify`

### Layer 2: GitHub Actions Gate (THIS DOCUMENT)
- ✅ Deployed: `.github/workflows/code-gate.yml`
- Runs: Every push to ANY branch
- Cannot be bypassed: No bypass flag exists
- Blocks: PR merge if violations found

### Layer 3: Branch Protection Rules (MANUAL SETUP REQUIRED)
- ❌ Not yet configured: Must be set up in GitHub UI
- Enforces: PR reviews, passing checks before merge
- Protects: All branches (main, feature branches, etc.)

---

## 🚨 Why This Is Critical

**Without GitHub protection, developers can:**
```bash
# Bypass local hook
git commit --no-verify

# Force-push to feature branch (GitHub doesn't block it)
git push --force-with-lease origin claude/linkedin-candidate-wros-mompvd
```

**Result:** Bad code ends up in feature branches → causes merge conflicts → hidden bugs in history

---

## 📋 Required GitHub Rules Configuration

### Step 1: Navigate to Branch Protection Settings

1. Go to: https://github.com/rapidtechnologiesllc-byte/WROS-Master/settings/branches
2. Click **"Add rule"** button
3. Enter pattern: `**` (protects ALL branches)
4. OR create specific rules for: `main`, `master`, `develop`, `feature/*`

---

### Step 2: Configure Protection Rules for Pattern `**`

| Setting | Value | Reason |
|---------|-------|--------|
| **Require a pull request before merging** | ✅ YES | No direct pushes allowed |
| **Require code review before merging** | ✅ YES | At least 1 approval needed |
| **Number of required reviews** | 1 (minimum) | Can set higher for main |
| **Dismiss stale pull request approvals** | ✅ YES | Fresh approval on new commits |
| **Require review from code owners** | ❌ NO | (Optional - create CODEOWNERS file if needed) |
| **Require status checks to pass** | ✅ YES | **CRITICAL** |
| **Status check:** Code Review Gate | ✅ YES | Require `code-gate` workflow to pass |
| **Status check:** Tests | ✅ YES | Require test suite to pass |
| **Require branches to be up to date** | ✅ YES | Merge only after rebasing on main |
| **Require conversation resolution** | ✅ YES | All comments must be resolved |
| **Include administrators** | ⚠️ YES (Recommended) | Admins must follow same rules |
| **Allow force pushes** | ❌ NO | Prevent bypassing protections |
| **Allow deletions** | ❌ NO | Prevent branch deletion |

---

### Step 3: Configure for `main` Branch (Stricter)

Create a second rule specifically for `main` with stricter settings:

| Setting | Value | Reason |
|---------|-------|--------|
| **Branch name pattern** | `main` | Production branch |
| **Require a pull request before merging** | ✅ YES | No direct pushes |
| **Number of required reviews** | 2+ | Peer review from multiple people |
| **Dismiss stale pull request approvals** | ✅ YES | Fresh approval only |
| **Require branches to be up to date** | ✅ YES | Always rebase before merge |
| **Require status checks to pass** | ✅ YES | **MANDATORY** |
| **Status checks:** | | |
| - Code Review Gate | ✅ REQUIRED | Gate violations block merge |
| - Tests | ✅ REQUIRED | Test suite must pass |
| - Build | ✅ REQUIRED | Code must compile/build |
| **Include administrators** | ✅ YES | No bypassing for admins |
| **Allow force pushes** | ❌ NO | Absolute - no force push to main |
| **Allow deletions** | ❌ NO | Absolute - cannot delete main |
| **Require conversation resolution** | ✅ YES | All comments resolved |

---

### Step 4: Authorize Status Checks

GitHub needs to know which CI/CD checks are required. After pushing code-gate.yml:

1. Go to https://github.com/rapidtechnologiesllc-byte/WROS-Master/settings/branches
2. Click on branch rule
3. Scroll to **"Require status checks to pass before merging"**
4. Search for: `Code Review Gate - All Branches`
5. Check the box to mark as **required**
6. Check **"Require branches to be up to date before merging"**

---

## 🚀 How It Works After Setup

### Scenario 1: Developer pushes to feature branch

```
Developer pushes to feature/my-branch
  ↓
GitHub Actions runs code-gate.yml
  ↓
Validator finds violations
  ↓
Check FAILS ❌
  ↓
Can NOT create PR (requires passing checks)
  ↓
Developer must fix code locally, push again
```

### Scenario 2: Developer tries to force-push (bypass)

```
Developer runs: git push --force-with-lease
  ↓
GitHub rejects (branch protection prevents force-push)
  ↓
Error message: "Branch protection rules prevent push to this branch"
  ↓
Must go through PR process instead
```

### Scenario 3: PR is created despite violations

```
Developer creates PR with violations
  ↓
GitHub Actions runs code-gate.yml on PR
  ↓
Check FAILS ❌
  ↓
Merge button DISABLED with message:
  "1 check is failing - Code Review Gate - All Branches"
  ↓
Cannot merge until violations fixed
```

---

## 🔍 Verification Checklist

After setting up all rules, verify they work:

- [ ] Attempt to push directly to `main` (should fail with "protected branch" error)
- [ ] Attempt to force-push to feature branch (should fail)
- [ ] Create PR with code violations (check should fail)
- [ ] Fix code, re-push, check should pass
- [ ] Verify PR merge button is disabled until check passes
- [ ] Verify PR requires 1+ approvals before merge
- [ ] Verify admin cannot bypass without following same rules

---

## 📊 Current Protection Status

| Layer | Status | Check |
|-------|--------|-------|
| Pre-commit hook | ✅ Active | `git commit` blocked locally |
| GitHub Actions gate | ✅ Deployed | `.github/workflows/code-gate.yml` |
| Branch protection rules | ❌ **PENDING SETUP** | Must be configured in GitHub UI |
| **Overall Protection** | ❌ **INCOMPLETE** | Waiting for manual GitHub configuration |

---

## 🎯 Implementation Timeline

1. **Now** (complete): Deploy code-gate.yml GitHub Actions workflow
2. **Next** (manual): Configure branch protection rules in GitHub UI (10 minutes)
3. **Verify**: Test that protection works as expected
4. **Document**: Add to CLAUDE.md that protection is live

---

## 🆘 Troubleshooting

### Issue: "Code Review Gate" check not appearing in status checks

**Solution:**
1. Wait 5 minutes for GitHub to index the workflow
2. Go to a PR → look for "Checks" tab
3. If still missing: re-run workflow manually in Actions tab
4. Then refresh branch protection settings and try adding check again

### Issue: Can't select "Code Review Gate" in required status checks

**Solution:**
1. Code-gate.yml must be in `main` branch first
2. Do one test push to `main` to trigger workflow
3. Wait for workflow to complete (green checkmark)
4. Go back to branch protection settings
5. Now "Code Review Gate" should appear in dropdown

### Issue: Force-push still works to feature branch

**Solution:**
1. Go to Settings → Branches
2. Find the rule protecting that branch
3. Verify **"Allow force pushes"** is set to ❌ NO
4. If it is, GitHub bug - try toggling off/on
5. Contact GitHub support if persists

### Issue: Developer claims rule is blocking legitimate work

**Solution:**
1. Check what violation is being reported
2. If it's a false positive in code_gate_validator.py:
   - Open issue in GitHub
   - Adjust validator rules
   - Redeploy code-gate.yml
3. For temporary bypass (ONLY for emergency):
   - Temporarily disable rule
   - Merge the code
   - Re-enable rule immediately
   - Document in PR why bypass was needed

---

## 📚 Related Documentation

- [Code Gate Validator Details](backend/scripts/code_gate_validator.py)
- [CLAUDE.md - Gate Configuration](CLAUDE.md)
- [GitHub Branch Protection Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)

---

## ⚡ Next Steps

1. **Admin:** Go to Settings → Branches → Add rule
2. **Configure:** Pattern `**`, all settings from table above
3. **Authorize:** Add "Code Review Gate" as required check
4. **Test:** Try pushing code with violations
5. **Verify:** Should be blocked by GitHub Actions

**Once complete:** All branches protected, no code violations can enter repository

---

**Created:** 2026-09-02
**Status:** Ready for implementation
**Configured by:** [Your name]
**Date implemented:** [To be filled]
