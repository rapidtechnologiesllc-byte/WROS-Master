# CI/CD Deployment Setup Guide

## Overview

This guide walks through setting up automated CI/CD deployment to production via GitHub Actions. The workflows:

1. **Test** — Run full test suite + linting
2. **Build** (frontend only) — Compile React app
3. **Deploy** — SSH into production, pull code, install deps, restart services
4. **Smoke Test** — Verify endpoints are responding
5. **Rollback** — Automatic rollback if deployment fails

## Prerequisites

Ask CloudMinister for these details (if not already provided):

- [ ] **Production Server Hostname/IP** — e.g. `prod.example.com` or `203.0.113.42`
- [ ] **SSH Key** — Private key for `HRMS` user (or generate one)
- [ ] **Passwordless Sudo** — Confirm `HRMS` user can run:
  - Backend: `sudo pm2 restart onboarding-backend` (backend only)
  - Frontend: `sudo systemctl reload nginx` or `sudo service nginx reload` (frontend only)

## Step 1: Set Up GitHub Secrets

Both repositories need the same secrets. Go to:

**Backend:** https://github.com/blitzenx25/OnboardingModule-Backend/settings/secrets/actions
**Frontend:** https://github.com/blitzenx25/OnboardingModule-Frontend/settings/secrets/actions

Click **"New repository secret"** and add:

### Required Secrets

| Secret Name | Value | Example |
|---|---|---|
| `PROD_SERVER_HOST` | Production server hostname/IP | `prod.example.com` or `203.0.113.42` |
| `PROD_USER` | SSH username | `HRMS` |
| `PROD_SSH_KEY` | Private SSH key (multiline) | `-----BEGIN OPENSSH PRIVATE KEY-----`... |

### How to generate SSH key (if needed)

On your local machine:

```bash
# Generate RSA key
ssh-keygen -t rsa -b 4096 -f ~/.ssh/prod_deploy_key -N ""

# View private key (paste this as PROD_SSH_KEY secret)
cat ~/.ssh/prod_deploy_key

# Send public key to CloudMinister to add to HRMS user's authorized_keys
cat ~/.ssh/prod_deploy_key.pub
```

Then have CloudMinister add the public key to `/home/HRMS/.ssh/authorized_keys` on the production server.

## Step 2: Test Secrets (Optional)

Create a test workflow to verify secrets are accessible:

```bash
# In either repo, push this tiny change and watch it fail gracefully
# if a secret is missing (GitHub will show which one)
```

## Step 3: Deploy Triggers

The workflows run automatically on **every push to `main`**. To deploy:

```bash
git push origin main
```

Watch the deployment:
1. Go to **Actions** tab on GitHub
2. Click the **"Deploy Backend to Production"** or **"Deploy Frontend to Production"** workflow run
3. Monitor each step:
   - ✅ Tests pass
   - ✅ SSH connection succeeds
   - ✅ Code pulls and installs
   - ✅ Services restart
   - ✅ Health checks pass
   - ✅ Deployment complete

## Step 4: Understand Rollback

If deployment fails at **any stage**:

1. **Health check fails** → Previous Git commit is restored
2. **Backend restart fails** → PM2 reverts to previous version
3. **Frontend reload fails** → Previous build directory is restored

The previous version is automatically kept in:
- Backend: `/tmp/backend-backup-[timestamp]`
- Frontend: `/tmp/frontend-backup-[timestamp]`

## Monitoring & Alerts

### View Deployment Status

**GitHub Actions Dashboard:**
- Backend: https://github.com/blitzenx25/OnboardingModule-Backend/actions
- Frontend: https://github.com/blitzenx25/OnboardingModule-Frontend/actions

### View Live Server Logs (Manual)

SSH to production and check logs:

```bash
# Backend logs (PM2)
ssh HRMS@prod.example.com
pm2 logs onboarding-backend

# Frontend logs (Nginx)
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Smoke Tests Explained

The workflows run **health checks** after deployment:

### Backend Smoke Test
```bash
curl http://localhost:8080/health
# Expected response: {"status":"healthy"}
```

### Frontend Smoke Test
```bash
curl http://prod.example.com/
# Expected: HTML response with "WROS" in the page
```

If **both** fail, deployment automatically rolls back.

## Common Issues

| Issue | Fix |
|---|---|
| **SSH key rejected** | Check `PROD_SSH_KEY` secret is exact private key (no copy/paste errors) |
| **Permission denied** | Confirm HRMS user's `authorized_keys` has the public key |
| **Passwordless sudo fails** | Ask CloudMinister to add HRMS to sudoers for pm2/nginx commands |
| **Alembic migration fails** | Backend won't restart until migrations complete; check DB schema |
| **Nginx reload fails** | Nginx config might be invalid; check `/etc/nginx/nginx.conf` syntax |

## Disabling CI/CD (Emergency)

If you need to pause auto-deployments:

1. Go to **Settings** → **Branches** → **main** → **Require status checks to pass before merging**
2. Uncheck the workflow (or delete `.github/workflows/deploy.yml` from main)

## Next Steps

1. ✅ Ask CloudMinister for production server details (hostname, SSH setup)
2. ✅ Generate SSH key pair
3. ✅ Have CloudMinister add public key to HRMS's authorized_keys
4. ✅ Add 3 secrets to GitHub (PROD_SERVER_HOST, PROD_USER, PROD_SSH_KEY)
5. ✅ Test by pushing a small change to main
6. ✅ Monitor the first deployment in GitHub Actions

That's it — CI/CD is fully automated from here on.
