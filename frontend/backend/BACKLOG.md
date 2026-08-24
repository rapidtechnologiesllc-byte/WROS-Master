# BACKLOG - End of Project Tasks

## EPIC: Database Migration (PostgreSQL)
**Priority:** CRITICAL - Must be done before production deployment
**Estimated:** 2-3 weeks
**Dependencies:** All current features must be complete first

### Epic Overview
Replace SQLite with PostgreSQL to enable:
- Concurrent write access (currently limited to 1 writer)
- Connection pooling (prevents lock contention)
- Row-level locking (not table-level)
- Multi-process/multi-worker support
- Production-grade reliability

### Current Workaround (Temporary Patch)
**File:** `app/core/db_resilience.py`
- SQLite WAL mode enabled (Write-Ahead Logging)
- 5-second busy_timeout on lock failures
- Exponential backoff retry logic
- Reduces but does NOT eliminate database lock failures

**Status:** ✅ DEPLOYED (2026-08-14)
**Impact:** Allows Thunder + Bulk Import to work concurrently
**Limitation:** Will still lock under extreme concurrent load (>1000 candidates/min)

### Migration Tasks

#### Phase 1: Infrastructure Setup
- [ ] Install PostgreSQL 14+ on dev/staging/production
- [ ] Create databases: `onboarding_dev`, `onboarding_staging`, `onboarding_prod`
- [ ] Create application user with proper permissions
- [ ] Test connection from application servers

#### Phase 2: Code Changes
- [ ] Update `app/core/database.py` with PostgreSQL connection string
- [ ] Configure connection pooling (pool_size=20, max_overflow=40)
- [ ] Remove SQLite-specific pragmas and WAL logic
- [ ] Add transaction isolation level configuration
- [ ] Update requirements.txt: add `psycopg2-binary`

#### Phase 3: Schema Migration
- [ ] Export schema from SQLite
- [ ] Create migration scripts for schema differences
- [ ] Run Alembic migrations on PostgreSQL
- [ ] Verify all indexes and constraints

#### Phase 4: Data Migration
- [ ] Export data from SQLite
- [ ] Transform and load into PostgreSQL
- [ ] Verify row counts and data integrity
- [ ] Test production data volume (30K+ candidates)

#### Phase 5: Testing & Validation
- [ ] Load test: 10K concurrent candidates
- [ ] Stress test: Thunder + Bulk Import simultaneously
- [ ] Verify no database locks under load
- [ ] Benchmark performance improvements
- [ ] Test failover/recovery scenarios

#### Phase 6: Deployment
- [ ] Update environment variables for all environments
- [ ] Create deployment runbook
- [ ] Schedule cutover window
- [ ] Prepare rollback plan
- [ ] Execute migration
- [ ] Monitor for 24 hours post-deployment

### Success Criteria
- ✅ Zero database lock errors under normal load
- ✅ Thunder processes 20+ candidates per minute continuously
- ✅ Bulk import can run while Thunder is active
- ✅ Response times < 200ms for queries
- ✅ Support for 100K+ candidate database

### Notes
- Current SQLite patch is a STOPGAP only - not production-ready
- PostgreSQL migration unblocks: autoscaling, multi-server deployment, cloud hosting
- Consider managed PostgreSQL (AWS RDS, Azure Database, DigitalOcean) for production
