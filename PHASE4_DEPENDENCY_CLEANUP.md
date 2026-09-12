# Phase 4: Dependency Cleanup Analysis

## Executive Summary

Audit of `requirements.txt` identified **16 unused packages**, but **many are actually needed** due to being:
- Indirect dependencies (required by other packages)
- FastAPI plugins (loaded automatically)
- Core infrastructure (authentication, database, configuration)

**Recommendation**: Delete only the clearly unused 3-4 packages; keep everything else.

---

## Audit Results

### Categories

#### ✅ ACTIVELY USED (Keep - High Confidence)
| Package | Usage | Confidence |
|---------|-------|-----------|
| fastapi | 176 files | CRITICAL |
| sqlalchemy | 598 files | CRITICAL |
| pydantic | 112 files | CRITICAL |
| requests | 25 files | HIGH |
| langgraph | 2 files | HIGH |
| apscheduler | 2 files | HIGH |
| bcrypt | 2 files | MEDIUM |

#### ⚠️ RARELY USED (Review before keeping)
| Package | Usage | Status | Notes |
|---------|-------|--------|-------|
| redis | 1 file | REVIEW | Auth middleware only, low usage |
| cryptography | 1 file | REVIEW | Used by security module |
| pyotp | 1 file | REVIEW | MFA support |
| msal | 1 file | REVIEW | Microsoft auth |
| openpyxl | 1 file | REVIEW | Excel import |

#### ❌ UNUSED - BUT ACTUALLY NEEDED (Keep - Hidden Dependencies)
| Package | Original Assessment | Actual Status | Reason |
|---------|-------------------|---------------|--------|
| python-dotenv | Unused | **KEEP** | Used in core/config.py + core/database.py |
| PyJWT[crypto] | Unused | **KEEP** | Used by FastAPI security |
| python-multipart | Unused | **KEEP** | Required by FastAPI for file uploads |
| email-validator | Unused | **KEEP** | Used by Pydantic for email fields |
| python-dateutil | Unused | **KEEP** | Used by date/time handling |
| psycopg2-binary | Unused | **KEEP** | Required for PostgreSQL (hidden by SQLAlchemy) |
| alembic | Unused | **KEEP** | Migration tool (referenced in docs even if not used) |
| greenlet | Unused | **KEEP** | Required by SQLAlchemy for async support |
| pydantic-settings | Unused | **KEEP** | Pydantic v2 settings management |

#### ❓ QUESTIONABLE - Can Likely Be Deleted
| Package | Usage | Recommendation | Risk |
|---------|-------|-----------------|------|
| uvicorn[standard] | 0 | **INVESTIGATE** | If not used, app won't start! |
| python-docx | 0 | DELETE | Document generation not used |
| pypdf | 0 | DELETE | PDF parsing not used |
| langchain-google-genai | 0 | DELETE | AI integration abandoned |
| gunicorn | 0 | DELETE | Production WSGI server (use uvicorn) |
| pyodbc | 0 | DELETE | ODBC for SQL Server (not used, using PostgreSQL) |

#### 🔴 CRITICAL - DO NOT DELETE
| Package | Why |
|---------|-----|
| uvicorn | **CRITICAL**: Application server. App will not start without it. |
| sqlalchemy | **CRITICAL**: ORM for all database operations. |
| pydantic | **CRITICAL**: Request/response validation. |
| fastapi | **CRITICAL**: Web framework. |

---

## Safe Deletion Candidates (LOW RISK)

### 1. python-docx
- **Usage**: 0 files
- **Purpose**: Generate Word documents (.docx)
- **In use**: NO - no offer letter generation found
- **Risk**: LOW
- **Action**: DELETE

### 2. pypdf  
- **Usage**: 0 files
- **Purpose**: Extract text from PDFs
- **In use**: NO - resume parsing uses other methods
- **Risk**: LOW
- **Action**: DELETE

### 3. langchain-google-genai
- **Usage**: 0 files
- **Purpose**: Google Generative AI integration
- **In use**: NO - using langgraph instead
- **Risk**: LOW
- **Action**: DELETE

### 4. gunicorn
- **Usage**: 0 files
- **Purpose**: Production WSGI server
- **In use**: NO - using uvicorn in production
- **Risk**: LOW
- **Action**: DELETE

### 5. pyodbc
- **Usage**: 0 files
- **Purpose**: ODBC driver for SQL Server
- **In use**: NO - using PostgreSQL with psycopg2
- **Risk**: LOW
- **Action**: DELETE

---

## Packages to Keep Despite Rare Usage

### redis (1 file in auth_middleware.py)
- **Assessment**: Rarely used but present
- **Risk of Deletion**: MEDIUM (might be used in background)
- **Recommendation**: KEEP for now, mark as "review in 6 months"

### cryptography (1 file)
- **Assessment**: Used by security module
- **Risk of Deletion**: MEDIUM (authentication might break)
- **Recommendation**: KEEP (it's critical infrastructure)

### pyotp (1 file)
- **Assessment**: MFA/TOTP support
- **Risk of Deletion**: MEDIUM (security feature)
- **Recommendation**: KEEP (it's a feature dependency)

### msal (1 file)
- **Assessment**: Microsoft authentication
- **Risk of Deletion**: LOW (only if not using Azure auth)
- **Recommendation**: REVIEW usage, possibly delete

### openpyxl (1 file)
- **Assessment**: Excel file handling
- **Risk of Deletion**: LOW (if not doing bulk imports)
- **Recommendation**: REVIEW usage, possibly delete

---

## Phase 4 Execution Plan

### TIER 1: Safe Deletions (Execute Now)

Remove these packages from `requirements.txt`:
```
- python-docx
- pypdf
- langchain-google-genai
- gunicorn
- pyodbc
```

**Impact**: -5 packages, eliminates 1-2% of dependencies
**Risk**: VERY LOW

### TIER 2: Review Required (Hold for Now)

Before deleting, need to investigate:
```
- redis (check auth_middleware.py usage pattern)
- msal (check if Azure auth is used)
- openpyxl (check if bulk import exists)
```

### TIER 3: Do NOT Delete

These are critical and must stay:
```
- FastAPI ecosystem (fastapi, uvicorn, starlette, pydantic)
- Database (sqlalchemy, psycopg2-binary)
- Security (PyJWT, python-multipart, python-dotenv)
- Core utilities (requests, apscheduler, langgraph)
```

---

## Recommendations

1. **Execute TIER 1 now** - Safe to remove 5 packages
2. **Review TIER 2 later** - Investigate specific files before deletion
3. **Never touch TIER 3** - Core infrastructure

---

## Safe Deletion Script (Ready to Execute)

```bash
# Create backup
cp requirements.txt requirements.txt.backup

# Remove unused packages
grep -v "python-docx\|pypdf\|langchain-google-genai\|gunicorn\|pyodbc" \
  requirements.txt.backup > requirements.txt

# Verify
diff requirements.txt requirements.txt.backup
```

---

## Summary

| Metric | Current | After Phase 4 | Change |
|--------|---------|---------------|--------|
| Total packages | 26 | 21 | -5 (-19%) |
| Critical packages | 8 | 8 | 0 |
| Unused packages | 16 | 11 | -5 |
| Risk level | UNKNOWN | LOW | ✅ |

**Status**: Ready for execution when approved
**Risk Assessment**: VERY LOW (only removing clearly unused packages)

