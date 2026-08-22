# Business Unit Implementation Plan - Complete Cross-Reference (2026-08-12)

## Overview
Complete the Business Unit system with full cross-referencing across all key entities: User, Candidate, Job, Employee, Expense, Opportunity, Performance, P&L.

## Phase 1: Database Schema Updates
- [x] Users.business_unit_id (already exists)
- [x] Jobs.business_unit_id (already exists)
- [x] Employee.bu_id (already exists - note: uses `bu_id` not `business_unit_id`)
- [x] Expense.business_unit_id (already exists)
- [x] OrgStructure models (already have BU refs)
- [ ] Candidate.business_unit_id - MISSING - need migration
- [ ] Opportunity.business_unit_id - MISSING - need to check and add if needed
- [ ] Performance table BU reference - MISSING - need to check

## Phase 2: API Endpoints - User Management
- [x] GET /hr/users/all (returns BU info)
- [x] GET /hr/users/search (filters by BU)
- [x] GET /hr/users/details/{user_id} (returns BU)
- [x] POST /hr/users/create (basic, doesn't set BU)
- [x] POST /hr/users/create-with-roles (sets BU)
- [ ] PUT /hr/users/{user_id} - NEEDS UPDATE - add business_unit_id and department_id fields
- [x] DELETE /hr/users/{user_id}
- [ ] POST /hr/users/{user_id}/assign-bu - NEW - assign BU to existing user

## Phase 3: Candidate BU Auto-Assignment
- [ ] Migration: Add business_unit_id to candidates table
- [ ] Service: Implement auto-assignment logic when candidate submitted to job
- [ ] Endpoint: POST /candidates/submit-to-job - auto-assign candidate's BU from job's BU
- [ ] Edge case: Handle candidates submitted to multiple jobs in different BUs

## Phase 4: Multi-BU Edge Cases
- [ ] Candidate in multiple BUs (track which BU for each job submission)
- [ ] Employee transfer between BUs (create employment history record)
- [ ] Expense allocation to multiple BUs (if needed)
- [ ] Reports with cross-BU consolidation

## Phase 5: Frontend Integration
- [ ] Edit User Modal: Add Business Unit dropdown field
- [ ] Connect Add/Edit/Delete buttons to backend APIs
- [ ] Display BU info in user list/search results
- [ ] Add BU filtering to candidate/employee/job lists
- [ ] Update navigation based on user's BU visibility

## Implementation Order
1. Update Users API: PUT endpoint to handle BU
2. Add migration for Candidate.business_unit_id
3. Add business_unit_id to Candidate model
4. Create submission endpoint with BU auto-assignment
5. Update schemas/responses
6. Frontend: Edit User modal with BU field
7. Frontend: Connect CRUD buttons to APIs
8. Testing & validation

---

## Current Status Check

### What Exists
- Users table: business_unit_id ✓, relationships configured ✓
- Jobs table: business_unit_id ✓
- Employee table: bu_id ✓  (note: different column name)
- Expense table: business_unit_id ✓
- User model relationships: business_unit ✓

### What's Missing
- Candidate model: NO business_unit_id
- Opportunity model: Need to verify
- Performance/P&L: Need to check
- Update endpoint for user BU changes
- Auto-assignment logic in submission flow
