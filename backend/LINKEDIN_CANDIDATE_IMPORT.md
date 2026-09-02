# LinkedIn Candidate Import Workflow

**Status:** ✅ IMPLEMENTED - Ready for Apollo MCP authentication
**Commit:** f775bad
**Branch:** claude/linkedin-candidate-wros-mompvd
**Scope:** LinkedIn URL → Apollo enrichment → Thunder autonomous outreach

---

## Overview

This workflow enables rapid candidate sourcing from LinkedIn with built-in quality gates:

1. **Input:** LinkedIn profile URL only (what user has when viewing a prospect)
2. **Enrich:** Apollo.io extracts email, phone, company, title, Open to Work status
3. **Gate:** ONLY import if candidate marked "Open to Work" (high-priority filter)
4. **Duplicate Check:** Email OR phone match prevents duplicates
5. **Create:** Real Candidate record (no staging - LinkedIn is pre-qualified)
6. **Consent:** Auto-record WhatsApp consent (LinkedIn profile = implied consent)
7. **Thunder:** Autonomous loop picks up candidate within 5 minutes for outreach

**Result:** Candidate ready for Thunder's autonomous qualifying flow. No manual recruiter clicks needed.

---

## Use Case: You Found Prabhu on LinkedIn

### What You Have
- LinkedIn profile link: https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707
- Email from LinkedIn: iyer.prabhu@gmail.com (optional - API will enrich)

### What Happens
```
Step 1: POST /candidate/import/linkedin
{
  "linkedin_url": "https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707"
}

Step 2: Backend parses URL → "prabhu-ananthanarayanan-989a707"

Step 3: Apollo.io enrichment (requires OAuth via claude.ai connectors)
Response includes:
- email: iyer.prabhu@gmail.com
- phone: +1-555-0123456
- full_name: Prabhu Ananthanarayanan
- company: TechCorp Inc
- title: Senior Software Engineer
- open_to_work: true ← CRITICAL GATE

Step 4: Gate check
IF open_to_work == false → HTTPException 403 "Candidate not open to work"
IF open_to_work == true → Continue to Step 5

Step 5: Duplicate check
Existing candidate found? → HTTPException 409 "Duplicate exists"
New candidate? → Create candidate record

Step 6: Create candidate
- candidateID: auto-generated UUID
- email: iyer.prabhu@gmail.com
- phone: +1-555-0123456
- linkedin_url: https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707
- candidate_source: "linkedin_import"
- status: "NEW"

Step 7: Record consent
ConsentRecord created:
- subject_id: candidateID
- consent_type: "whatsapp_outreach"
- consent_given: true

Step 8: Return success
{
  "status": "SUCCESS",
  "candidate_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "iyer.prabhu@gmail.com",
  "phone": "+1-555-0123456",
  "full_name": "Prabhu Ananthanarayanan",
  "open_to_work": true,
  "linkedin_url": "https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707",
  "message": "Candidate imported from LinkedIn and ready for Thunder autonomous outreach"
}

Step 9: Thunder picks up candidate
Within 5 minutes, Thunder autonomous loop:
- Detects new candidate with linkedin_source
- Matches to open jobs (Thunder skill matching)
- Sends WhatsApp intro/qualification questions
- Scores candidate fit
- Schedules interview if qualified
- No recruiter clicks needed
```

---

## API Endpoint Reference

### POST /candidate/import/linkedin

**Request:**
```json
{
  "linkedin_url": "https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707"
}
```

**Success Response (200):**
```json
{
  "status": "SUCCESS",
  "candidate_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "iyer.prabhu@gmail.com",
  "phone": "+1-555-0123456",
  "full_name": "Prabhu Ananthanarayanan",
  "open_to_work": true,
  "linkedin_url": "https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707",
  "message": "Candidate imported from LinkedIn and ready for Thunder autonomous outreach"
}
```

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 400 | InvalidLinkedInURL | URL format invalid (not /in/profile-slug) |
| 404 | ApolloCandidateNotFound | Apollo found no enrichment data |
| 403 | CandidateNotOpenToWork | Candidate NOT marked "Open to Work" - gate failed |
| 409 | DuplicateCandidateExists | Email or phone already in candidates table |
| 500 | Apollo MCP auth error | Apollo.io OAuth not configured in claude.ai |

---

## Architecture

### Service Layer: `linkedin_import_service.py`

**Functions:**

1. **`_parse_linkedin_url(linkedin_url: str) -> str`**
   - Input: Full LinkedIn URL or profile slug
   - Output: Profile slug (e.g., "prabhu-ananthanarayanan-989a707")
   - Raises: `InvalidLinkedInURL` if format invalid
   
   Accepts:
   - https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707
   - https://linkedin.com/in/prabhu-ananthanarayanan-989a707
   - /in/prabhu-ananthanarayanan-989a707

2. **`_enrich_via_apollo(profile_slug: str, apollo_search_func=None) -> Dict`**
   - Input: Profile slug + injectable Apollo search function
   - Output: Enriched profile data
   ```python
   {
     'email': 'iyer.prabhu@gmail.com',
     'phone': '+1-555-0123456',
     'full_name': 'Prabhu Ananthanarayanan',
     'company': 'TechCorp Inc',
     'title': 'Senior Software Engineer',
     'open_to_work': True,  # CRITICAL GATE
     'linkedin_url': 'https://www.linkedin.com/in/prabhu-...',
     'raw_profile_data': '{...full Apollo response...}'
   }
   ```
   - Raises: `ApolloCandidateNotFound`, `CandidateNotOpenToWork`

3. **`import_linkedin_candidate(db, linkedin_url, apollo_search_func, promoted_by, now) -> Tuple[Candidate, Dict]`**
   - Complete workflow orchestrator
   - Returns: (candidate model, import_info dict)
   - Handles: Parsing → Enrichment → Gate → Dedup → Create → Consent

---

### Exception Hierarchy

```python
LinkedInImportError (base)
├── InvalidLinkedInURL
│   └── Raised when URL doesn't match /in/profile-slug pattern
│
├── ApolloCandidateNotFound
│   └── Raised when Apollo enrichment fails or returns empty
│
├── CandidateNotOpenToWork
│   └── Raised when open_to_work_status == false (GATE - expected rejection)
│
└── DuplicateCandidateExists
    └── Raised when email or phone match existing candidate
```

---

## Implementation Details

### Data Flow

```
User provides LinkedIn URL
         ↓
Parse URL → Extract profile slug
         ↓
Call Apollo.io → Enrich profile
         ↓
Check open_to_work status
  ├─ false → GATE FAIL (403 Forbidden)
  └─ true → Continue
         ↓
Check for duplicates (email OR phone)
  ├─ found → DUPLICATE (409 Conflict)
  └─ new → Continue
         ↓
Create Candidate record
  ├─ Fields: email, phone, linkedin_url, candidate_source
  └─ Status: NEW
         ↓
Record WhatsApp consent
  └─ consent_given: true
         ↓
Return to frontend
         ↓
Thunder loop (within 5 min) picks up
  ├─ Matches to jobs
  ├─ Sends outreach
  └─ Autonomous flow
```

### Why No Staging?

LinkedIn profiles are **pre-qualified** by:
1. **Open to Work status** - candidate explicitly signaled intent
2. **Apollo enrichment** - verified email/phone match
3. **Consent implied** - visiting LinkedIn profile = willingness to connect

Therefore: **Direct promotion to Candidate record** (no staging step needed).

### Critical Gate: "Open to Work"

Apollo returns `open_to_work_status` from LinkedIn's public profile data:

- ✅ `true` → Import proceeds (candidate actively looking)
- ❌ `false` → Import rejected with 403 (candidate passive - low priority)

**Why this gate?**
- Filters to high-intent targets only
- Saves Thunder resources (don't contact passive candidates)
- Respects candidate signals (not interrupting working employees)
- Increases response rate (Open to Work = actively looking)

---

## Dependency Injection: Apollo MCP

Service uses injected `apollo_search_func` for testability:

```python
async def import_linkedin_candidate(
    db: Session,
    linkedin_url: str,
    *,
    apollo_search_func=None,  # Injected, not hardcoded
    promoted_by: str = "linkedin_auto_import",
    now: Optional[datetime] = None
)
```

### Apollo Integration Module

Centralized Apollo integration code located in: `app/services/apollo_integration.py`

**Key functions:**
- `search_apollo_by_linkedin_url(linkedin_url, apollo_mcp_client)` - Main search function
- `create_mock_apollo_search()` - Mock for testing (no auth needed)
- `create_mock_apollo_not_open_to_work()` - Mock for gate testing
- `create_mock_apollo_empty_result()` - Mock for "not found" testing

### Production Setup (Required)

1. **Authenticate Apollo.io via claude.ai**
   - Go to: https://claude.ai/settings/connectors
   - Find: Apollo.io
   - Click: Connect → OAuth flow
   - Grant: API access
   - Result: MCP server becomes available in this backend

2. **Wire Apollo MCP Client in Endpoint** (currently raises NotImplementedError)
   ```python
   # CURRENT (in candidates.py endpoint):
   async def apollo_search_func(search_params):
       return await search_apollo_by_linkedin_url(
           linkedin_url=search_params.get('linkedin_url'),
           apollo_mcp_client=None  # Not configured yet
       )

   # PRODUCTION: Inject real MCP client:
   async def apollo_search_func(search_params):
       # Get Apollo MCP client from environment/config
       apollo_mcp_client = get_apollo_mcp_client()  # Your MCP setup
       return await search_apollo_by_linkedin_url(
           linkedin_url=search_params.get('linkedin_url'),
           apollo_mcp_client=apollo_mcp_client
       )
   ```

3. **Test with mock** (no auth needed)
   ```python
   from app.services.apollo_integration import create_mock_apollo_search

   # Use mock for testing
   mock_apollo = create_mock_apollo_search(
       email='test@example.com',
       phone='+1-555-0123',
       full_name='Test User',
       open_to_work=True
   )

   candidate, import_info = await import_linkedin_candidate(
       db,
       "https://www.linkedin.com/in/test-user",
       apollo_search_func=mock_apollo  # Pass mock instead of real
   )
   ```

### Error Message When Apollo Not Configured

Until Apollo.io OAuth is set up, calling the endpoint returns 500 with:
```
NotImplementedError: Apollo MCP integration required.
Setup steps:
1. Go to https://claude.ai/settings/connectors
2. Find 'Apollo.io' and click 'Connect'
3. Complete OAuth flow to authorize API access
4. Restart this backend
See backend/LINKEDIN_CANDIDATE_IMPORT.md for details.
```

---

## Error Handling & Edge Cases

| Scenario | Status | Handling |
|----------|--------|----------|
| Invalid URL format | 400 | Regex validation fails, clear error message |
| Apollo enrichment timeout | 404 | Apollo call fails, return not found |
| Candidate not open to work | 403 | Expected rejection, log and inform user |
| Email match found | 409 | Candidate exists, don't create duplicate |
| Phone match found | 409 | Candidate exists, don't create duplicate |
| Apollo auth not configured | 500 | MCP NotImplementedError caught, return 500 |
| Database commit fails | 500 | Transaction rolls back, clear error |

---

## Testing Strategy

### Unit Tests

```python
# Test URL parsing
assert _parse_linkedin_url("https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707") \
    == "prabhu-ananthanarayanan-989a707"

# Test gate: Open to Work
with pytest.raises(CandidateNotOpenToWork):
    await import_linkedin_candidate(
        db, 
        linkedin_url,
        apollo_search_func=mock_apollo_not_open_to_work
    )

# Test duplicate detection
# Create candidate first
candidate1 = create_candidate_safe(db, email="test@example.com", ...)
# Attempt import with same email
with pytest.raises(DuplicateCandidateExists):
    await import_linkedin_candidate(db, linkedin_url, apollo_search_func=...)
```

### Integration Tests

```python
async def test_complete_linkedin_import_flow():
    """End-to-end test: URL → Candidate → Ready for Thunder"""
    
    # Setup
    db = get_test_db()
    
    # Mock Apollo enrichment
    async def mock_apollo(params):
        return {
            'contacts': [{
                'email': 'prabhu@example.com',
                'phone_number': '+1-555-0123',
                'name': 'Prabhu Ananthanarayanan',
                'open_to_work_status': True,
                'company_name': 'TechCorp'
            }]
        }
    
    # Execute
    candidate, import_info = await import_linkedin_candidate(
        db,
        "https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707",
        apollo_search_func=mock_apollo
    )
    
    # Verify
    assert candidate.candidateID is not None
    assert candidate.candidateEmail == 'prabhu@example.com'
    assert candidate.candidateMobileNumber == '+1-555-0123'
    assert candidate.candidate_linkedin_url == 'https://...'
    assert import_info['status'] == 'SUCCESS'
    
    # Verify Thunder will pick it up
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.subject_id == candidate.candidateID
    ).first()
    assert consent.consent_given == True
```

---

## Monitoring & Metrics

### Key Metrics to Track

| Metric | Formula | Why |
|--------|---------|-----|
| Import success rate | Successful imports / Total attempts | Overall system health |
| Gate rejection rate | CandidateNotOpenToWork / Total attempts | Filter quality |
| Duplicate rate | DuplicateCandidateExists / Successful imports | Data quality |
| Time to Thunder pickup | Minutes from import to first outreach | Automation latency |
| Candidate response rate | Responded to Thunder / Imported | Engagement quality |

### Logging

Service logs all steps:
```python
[LinkedIn Import] Parsing LinkedIn URL: https://...
[LinkedIn Import] Enriching via Apollo: prabhu-ananthanarayanan-989a707
[LinkedIn Import] Apollo enrichment success: Prabhu Ananthanarayanan (iyer.prabhu@gmail.com)
[LinkedIn Import] Checking for duplicates: iyer.prabhu@gmail.com / +1-555-0123
[LinkedIn Import] Creating candidate: Prabhu Ananthanarayanan
[LinkedIn Import] Recording consent for {candidate_id}
[LinkedIn Import] SUCCESS: Candidate {candidate_id} created and ready for Thunder
```

---

## Known Limitations & Future Work

### Current Limitations

1. **Apollo MCP requires auth** - Must be configured via claude.ai connectors
2. **No batch import** - One URL at a time (can be added later)
3. **No campaign tracking** - No link between import source and outcome
4. **No retry logic** - Failed imports not requeued automatically

### Future Enhancements

1. **Batch import** - CSV/JSON with multiple LinkedIn URLs
2. **Campaign tracking** - Tag imports with source (e.g., "Sales team LinkedIn search")
3. **Enrichment retry** - Auto-retry failed Apollo calls after delay
4. **Webhook notifications** - Alert when candidate takes Thunder action
5. **LinkedIn company filters** - Only import from specific companies
6. **Skill matching prefilter** - Additional gate based on required skills

---

## Related Systems

### Thunder Autonomous Loop
- Picks up candidate within 5 minutes
- Matches to open jobs using skill scores
- Sends WhatsApp qualification flow
- Schedules interviews if qualified
- No manual recruiter intervention needed

**Interaction:** LinkedIn import creates candidate, Thunder handles rest.

### Duplicate Candidate Architecture (Commit 7002d3b4)
- Allows same candidate to apply to multiple jobs
- Tracks multiple applications for genuine interest scoring
- Email OR phone match = single candidate record
- Multiple job submissions = multiple candidate_job_assignment records

**Interaction:** LinkedIn import checks duplicates, then creates candidate for Thunder.

### Candidate Profile (EPIC-04, 2026-08-08)
- Resume parsing from LinkedIn
- Auto-populate education/experience
- Structured skills with primary designation
- LinkedI URL stored in profile

**Interaction:** LinkedIn import populates linkedin_url, Thunder's profile parsing uses it.

---

## Commit History

| Commit | Message | Changes |
|--------|---------|---------|
| f775bad | feat: Add LinkedIn candidate import endpoint with Apollo enrichment gate | Service + Endpoint |
| 7002d3b4 | Duplicate candidate architecture | Enables multiple applications |
| e967d51 | Submit Job Modal | Candidate → Job workflow |

---

## Troubleshooting

### Apollo returns empty profile
- **Cause:** LinkedIn profile private or Apollo doesn't have access
- **Fix:** Check Apollo credentials, verify LinkedIn profile is public
- **Result:** HTTPException 404 "ApolloCandidateNotFound"

### Candidate not open to work
- **Cause:** LinkedIn profile shows "Open to Work" = OFF
- **Fix:** Ask candidate to enable "Open to Work" on their LinkedIn
- **Result:** HTTPException 403 "CandidateNotOpenToWork" (expected)

### Duplicate detected
- **Cause:** Email or phone already imported
- **Fix:** Check if candidate already exists, update instead of re-import
- **Result:** HTTPException 409 "DuplicateCandidateExists"

### Apollo MCP not configured
- **Cause:** Apollo.io OAuth not connected in claude.ai
- **Fix:** Go to claude.ai Settings → Connectors → Apollo.io → Connect
- **Result:** HTTPException 500 when Apollo call attempted
