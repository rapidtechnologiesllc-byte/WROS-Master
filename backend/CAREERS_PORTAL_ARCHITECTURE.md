# careers.blitzenx.com Frontend & Portal Architecture

**Status:** Architecture & Specification (Ready for Frontend Team)  
**Created:** 2026-08-13  
**Tech Stack:** React 18 + Next.js, Tailwind CSS, TypeScript  
**Backend Integration:** OnboardingModule-Backend APIs (Thunder + HM Validation)

---

## 🎯 Overview

careers.blitzenx.com is a **separate, customer-facing careers portal** distinct from the internal HRMS (hrms.blitzenx.com). It hosts:

1. **Thunder Pre-Screening** - Candidate intake chatbot
2. **Job Listings** - Browse open positions
3. **Candidate Application Flow** - Resume upload, screening questions
4. **Application Status** - Track application progress
5. **Public Company Info** - About us, culture, testimonials

### Key Principles:
- **No authentication** (external candidates)
- **Mobile-first** responsive design
- **Progress persistence** (candidate can return via email link)
- **Single-purpose UX** (focused on application, not browsing)
- **Fast load times** (hosted on CDN, cached job listings)

---

## 📐 Architecture Diagram

```
careers.blitzenx.com (Next.js Frontend)
├─ Job Listings Page
│  ├─ GET /api/v1/jobs (Backend)
│  └─ Display with filters (location, department, etc)
│
├─ Job Detail Page
│  ├─ GET /api/v1/jobs/{job_id}
│  └─ "Apply Now" → Thunder Session Create
│
├─ Thunder Chat Flow (Main UI)
│  ├─ POST /api/v1/thunder/sessions (Create/Resume)
│  ├─ GET /api/v1/thunder/sessions/{session_id} (Fetch state)
│  ├─ POST /api/v1/thunder/sessions/{session_id}/answer (Submit Q&A)
│  ├─ POST /api/v1/thunder/sessions/{session_id}/upload-resume (File upload)
│  └─ POST /api/v1/thunder/sessions/{session_id}/submit (Finalize)
│
├─ Application Status Dashboard
│  ├─ Query params: ?session_id=xxx&email=xxx (resume link from email)
│  └─ Shows progress, HM validation status, interview info
│
└─ Static Pages
   ├─ About Us
   ├─ Culture & Values
   ├─ Benefits
   ├─ FAQ
   └─ Contact

Backend (OnboardingModule-Backend)
├─ /api/v1/thunder/* (Thunder endpoints)
├─ /api/v1/hiring-manager-validations/* (HM validation - internal only)
├─ /api/v1/jobs/* (Job listings - read-only for external)
└─ /api/v1/candidates/* (Candidate CRUD)
```

---

## 🏗️ Project Structure

```
careers.blitzenx.com/
├── .env.local                  # API_BASE_URL, env-specific config
├── .env.example
├── .gitignore
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
├── package.json
│
├── public/
│   ├── logo.png
│   ├── favicon.ico
│   ├── images/
│   │   ├── hero-bg.jpg
│   │   ├── culture-1.jpg
│   │   └── team-photo.jpg
│   └── documents/
│       └── employee-handbook.pdf
│
├── src/
│   ├── pages/
│   │   ├── _app.tsx              # Next.js app wrapper
│   │   ├── _document.tsx
│   │   ├── index.tsx             # Homepage / Job listings
│   │   ├── jobs/
│   │   │   ├── [id].tsx          # Job detail page
│   │   │   └── index.tsx
│   │   ├── apply/
│   │   │   ├── [[...slug]].tsx   # Thunder chat flow (catch-all)
│   │   │   └── status.tsx        # Application status
│   │   ├── about.tsx
│   │   ├── culture.tsx
│   │   ├── benefits.tsx
│   │   ├── faq.tsx
│   │   ├── contact.tsx
│   │   └── api/
│   │       └── health.ts         # Health check (no-op)
│   │
│   ├── components/
│   │   ├── Layout.tsx
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   ├── Navbar.tsx
│   │   ├── SEO.tsx
│   │   │
│   │   ├── Thunder/
│   │   │   ├── ThunderChat.tsx           # Main chat UI
│   │   │   ├── ChatMessage.tsx           # Message bubble
│   │   │   ├── QuestionRenderer.tsx      # Dynamic Q type rendering
│   │   │   ├── FileUploader.tsx          # Resume upload
│   │   │   ├── ProgressBar.tsx           # Session progress
│   │   │   ├── ConversationHistory.tsx   # Q&A summary
│   │   │   └── ResumePreview.tsx         # Resume preview
│   │   │
│   │   ├── Jobs/
│   │   │   ├── JobCard.tsx
│   │   │   ├── JobList.tsx
│   │   │   ├── JobFilters.tsx
│   │   │   └── JobDetail.tsx
│   │   │
│   │   └── Common/
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       ├── Modal.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   │
│   ├── services/
│   │   ├── api.ts                # Axios instance + interceptors
│   │   ├── thunder.ts            # Thunder API calls
│   │   ├── jobs.ts               # Job API calls
│   │   ├── candidates.ts         # Candidate API calls
│   │   └── storage.ts            # LocalStorage helpers
│   │
│   ├── hooks/
│   │   ├── useThunderSession.ts  # Session state management
│   │   ├── useJobs.ts
│   │   ├── useAsync.ts           # Generic async hook
│   │   └── useLocalStorage.ts
│   │
│   ├── types/
│   │   ├── thunder.ts
│   │   ├── jobs.ts
│   │   ├── candidates.ts
│   │   └── common.ts
│   │
│   ├── utils/
│   │   ├── validation.ts         # Form validation
│   │   ├── formatting.ts         # Date, currency formatting
│   │   ├── tracking.ts           # Google Analytics, Mixpanel
│   │   └── constants.ts
│   │
│   └── styles/
│       ├── globals.css
│       ├── thunder.module.css
│       └── jobs.module.css
│
├── tests/
│   ├── unit/
│   │   ├── thunder.test.tsx
│   │   └── jobs.test.tsx
│   └── integration/
│       └── e2e.test.tsx
│
└── docs/
    ├── ARCHITECTURE.md
    ├── DEPLOYMENT.md
    └── TESTING.md
```

---

## 🎨 UI/UX Design

### Thunder Chat Interface (Main Feature)

**Q&A Display Pattern:**
```
User Avatar (Left)  [Q: "What's your experience level?"]

                                        [A: "8 years"] (Right)
Assistant Avatar

[Q: "Great! What's your current job title?"]

[Input field or options below question]
```

**Question Types Supported:**
- `text` - Text input field
- `yes_no` - Yes/No buttons
- `yes_no_maybe` - Yes/No/Maybe buttons
- `dropdown` - Select from list (locations)
- `file_upload` - Resume uploader with drag-drop
- `number` - Numeric input (years of experience)

**Key UI Components:**

#### 1. ThunderChat Component
```tsx
export interface ThunderChatProps {
  sessionId: string;
  onSessionComplete: (candidateId: string) => void;
  onSessionError: (error: string) => void;
}

// Features:
// - Auto-scroll to latest message
// - Typing indicators ("Assistant is thinking...")
// - Form persistence (auto-save drafts)
// - Back button with unsaved prompt
// - Progress bar (Completion %)
// - Pause session button
// - Keyboard shortcuts (Enter to send)
```

#### 2. ProgressBar Component
```tsx
// Shows:
// - Current question (e.g., "Question 4 of 12")
// - Completion percentage (33%)
// - Estimated time remaining
// - Visual bar filling as candidate progresses
```

#### 3. ResumePreview Component
```tsx
// If resume on file:
// - "Resume on file as of [DATE]"
// - Display resume thumbnail/preview
// - "Update resume" button
// - "Use existing" button
```

### Jobs Listing Page

**Filters:**
- Location (dropdown with existing location list)
- Department
- Experience Level
- Job Type (Full-time, Contract, Internship)
- Salary Range

**Job Card:**
```
[Company Logo] [Job Title]
Department | Location | Experience
$X - $Y LPA | Full-time
"Apply Now" CTA → Thunder Session Start
```

### Application Status Page

**Query-based resume:**
```
https://careers.blitzenx.com/apply/status?session_id=xxx&email=jane@example.com
```

**Shows:**
- Session progress (where they left off)
- Option to continue application
- If submitted: "Under Review" status
- If HM validation: "Manager Review in Progress"
- If interview scheduled: Interview details

---

## 🔌 API Integration

### Thunder Session Flow (Careers → Backend)

**1. Create/Resume Session**
```typescript
// careers.blitzenx.com/apply/
POST /api/v1/thunder/sessions
{
  "candidate_email": "jane@example.com",
  "device_type": "mobile|desktop",
  "utm_source": "email_campaign"
}

// Response:
{
  "session_id": "sess_abc123",
  "status": "STARTED|IN_PROGRESS",
  "last_question_reached": "Q1",
  "completion_percentage": 0,
  "form_state": {}
}
```

**2. Submit Answer**
```typescript
POST /api/v1/thunder/sessions/{session_id}/answer
{
  "question": "Q1",
  "response": "jane.smith@example.com",
  "time_taken_seconds": 15
}

// Response:
{
  "status": "ok",
  "next_question": "Q2",
  "completion_percentage": 8
}
```

**3. Upload Resume**
```typescript
POST /api/v1/thunder/sessions/{session_id}/upload-resume
(multipart/form-data with file)

// Response:
{
  "status": "success",
  "resume_url": "s3://...",
  "parsed_data": {
    "skills": ["Python", "Go"],
    "experience_years": 5
  }
}
```

**4. Submit Application**
```typescript
POST /api/v1/thunder/sessions/{session_id}/submit

// Response:
{
  "status": "submitted",
  "candidate_id": "cand_123",
  "job_matches": [
    {
      "job_id": "job_001",
      "title": "Senior Engineer",
      "match_score": 0.92
    }
  ]
}
```

### Jobs API

**List Jobs (with filters)**
```typescript
GET /api/v1/jobs?location=SF&dept=Engineering&limit=20
```

**Get Job Detail**
```typescript
GET /api/v1/jobs/{job_id}
```

---

## 📊 State Management

### Using React Hooks + Context API (or Redux if needed)

```typescript
// ThunderContext
export interface ThunderContextType {
  sessionId: string;
  candidateEmail: string;
  status: SessionStatus;
  currentQuestion: string;
  formResponses: Record<string, any>;
  resumeUrl?: string;
  completionPercentage: number;
  
  createSession: (email: string) => Promise<void>;
  submitAnswer: (q: string, response: any) => Promise<void>;
  uploadResume: (file: File) => Promise<void>;
  submitApplication: () => Promise<SubmitResponse>;
  pauseSession: () => void;
  resumeSession: (sessionId: string) => Promise<void>;
}
```

### LocalStorage Strategy

Store in browser:
```typescript
{
  "thunder_session": {
    "sessionId": "sess_abc123",
    "candidateEmail": "jane@example.com",
    "formResponses": { /* ... */ },
    "savedAt": "2026-08-13T10:30:00Z"
  }
}
```

This allows "resume from browser" even if server session expires.

---

## 🎯 Key Features & Implementation

### Feature 1: Resume Persistence

**Scenario:** Candidate closes browser at Q4, returns next day via email link.

**Implementation:**
```typescript
// careers.blitzenx.com/apply/status?session_id=xxx&email=jane@example.com

// Fetch session from backend
const session = await getThunderSession(sessionId);

// Resume at Q4
setCurrentQuestion(session.last_question_reached);
setFormResponses(session.form_responses);
```

### Feature 2: Form State Auto-Save

**Trigger on every keystroke** (debounced):
```typescript
useEffect(() => {
  const timer = setTimeout(() => {
    localStorage.setItem('thunder_draft', JSON.stringify(formResponses));
  }, 1000);
  return () => clearTimeout(timer);
}, [formResponses]);
```

### Feature 3: Conditional Question Rendering

**Work auth question only for US jobs:**
```typescript
const showWorkAuthQuestion = (
  currentQuestion === "Q8" &&
  jobLocation?.includes("US")
);

if (!showWorkAuthQuestion) {
  // Skip Q8, go to Q9
  return getNextQuestion("Q8");
}
```

### Feature 4: File Upload with Drag-Drop

```typescript
// FileUploader.tsx
const handleDrop = (e: React.DragEvent) => {
  e.preventDefault();
  const files = e.dataTransfer.files;
  uploadResume(files[0]);
};

const uploadResume = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(
    `/api/v1/thunder/sessions/${sessionId}/upload-resume`,
    { method: 'POST', body: formData }
  );
};
```

### Feature 5: Progress Tracking & Analytics

**Track user behavior:**
```typescript
// useTracking.ts
const trackEvent = (event: string, data: any) => {
  if (window.gtag) {
    window.gtag('event', event, data);
  }
  // Also send to backend for logging
  logEvent(event, data);
};

// Usage:
trackEvent('thunder_session_started', { email: candidateEmail });
trackEvent('question_answered', { question: 'Q1', time_seconds: 15 });
trackEvent('resume_uploaded', { file_size_kb: 245 });
trackEvent('application_submitted', { job_matches_count: 3 });
```

---

## 🚀 Deployment Strategy

### Frontend Hosting

**Option 1: Vercel (Recommended)**
- Deploy Next.js app directly
- Automatic CI/CD on push
- Built-in CDN
- $0 startup cost
- `vercel deploy`

**Option 2: AWS S3 + CloudFront**
- Build static site: `next export` or `next build`
- Upload to S3
- Cache via CloudFront
- ~$5/month

### Environment Configuration

```env
# .env.production
NEXT_PUBLIC_API_BASE_URL=https://api.blitzenx.com
NEXT_PUBLIC_APP_NAME=BlitzenX Careers
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=G-XXXXX
NEXT_PUBLIC_SENTRY_DSN=https://...
```

### DNS

```
careers.blitzenx.com → Vercel (or S3 + CloudFront)
api.blitzenx.com → OnboardingModule-Backend (existing)
hrms.blitzenx.com → Internal HRMS (existing)
```

---

## 📋 Implementation Roadmap

### Phase 1: MVP (Week 1-2)
- [ ] Setup Next.js project
- [ ] Create Thunder Chat component
- [ ] Implement basic Q&A flow
- [ ] Resume form state persistence
- [ ] File upload (resume)
- [ ] Session submission

### Phase 2: Enhancement (Week 3-4)
- [ ] Job listings page
- [ ] Job detail page
- [ ] Application status dashboard
- [ ] Email resume link (session recovery)
- [ ] Progress analytics

### Phase 3: Polish (Week 5-6)
- [ ] Mobile responsiveness
- [ ] Accessibility (WCAG 2.1)
- [ ] Error handling & fallbacks
- [ ] Performance optimization
- [ ] SEO (meta tags, sitemaps)

### Phase 4: Launch (Week 7-8)
- [ ] User acceptance testing
- [ ] Staging environment
- [ ] Production deployment
- [ ] Monitoring & alerting
- [ ] Support documentation

---

## 🔒 Security Considerations

1. **CORS** - Only allow careers.blitzenx.com to call backend APIs
2. **Rate Limiting** - Prevent spam applications (10 per IP per hour)
3. **Input Validation** - Validate all form inputs before sending to backend
4. **File Upload** - Restrict to PDF/DOCX, max 5MB, scan for malware
5. **HTTPS Only** - careers.blitzenx.com must be HTTPS
6. **Session Tokens** - Generate secure session IDs (use UUIDs)

---

## 📱 Mobile Optimization

- Touch-friendly buttons (44px minimum)
- Stacked layout on mobile
- Large text inputs (no 16px font zoom issue)
- Avoid hover states (use active/focus instead)
- Test on iOS Safari + Android Chrome

---

## Testing Strategy

### Unit Tests
```bash
npm run test
# Test components: ThunderChat, FileUploader, JobCard, etc.
```

### Integration Tests
```bash
npm run test:integration
# Test Thunder flow end-to-end
# Test job listing → apply → Thunder → submit
```

### E2E Tests (Cypress)
```bash
npm run test:e2e
# careers.blitzenx.com/apply → complete Thunder → check status page
```

---

## 📦 Dependencies

```json
{
  "next": "^14.0.0",
  "react": "^18.2.0",
  "axios": "^1.6.0",
  "tailwindcss": "^3.3.0",
  "typescript": "^5.2.0",
  "zustand": "^4.4.0",
  "react-hook-form": "^7.47.0",
  "zod": "^3.22.0"
}
```

---

## 🎓 Next Steps

1. **Setup careers.blitzenx.com** Next.js project
2. **Create ThunderChat component** with dynamic question rendering
3. **Implement API integration** with Thunder endpoints
4. **Build job listings** page and detail views
5. **Test end-to-end** flow
6. **Deploy to production** (careers.blitzenx.com)

---

**Status:** 🟢 Ready for Frontend Team to Build  
**Backend Support:** All APIs ready (Thunder + HM Validation)  
**Timeline:** 6-8 weeks for complete implementation and launch
