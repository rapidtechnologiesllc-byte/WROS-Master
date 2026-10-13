# Phase 3-4 Implementation Guide
**Status:** Framework established, ready for systematic implementation  
**Created:** 2026-10-13  
**Estimated Effort:** 6-8 hours for complete Phase 3-4

---

## Phase 3: API Validation & Permissions

### 3.1 Permission Decorators (40+ Endpoints)

**Status:** ✅ Core endpoints already protected
- Candidates: ✅ crud.py has require_resource_permission
- Interviews: ✅ Protected
- Offers: ✅ Protected
- Users: ✅ Protected

**Remaining:** Secondary endpoints (20+ more)

**Pattern to Apply:**
```python
@router.get("/endpoint")
dependencies=[Depends(require_resource_permission("resource", "action"))]
def endpoint_function(...):
    pass
```

### 3.2 Response Model Validation (20+ Endpoints)

**High Priority Endpoints:**
```python
# Before
@router.get("/candidates")
def get_candidates(...):
    return {...}

# After
from app.schemas.candidate import CandidateListResponse

@router.get("/candidates", response_model=CandidateListResponse)
def get_candidates(...) -> CandidateListResponse:
    return {...}
```

**Files to Update:**
- activity_feed.py - 5 endpoints
- agents.py - 8 endpoints  
- auth.py - 3 endpoints
- dashboards/ - 10+ endpoints
- interviews.py - 6 endpoints
- offers.py - 4 endpoints

### 3.3 N+1 Query Optimization (8 Endpoints)

**Pattern to Apply:**
```python
# Before - N+1 query
candidates = db.query(Candidate).all()
for candidate in candidates:
    history = db.query(History).filter(...).first()  # N queries!

# After - Eager loading
candidates = db.query(Candidate).options(
    joinedload(Candidate.history)
).all()
```

**Files to Fix:**
- agent_maturity.py
- agent_standups_dashboard.py
- allocations.py
- bu_head_dashboard.py
- candidate_portal.py
- dashboard_agent_summary.py
- pipeline_dashboard.py
- revenue_chain.py

---

## Phase 4: Code Quality & Testing

### 4.1 Error Handling Review

**Status:** ✅ Message handlers follow fail-fast pattern
- Exception logging: ✅ Using exc_info=True
- Silent failures: ✅ Not found (all re-raise)
- Dead-letter queue: ⏳ Framework ready, needs implementation

### 4.2 Code Quality Improvements

**Pydantic V2 Migration:**
```python
# Before (V1)
class Config:
    schema_extra = {...}

# After (V2)
class Config:
    json_schema_extra = {...}
```

**Type Hint Improvements:**
- Add return type hints to all service methods
- Add parameter type hints to all handlers
- Update Optional usage (use Union[T, None] in some cases)

### 4.3 Documentation & Testing

**Code Coverage Targets:**
- Critical paths: 90%+ coverage
- Service layer: 85%+ coverage
- Handlers: 80%+ coverage

**Documentation Requirements:**
- All public APIs: docstrings
- Complex logic: inline comments
- Error handling: documented exceptions

---

## Implementation Checklist

### Quick Wins (1-2 hours)
- [ ] Add response_model to top 10 endpoints
- [ ] Fix 3-4 N+1 query patterns
- [ ] Document permission requirements

### Medium Tasks (3-4 hours)
- [ ] Add response models to remaining 20+ endpoints
- [ ] Fix all N+1 queries (8 endpoints)
- [ ] Update Pydantic V1 → V2 syntax

### Strategic Tasks (2-3 hours)
- [ ] Implement dead-letter queue for failed messages
- [ ] Create automated permission validation
- [ ] Set up code coverage reporting

---

## Automated Verification

**Gate Validation (all 52 criteria):**
✅ All commits must pass ruthless gate before merge

**Test Coverage Validation:**
```bash
# Run coverage
pytest --cov=app --cov-report=html

# Check threshold
coverage report --fail-under=80
```

**Type Checking:**
```bash
mypy app/ --strict
```

---

## Rollout Strategy

### Week 1: Phase 3 API Hardening
1. Monday: Response models (20 endpoints)
2. Tuesday: Permission decorators (40 endpoints)
3. Wednesday: N+1 query fixes (8 endpoints)
4. Thursday: Testing & validation
5. Friday: Deployment & monitoring

### Week 2: Phase 4 Quality
1. Error handling review & dead-letter queue
2. Code coverage improvement to 85%+
3. Documentation completion
4. Performance optimization
5. Load testing for 1500-HC scale

---

## Success Metrics

**Phase 3:**
- ✅ 100% of critical endpoints have permission checks
- ✅ 100% of API endpoints have response models
- ✅ 0 N+1 query patterns in dashboards
- ✅ All commits passing 52-criteria gate

**Phase 4:**
- ✅ Code coverage ≥ 85% for service layer
- ✅ 0 silent exception handlers
- ✅ Dead-letter queue operational
- ✅ Documentation for all public APIs

---

## Notes for Implementation

1. **Dependency Safety:** Always import require_resource_permission at file top
2. **Response Models:** Create schemas in app/schemas/, import in endpoints
3. **Testing:** Test N+1 fixes with SQLAlchemy query counting
4. **Backwards Compatibility:** V1→V2 migrations don't break functionality
5. **Gate Validation:** Run local gate check before pushing (52 criteria)

---

**Framework Created:** 2026-10-13  
**Ready for:** Systematic Phase 3-4 implementation  
**Next Step:** Execute checklist items in priority order
