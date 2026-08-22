# 🚀 HOW TO RUN BU SCOPING TESTS - STEP BY STEP

**Status:** Tests Created ✅ | Ready to Execute  
**Prerequisites:** Backend running + Test users created  

---

## 📋 PREREQUISITES

### 1. ✅ Backend API Running
```bash
# Terminal 1: Start backend
cd OnboardingModule-Backend
npm start
# Should run on http://localhost:8080
```

### 2. ✅ Frontend App Running
```bash
# Terminal 2: Start frontend
cd OnboardingModule-Frontend-main
npm start
# Should run on http://localhost:3000
```

### 3. ✅ Database Connected
- Ensure PostgreSQL is running
- Database `wros_dev` is created
- All migrations are run

---

## 🔧 SETUP: Create Test Users

You have **2 options**:

### **Option A: Use Python Script (Recommended - 2 minutes)**

```bash
cd OnboardingModule-Frontend-main

# Run the test data creation script
python3 create_test_data.py
```

This will create:
- ✅ 2 Business Units (NA, EU)
- ✅ 10 Test Users with roles
- ✅ All credentials configured

### **Option B: Manual SQL (Advanced - 5 minutes)**

```bash
cd OnboardingModule-Backend

# Connect to PostgreSQL
psql -U postgres -d wros_dev

# Run the SQL script
\i create_test_users.sql
```

**Note:** You'll need to hash the passwords. Use bcrypt:
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'RecruiterNA1@123', bcrypt.gensalt()).decode())"
```

---

## ✅ Test Users Created

After setup, you'll have these credentials:

### **BU 1 (North America) Users**
```
BU Head:
  buhead.na@blitzenx.com / BUHeadNA@123

Recruiters:
  recruiter.na.1@blitzenx.com / RecruiterNA1@123
  recruiter.na.2@blitzenx.com / RecruiterNA2@123

HR Manager:
  hr.na.1@blitzenx.com / HRNA1@123

Hiring Manager:
  hm.na.1@blitzenx.com / HMNA1@123
```

### **BU 2 (Europe) Users**
```
BU Head:
  buhead.eu@blitzenx.com / BUHeadEU@123

Recruiters:
  recruiter.eu.1@blitzenx.com / RecruiterEU1@123
  recruiter.eu.2@blitzenx.com / RecruiterEU2@123

HR Manager:
  hr.eu.1@blitzenx.com / HREU1@123

Hiring Manager:
  hm.eu.1@blitzenx.com / HMEU1@123
```

---

## 🎬 RUN THE TESTS

### **Option 1: Run BU Scoping Tests Only**

```bash
npm run test:e2e -- tests/e2e/bu-scoping.spec.js
```

### **Option 2: Run with Visible Browser (Watch Execution)**

```bash
npx playwright test tests/e2e/bu-scoping.spec.js --headed
```

This opens a real browser where you can:
- 👁️ Watch the test execute in real-time
- 🔍 See login, navigation, form filling
- ✅ See pass/fail results

### **Option 3: Run All Tests**

```bash
npm run test:e2e
```

This runs all 120+ tests:
- 7 User role tests
- 15 BU scoping tests
- All workflows

### **Option 4: Run with Debug Mode**

```bash
npx playwright test tests/e2e/bu-scoping.spec.js --debug
```

This opens Playwright Inspector where you can:
- ⏭️ Step through each line
- 🔎 Inspect elements
- 🖱️ Control the browser manually

---

## 📊 EXPECTED TEST FLOW

When you run the tests, here's what should happen:

### **Phase 1: BU 1 Recruiter Creates Candidate**
```
✅ Login as recruiter.na.1@blitzenx.com
✅ Navigate to Add Candidate
✅ Create candidate: "John Software Engineer"
✅ Assign to BU-001 (North America)
✅ Candidate shows BU badge: "NA"
```

### **Phase 2: BU 2 Recruiter Can't See Candidate**
```
✅ Login as recruiter.eu.1@blitzenx.com
✅ Navigate to Candidates
❌ "John Software Engineer" NOT VISIBLE (BU SCOPING WORKING!)
✅ Only sees BU-002 candidates
```

### **Phase 3: Interview Rejected**
```
✅ Login as hm.na.1@blitzenx.com (Hiring Manager)
✅ Navigate to Interviews
✅ Click Reject Interview
✅ Candidate status: REJECTED
✅ BU assignment REMOVED
```

### **Phase 4: Candidate Now Visible to BU 2**
```
✅ Login as recruiter.eu.1@blitzenx.com
✅ Navigate to Candidates
✅ "John Software Engineer" NOW VISIBLE (BU SCOPING REMOVED!)
✅ No BU badge (in pool now)
✅ Recruiter can interact with candidate
```

---

## 🔍 VIEW TEST RESULTS

After tests complete:

```bash
# View HTML report
npm run test:e2e:report
```

The report shows:
- ✅/❌ Each test result
- 📸 Screenshots of failures
- 🎥 Videos of failed tests
- ⏱️ Execution times
- 📊 Summary statistics

---

## 🐛 IF TESTS FAIL

### **1. Check Backend is Running**
```bash
# Test backend API
curl http://localhost:8080/health
# Should return 200 OK
```

### **2. Check Frontend is Running**
```bash
# Test frontend
curl http://localhost:3000
# Should return HTML
```

### **3. Verify Test Users Exist**
```bash
# Query database
psql -U postgres -d wros_dev
SELECT email, role, business_unit_id FROM users WHERE email LIKE 'recruiter%';
```

### **4. Check Test User Passwords**
```bash
# Login manually in browser to test credentials
# Go to http://localhost:3000
# Try: recruiter.na.1@blitzenx.com / RecruiterNA1@123
```

### **5. View Test Debug Output**
```bash
# Run tests with verbose output
npm run test:e2e -- tests/e2e/bu-scoping.spec.js --verbose
```

---

## 📝 QUICK START (3 Steps)

```bash
# Step 1: Create test data
python3 create_test_data.py

# Step 2: Run tests with browser visible
npx playwright test tests/e2e/bu-scoping.spec.js --headed

# Step 3: View results
npm run test:e2e:report
```

That's it! 🎉

---

## 📚 COMPLETE TEST SUITE

If setup is successful, you can also run:

```bash
# All role-based tests
npm run test:e2e

# Specific roles
npm run test:e2e:candidate
npm run test:e2e:recruiter
npm run test:e2e:employee
npm run test:e2e:buhead
npm run test:e2e:partner
npm run test:e2e:cfo
npm run test:e2e:ceo
```

---

## ✨ What This Tests

✅ **BU Isolation:** Candidates assigned to BU 1 hidden from BU 2  
✅ **Permission Enforcement:** Recruiters only see their BU's data  
✅ **Workflow Logic:** Status changes remove BU scoping  
✅ **Data Consistency:** Visibility updates across all users  
✅ **Role-Based Access:** Each role sees appropriate data  

---

## 🎯 SUCCESS CRITERIA

All tests pass when:

- ✅ BU 1 recruiter can create and assign candidates to BU 1
- ✅ BU 2 recruiter **cannot** see BU 1 candidate (before rejection)
- ✅ Hiring manager can reject interview
- ✅ Candidate status changes to REJECTED
- ✅ BU 2 recruiter **can now** see candidate (after rejection)
- ✅ No BU badge on released candidate

---

## 📞 TROUBLESHOOTING

| Issue | Solution |
|-------|----------|
| Tests timeout | Check backend/frontend running |
| Login fails | Verify test users exist in DB |
| Candidate not visible | Check BU assignment in DB |
| Rejection fails | Verify hiring manager role |
| Tests pass but no output | Run with `--reporter=html` |

---

**Ready to test? Run this:**
```bash
python3 create_test_data.py && npx playwright test tests/e2e/bu-scoping.spec.js --headed
```

Good luck! 🚀
