# New Developer Onboarding - 30 Minute Setup

Welcome to WROS! This is your fastest path to a working local environment.

## Prerequisites (5 min)
- [ ] Git installed & SSH key added to GitHub
- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] PostgreSQL 18 installed OR Docker available

## Step 1: Clone Repository (2 min)

```bash
git clone https://github.com/rapidtechnologiesllc-byte/WROS-Master.git
cd WROS-Master
cp .env.example .env
```

## Step 2: Database Setup (5 min)

**Using PostgreSQL directly:**
```bash
psql -U postgres
# In psql:
CREATE DATABASE onboarding_prod;
CREATE USER app_user WITH PASSWORD 'P7kQmR9xL2wJnV5sT8pM';
GRANT ALL PRIVILEGES ON DATABASE onboarding_prod TO app_user;
\q
```

**OR Using Docker:**
```bash
docker run -d --name wros-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:18
```

## Step 3: Choose Your Path

### 👨‍💻 Backend Developer (10 min)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head

# Verify
python -m uvicorn app.main:app --reload
# ✅ Visit http://localhost:8080/docs to see API docs
```

### 🎨 Frontend Developer (10 min)

```bash
cd frontend
npm install
npm start
# ✅ Opens http://localhost:3000 automatically
```

### 🤝 Careers Developer (10 min)

```bash
cd careers
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 5000
# ✅ Visit http://localhost:5000
```

## Step 4: Verify Everything Works (3 min)

```bash
# In a new terminal:
curl http://localhost:8080/health
# Expected: {"status": "healthy"}
```

## Step 5: Make Your First Commit (5 min)

```bash
# Create a feature branch
git checkout -b feature/your-feature

# Make a small change (e.g., add a comment)
# Commit it
git add .
git commit -m "feat: Your feature description"

# Push
git push origin feature/your-feature

# Create PR on GitHub
```

## ✅ You're Done!

Your environment is ready. Now read:
- **Full guide:** [`DEVELOPER-GUIDE.md`](./DEVELOPER-GUIDE.md)
- **Git workflow:** Section "Git Workflow" in DEVELOPER-GUIDE.md
- **API docs:** http://localhost:8080/docs (when backend running)

## 🚀 Next Steps

1. **Get assigned to a task** from your tech lead
2. **Follow the git workflow** in DEVELOPER-GUIDE.md
3. **Ask in Slack** if you get stuck (#wros-backend, #wros-frontend, #wros-careers)
4. **Run tests locally** before pushing
5. **Create PR and request review** from your team

## Common Issues

**Backend won't start?**
```bash
# Check database
psql -U app_user -d onboarding_prod -c "SELECT 1;"
# Should return 1
```

**Frontend build fails?**
```bash
cd frontend
rm -rf node_modules
npm install
npm start
```

**Port already in use?**
```bash
lsof -i :8080  # See what's using port
kill -9 <PID>   # Kill it
```

**Still stuck?** Check [Troubleshooting](./DEVELOPER-GUIDE.md#troubleshooting) in DEVELOPER-GUIDE.md

---

**Questions?** Slack your team lead or ask in #wros-general

**Ready to start?** See [DEVELOPER-GUIDE.md](./DEVELOPER-GUIDE.md) for detailed info.

Welcome aboard! 🎉
