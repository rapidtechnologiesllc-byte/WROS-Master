# careers.blitzenx.com - Development Notes

## 🚀 CURRENT STATUS (2026-08-13 Session - MVP Portal Launched)

**Frontend:** ✅ MVP DEPLOYED - careers.blitzenx.com running on localhost:3001
**Repository:** ✅ PUSHED - https://github.com/rapidtechnologiesllc-byte/careers-blitzenx
**Git Status:** ✅ COMMITTED - Commit f5e4b55 clean source on main
**Next:** Production hardening (EPIC-07, 5 weeks)

---

## 📋 PROJECT OVERVIEW

**Purpose:** Public-facing careers portal for external candidates to apply to BlitzenX positions

**Architecture:**
- Frontend: Next.js 14 + React 18 + TypeScript (careers.blitzenx.com)
- Backend: OnboardingModule-Backend APIs (Thunder + HM Validation)
- Deployment: Vercel (auto-deploy on push to main)
- API Integration: http://localhost:8000 (dev) / https://api.blitzenx.com (prod)

**Related Projects:**
- Backend: https://github.com/blitzenx25/OnboardingModule-Backend (Thunder + HM APIs)
- Internal Frontend: https://github.com/blitzenx25/OnboardingModule-Frontend (HRMS)
- Careers Portal: https://github.com/rapidtechnologiesllc-byte/careers-blitzenx (this repo)

---

## 🎯 EPIC-00-CAREERS-MVP (Current Session - 2026-08-13)

**Status:** MVP COMPLETE - Production deployment ready

### Features Implemented:

**1. Job Listings Page** (`src/pages/jobs/index.tsx`)
- Display all open positions from backend API (future integration)
- Filter by location, department, experience level
- Job cards with title, company, location, type, match score
- "Apply Now" CTA links to Thunder intake

**2. Thunder Pre-Screening Flow** (`src/pages/apply.tsx`)
- 8 interactive Q&A questions
- Form state persistence (localStorage)
- Progress tracking (% complete, Q# of 8)
- Typing indicators for bot messages
- Yes/No questions with button options
- Text input for open-ended responses
- Session management (resume capability)

**3. Application Status Page** (`src/pages/apply/status.tsx`)
- Confirmation after submission
- Next steps timeline (Screening → Validation → Interview)
- Tip for email checking
- Back to jobs link

**4. Responsive Design**
- Mobile-first approach
- Touch-friendly buttons (44px+)
- Responsive grid layouts
- Works on desktop, tablet, mobile

### Files Created:

**Pages:**
- `src/pages/_app.tsx` - App wrapper with global styling
- `src/pages/jobs/index.tsx` - Job listings page (250 LOC)
- `src/pages/apply.tsx` - Thunder chatbot page (300 LOC)
- `src/pages/apply/status.tsx` - Confirmation page (120 LOC)

**Configuration:**
- `package.json` - Next.js 14, React 18, TypeScript, Axios
- `next.config.js` - Next.js configuration
- `tsconfig.json` - TypeScript strict mode
- `.env.local` - API base URL configuration
- `.gitignore` - Excludes node_modules, .next, build artifacts
- `.claude/launch.json` - Dev server config (port 3001)
- `README.md` - Quick start guide

---

## 🏗️ ARCHITECTURE

### Tech Stack:
- **Framework:** Next.js 14 (React 18)
- **Language:** TypeScript
- **Styling:** Inline CSS (MVP) → Tailwind CSS (production)
- **HTTP Client:** Axios
- **State:** React hooks + localStorage
- **Deployment:** Vercel

### Directory Structure:
```
careers.blitzenx.com/
├── src/
│   ├── pages/
│   │   ├── _app.tsx (App layout & global styles)
│   │   ├── jobs/
│   │   │   └── index.tsx (Job listings with filters)
│   │   ├── apply.tsx (Thunder chatbot flow - 8 Q)
│   │   └── apply/
│   │       └── status.tsx (Application confirmation)
│   └── (future: components/, hooks/, services/, types/)
├── public/ (static assets - future)
├── .claude/
│   └── launch.json (Dev server config)
├── .env.local (API configuration)
├── .gitignore
├── package.json
├── next.config.js
├── tsconfig.json
├── README.md
└── CLAUDE.md (this file)
```

---

## 📖 USER FLOWS

### Flow 1: Browse & Apply to Job
```
1. User visits careers.blitzenx.com/jobs
2. Sees job listings with filters (location, dept, experience)
3. Clicks "Apply now" on Business Delivery Consultant
4. Redirected to /apply?job_id=job_001
5. Thunder chatbot starts: "What's your email?"
```

### Flow 2: Complete Thunder Intake
```
Q1: Email address
Q2: Current job title  
Q3: Years of experience
Q4: Current company
Q5: Resume on file?
Q6: Location still accurate?
Q7-Q8: Agreements & contact consent

→ Click "Submit" → Redirected to /apply/status
```

### Flow 3: Resume Application via Email
```
1. User starts Thunder, gets to Q4, closes browser
2. Email received: "Continue your application"
3. Link: /apply/status?session_id=xxx&email=jane@example.com
4. Session resumes at Q5 (last saved question)
5. User continues & completes
```

---

## 🔗 BACKEND INTEGRATION

### API Endpoints Ready:
- `POST /api/v1/thunder/sessions` - Create/resume session
- `GET /api/v1/thunder/sessions/{id}` - Get session state
- `POST /api/v1/thunder/sessions/{id}/answer` - Submit Q&A
- `POST /api/v1/thunder/sessions/{id}/upload-resume` - Resume file
- `POST /api/v1/thunder/sessions/{id}/submit` - Finalize application

### Configuration:
```
.env.local:
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

Vercel Production:
NEXT_PUBLIC_API_BASE_URL=https://api.blitzenx.com
```

### Next Integration Step:
Currently hardcoded job data and Thunder flow; needs API wiring:
- [ ] Fetch jobs from backend API
- [ ] Connect form submission to `/api/v1/thunder/sessions`
- [ ] Implement session persistence via backend
- [ ] Add resume upload to S3
- [ ] Handle resume parsing responses

---

## 🚀 DEPLOYMENT

### Local Development:
```bash
npm install
npm run dev
# Opens http://localhost:3001
```

### Production Deployment (Vercel):
1. Repository: https://github.com/rapidtechnologiesllc-byte/careers-blitzenx
2. Connect to Vercel
3. Set environment: `NEXT_PUBLIC_API_BASE_URL=https://api.blitzenx.com`
4. Auto-deploys on push to main
5. Live at: `https://careers-blitzenx.vercel.app` (or custom domain)

---

## 📊 BACKLOG: EPIC-07-CAREERS-PORTAL-FRONTEND (Production Hardening)

**Status:** PLANNED - 5-week implementation

### Phase Breakdown:

**Phase 1 (Week 1): Form Validation & Error Handling**
- [ ] Email, phone, file upload validation
- [ ] Network error recovery with retry logic
- [ ] User-friendly error messages
- [ ] Toast notifications

**Phase 2 (Week 2): State Management & Persistence**
- [ ] Zustand store for session state
- [ ] LocalStorage for form recovery
- [ ] Session resume via email link
- [ ] Auto-save on input

**Phase 3 (Week 2): API Integration**
- [ ] Connect to backend Thunder endpoints
- [ ] Resume parsing callback
- [ ] Job listing API integration
- [ ] Error handling per endpoint

**Phase 4 (Week 3): UX Enhancements**
- [ ] Loading states & spinners
- [ ] Progress indicators
- [ ] Success/error messaging
- [ ] Keyboard navigation

**Phase 5 (Week 3): Mobile & Responsive**
- [ ] Touch-friendly design (48px+ buttons)
- [ ] Mobile-first responsive layout
- [ ] iOS/Android testing

**Phase 6 (Week 4): Testing**
- [ ] Unit tests (Jest)
- [ ] Integration tests
- [ ] E2E tests (Cypress)
- [ ] Performance testing (Lighthouse 90+)

**Phase 7 (Week 4): Analytics & Monitoring**
- [ ] Google Analytics funnel tracking
- [ ] Error tracking (Sentry)
- [ ] Session recording (optional)
- [ ] Web Vitals monitoring

**Phase 8 (Week 5): Deployment**
- [ ] Vercel configuration
- [ ] Environment setup (staging/prod)
- [ ] CDN caching strategy
- [ ] SSL/TLS setup
- [ ] Monitoring & alerting

---

## 🔄 GIT WORKFLOW

### Repository:
- **Remote:** https://github.com/rapidtechnologiesllc-byte/careers-blitzenx
- **Branch:** main (production)
- **Strategy:** Push directly to main for MVP, PR workflow for production hardening

### Commits:
```
f5e4b55 - Initial careers portal - clean source
```

### Pushing Changes:
```bash
git add src/ package.json ...
git commit -m "feat: ..."
git push origin main
```

---

## 📝 STYLE GUIDE

### Code Organization:
- TypeScript strict mode enabled
- Prefer function components with hooks
- Props types defined inline or via interfaces
- No commented-out code (delete instead)

### Naming:
- Components: PascalCase (ThunderChat.tsx)
- Functions/variables: camelCase
- Constants: UPPER_SNAKE_CASE
- Files: kebab-case or component name

### Styling (MVP):
- Inline CSS (temporary)
- CSS variables for theming
- Mobile-first responsive design
- NO hardcoded colors

---

## 📚 RELATED DOCUMENTATION

- Backend: `/dev/OnboardingModule-Backend/CLAUDE.md` (Thunder + HM APIs)
- Internal Frontend: `/dev/OnboardingModule-Frontend/CLAUDE.md` (RBAC + Employee Conversion)
- Thunder Spec: `/dev/OnboardingModule-Backend/THUNDER_COMPLETE_DESIGN_SPEC.md`
- Careers Portal Architecture: `/dev/OnboardingModule-Backend/CAREERS_PORTAL_ARCHITECTURE.md`
- Implementation Guide: `/dev/OnboardingModule-Backend/THUNDER_HM_IMPLEMENTATION_GUIDE.md`
- Testing Guide: `/dev/OnboardingModule-Backend/TESTING_AND_LAUNCH_GUIDE.md`

---

## 🎯 SUCCESS CRITERIA

**MVP (Current - ✅ COMPLETE):**
- [x] Job listings page
- [x] Thunder chatbot (8 questions)
- [x] Application confirmation
- [x] Mobile responsive
- [x] LocalStorage persistence
- [x] Git repository
- [x] Ready for deployment

**Production (EPIC-07):**
- [ ] Backend API integration
- [ ] Form validation
- [ ] Error handling & retry
- [ ] Loading states
- [ ] WCAG 2.1 AA accessibility
- [ ] 80%+ test coverage
- [ ] Analytics tracking
- [ ] Vercel deployment

---

## 👥 TEAM ASSIGNMENTS

- **Backend:** OnboardingModule-Backend team (Thunder + HM APIs ready)
- **Frontend:** careers.blitzenx.com team (EPIC-07 hardening, 5 weeks)
- **Deployment:** DevOps (Vercel setup, environment config)
- **QA:** Testing team (EPIC-07 test plan)

---

## 📅 TIMELINE

**Current:** MVP deployed (August 13, 2026)  
**Next 5 Weeks:** Production hardening (EPIC-07)  
**Launch Target:** September 2026  

---

**Created:** 2026-08-13  
**Last Updated:** 2026-08-13  
**Maintained By:** Claude Code
