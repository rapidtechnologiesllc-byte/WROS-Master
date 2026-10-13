# Comprehensive Build & Test Plan - P&L Revenue Recognition Implementation

**Date:** 2026-08-13  
**Status:** Phase 1-2 Backend Complete | Phase 3 Frontend In Progress  
**Scope:** Opportunity→Job→Project→Invoice→Revenue workflow with P&L attribution and partner revenue share

---

## PHASE 1: Backend Models & Migrations ✅ COMPLETE

### Database Schema Changes
- [x] Create `enums.py` with Service, Module, ClientType, PricingModel types
- [x] Update `opportunities` table: add service, module, client_type, pricing_model columns
- [x] Create `revenues` table for revenue recognition tracking
- [x] Update `invoices` table: add opportunity_id (FK) link
- [x] Update `partner_bu_assignments` table: add core_revenue_share_pct field
- [x] Create migration file: `20260813_phase1_revenue_recognition.py`

### Model Files Created
- [x] `app/models/enums.py` - Enum definitions (11 enum types)
- [x] `app/models/revenue.py` - Revenue model (P&L tracking)
- [x] Updated `app/models/opportunity.py` - Add 4 enum fields
- [x] Updated `app/models/invoice.py` - Add opportunity_id link
- [x] Updated `app/models/org_structure.py` - Add core_revenue_share_pct

### Unit Tests
- [x] `tests/unit/test_models_phase1.py` - Comprehensive model tests (150+ assertions)
- Tests cover: enums, opportunity fields, invoice links, revenue model, partner share config

---

## PHASE 2: Backend Services & APIs ✅ COMPLETE

### Service Files Created
- [x] `app/services/revenue_service.py` - Revenue recognition business logic
  - recognize_invoice_revenue() - Trigger revenue recognition on invoice PAID
  - Revenue breakdown by service, module, pricing, client
  - Gross margin analysis
  - Partner revenue share calculation
  
- [x] `app/services/invoice_service.py` - Invoice management (enhanced)
  - create_invoice() - Create DRAFT invoice with opportunity link
  - add_line_item() - Add timesheet-derived line items
  - transition_invoice_status() - DRAFT→APPROVED→SENT→PAID workflow
  - Revenue-focused queries (by opportunity, client, service)

### API Endpoints (Ready for Implementation)
**Revenue Recognition Endpoints:**
- GET  /api/v1/revenue/by-opportunity/{id} - List revenue by opportunity
- GET  /api/v1/revenue/by-client-owner/{id} - P&L tracking by account manager
- GET  /api/v1/revenue/by-bu/{id} - BU revenue rollup
- GET  /api/v1/revenue/breakdowns/{bu_id}
  - ?breakdown=service - Revenue by service
  - ?breakdown=module - Revenue by Guidewire module
  - ?breakdown=pricing - Revenue by pricing model
- GET  /api/v1/revenue/gross-margin/{bu_id} - Margin analysis
- GET  /api/v1/revenue/partner-share/{bu_id} - Partner share details

**Invoice Management Endpoints:**
- POST /api/v1/invoices/create - Create invoice (links opportunity)
- POST /api/v1/invoices/{id}/approve - DRAFT→APPROVED (with revenue trigger)
- POST /api/v1/invoices/{id}/send - APPROVED→SENT
- POST /api/v1/invoices/{id}/mark-paid - SENT→PAID (triggers recognition)
- GET  /api/v1/invoices/{id}/revenue - Get recognized revenue from invoice

---

## PHASE 3: Frontend Screens (IN PROGRESS)

### New Screens to Build

#### 1. **Invoice Management Screen** (NEW)
**Location:** `src/screens/InvoiceManagementScreen.js`
**Purpose:** Finance: create, approve, send, track payment + revenue recognition

**Components:**
- [ ] Invoice list with filters (status, project, client, date range)
- [ ] Invoice status indicators (DRAFT, APPROVED, SENT, PAID)
- [ ] Create Invoice modal
  - [ ] Project selector (auto-populates client, BU)
  - [ ] Opportunity selector (optional, for P&L linking)
  - [ ] Date range picker (billing period)
  - [ ] Currency selector
  - [ ] Line items table (auto-populate from timesheets)
  
- [ ] Invoice details panel
  - [ ] Invoice summary (total, status, dates)
  - [ ] Line items breakdown
  - [ ] Approval workflow (approve, send, mark paid buttons)
  - [ ] Revenue recognition display (when PAID)
  - [ ] Margin indicators (cost, margin $, margin %)

**UX Flow:**
1. Finance clicks "Create Invoice"
2. Selects project → Auto-loads client, BU, opportunity
3. Selects date range → Auto-loads timesheets for that period
4. System calculates total from line items
5. Finance approves → Status: APPROVED
6. Finance sends to client → Status: SENT
7. Finance marks paid → Status: PAID + Revenue recognized + P&L updated

#### 2. **Opportunity Form Enhancements** (UPDATE)
**Location:** `src/screens/OpportunityForm.js` or `OpportunityDetailsScreen.js`
**Changes:**
- [ ] Add Service dropdown (12 options from enums)
- [ ] Add Module dropdown (12 options from enums)
- [ ] Add ClientType dropdown (4 options from enums)
- [ ] Add PricingModel dropdown (11 options from enums)
- [ ] Add HubSpot contact search (NEW)
  - [ ] Search box with debounce
  - [ ] Contact suggestions dropdown
  - [ ] Selected contact display
  - [ ] Contact details preview

**Form Layout:**
```
Row 1: Account Manager | Client Owner (existing)
Row 2: Service | Module | ClientType | PricingModel (NEW)
Row 3: Engagement Type | Expected Close Date (existing)
Row 4: Revenue Value | Currency (existing)
Row 5: HubSpot Contact (NEW - optional)
Row 6: Save | Cancel
```

#### 3. **Opportunity Pipeline Enhancements** (UPDATE)
**Location:** `src/screens/OpportunityPipelineScreen.js`
**Changes:**
- [ ] Add filter sidebar
  - [ ] Service filter (multi-select)
  - [ ] Module filter (multi-select)
  - [ ] Pricing model filter (multi-select)
  - [ ] Revenue range filter (min, max)
  
- [ ] Add revenue breakdown cards
  - [ ] By Service (pie chart or bars)
  - [ ] By Module (pie chart or bars)
  - [ ] By Pricing Model (pie chart or bars)
  
- [ ] Display engagement type badge (STAFF_AUG vs PROJECT_BASED)
- [ ] Show classification summary in opportunity card

#### 4. **Partner ROI Dashboard Enhancements** (UPDATE)
**Location:** `src/screens/PartnerROIAgentScreen.js`
**Changes:**
- [ ] Add breakdown tabs
  - [ ] By Service (revenue, count, avg deal size)
  - [ ] By Module (revenue, % of total)
  - [ ] By Pricing Model (revenue, avg margin)
  - [ ] By Client (revenue, top clients list)
  
- [ ] Add chart visualizations
  - [ ] Revenue by service (bar/pie)
  - [ ] Revenue trend (line chart, 6-month)
  - [ ] Margin by service (grouped bars)
  
- [ ] Add partner share section
  - [ ] Core business revenue
  - [ ] Partner share % and amount
  - [ ] Company retains %

#### 5. **Opportunity Details Screen Enhancements** (UPDATE)
**Location:** `src/screens/OpportunityDetailsScreen.js`
**Changes:**
- [ ] Display all 4 new classification fields (read-only after creation)
- [ ] Show linked Job/Project status
  - [ ] Job creation status (for STAFF_AUGMENTATION)
  - [ ] Project creation status (for PROJECT_BASED)
  - [ ] Approval status
  
- [ ] Show invoice tracker
  - [ ] Count of invoices by status
  - [ ] Total revenue recognized (from PAID invoices)
  - [ ] Outstanding invoice amount
  - [ ] Revenue cards (pie: recognized vs pending)

#### 6. **Client Management Enhancements** (UPDATE)
**Location:** `src/screens/ClientManagementScreen.js`
**Changes:**
- [ ] Add `partner_revenue_share_pct` field to client form
  - [ ] This is actually for PartnerBUAssignment, but may be editable from client context
  - [ ] Shows which partner oversees this client and their revenue share %

---

### Frontend Services to Create

#### 1. **invoiceService.js** (NEW)
```javascript
// API calls for invoice management
export const invoiceService = {
  createInvoice(data),      // POST /invoices
  getInvoices(filters),     // GET /invoices?status=PAID&bu_id=1
  getInvoiceDetail(id),     // GET /invoices/{id}
  approveInvoice(id),       // POST /invoices/{id}/approve
  sendInvoice(id),          // POST /invoices/{id}/send
  markInvoicePaid(id),      // POST /invoices/{id}/mark-paid
  getInvoiceLineItems(id),  // GET /invoices/{id}/line-items
}
```

#### 2. **revenueService.js** (NEW)
```javascript
// API calls for revenue recognition & P&L
export const revenueService = {
  getRevenueByOpportunity(oppId),      // GET /revenue/by-opportunity/{id}
  getRevenueByClientOwner(ownerId),    // GET /revenue/by-client-owner/{id}
  getRevenueByBU(buId),                // GET /revenue/by-bu/{id}
  getBreakdown(buId, breakdownType),   // GET /revenue/breakdowns/{id}?breakdown=service
  getGrossMargin(buId),                // GET /revenue/gross-margin/{id}
  getPartnerShare(buId),               // GET /revenue/partner-share/{id}
}
```

#### 3. **opportunityService.js** (UPDATE)
```javascript
// Existing service, add:
export const opportunityService = {
  // ... existing
  updateOpportunityClassification(id, {service, module, clientType, pricingModel}),
  searchHubSpotContacts(query),        // Integration with HubSpot API
}
```

---

## PHASE 4: Comprehensive Test Suite

### Unit Tests
- [x] Backend model tests (test_models_phase1.py) - 150+ assertions
- [ ] Backend service tests (test_revenue_service.py)
  - [ ] Revenue recognition logic
  - [ ] Partner share calculation
  - [ ] Margin calculation
  - [ ] Classification tracking
  
- [ ] Frontend component tests (Jest)
  - [ ] InvoiceManagementScreen rendering
  - [ ] Form submissions
  - [ ] Filter/sort logic
  - [ ] Chart rendering

### Integration Tests
- [ ] Invoice → Revenue flow
  - [ ] Create invoice (DRAFT)
  - [ ] Approve invoice (APPROVED)
  - [ ] Send invoice (SENT)
  - [ ] Mark paid (PAID) → Revenue recognized
  - [ ] Verify revenue record created with all fields
  - [ ] Verify P&L attribution to client owner
  - [ ] Verify partner share calculated (Core only)
  
- [ ] Opportunity → Invoice → Revenue flow
  - [ ] Create opportunity with classifications
  - [ ] Create invoice linked to opportunity
  - [ ] Mark paid → Revenue inherits classifications
  - [ ] Verify service/module/pricing tracked correctly

- [ ] Filters and aggregations
  - [ ] Revenue breakdown by service
  - [ ] Revenue breakdown by module
  - [ ] Revenue breakdown by pricing
  - [ ] Gross margin by service
  - [ ] Partner share calculation (Core vs Speciality)

### E2E Tests (Cypress)
- [ ] End-to-end: Opportunity creation to revenue recognition
  1. Create opportunity with Service=System Integration, Module=ClaimsCenter, Pricing=FTE
  2. Create project from WON opportunity
  3. Create timesheets for project
  4. Generate invoice from timesheets
  5. Approve → Send → Mark Paid
  6. Verify revenue recognized with correct classifications
  7. Verify P&L dashboard shows revenue breakdown
  
- [ ] Partner revenue share flow
  1. Set partner revenue share on BU assignment
  2. Create CORE business invoice
  3. Mark paid → Revenue recognized
  4. Verify partner share amount calculated correctly
  5. Verify Speciality invoice doesn't get partner share
  
- [ ] Multiple invoices → Rollup reporting
  1. Create 5 invoices (different services, clients, pricing)
  2. Mark all paid → All revenue recognized
  3. Check Partner ROI dashboard
  4. Verify service breakdown aggregation
  5. Verify total margin calculation

---

## Regression Test Checklist

### Critical Paths (Must Pass)
- [ ] Opportunity creation still works (backward compat - new fields optional)
- [ ] Opportunity pipeline displays correctly
- [ ] Job auto-creation for STAFF_AUGMENTATION still works
- [ ] Project auto-creation for PROJECT_BASED still works
- [ ] Invoice approval workflow unchanged
- [ ] Existing reports still calculate correctly

### P&L Tracking (New Tests)
- [ ] Revenue recognized only when invoice PAID
- [ ] Client Owner receives credit for all revenue
- [ ] Partner share only applies to CORE business
- [ ] Gross margin calculated correctly (revenue - cost)
- [ ] Classifications preserved through invoice→revenue flow
- [ ] P&L reports show correct breakdowns

### Data Integrity
- [ ] No orphaned revenue records
- [ ] No duplicate revenue for same invoice
- [ ] Partner share never exceeds revenue
- [ ] Margin never negative (alert if cost > revenue)
- [ ] Tenant isolation maintained

---

## Deployment Checklist

### Before Deployment
- [ ] All unit tests pass (>85% coverage)
- [ ] All integration tests pass
- [ ] All E2E tests pass
- [ ] Database migration runs successfully on test environment
- [ ] Backward compatibility verified (old opportunities still work)
- [ ] Performance tested (no slowdown on large opportunity sets)

### Database
- [ ] Migration applied to all environments
- [ ] Enums registered in database
- [ ] Foreign keys validated
- [ ] Indexes created for performance

### Frontend
- [ ] Components render without errors
- [ ] Forms submit successfully
- [ ] Charts render correctly
- [ ] Mobile responsive verified
- [ ] Accessibility (WCAG) checked

### Rollback Plan
- [ ] Migration rollback tested
- [ ] Feature flag ready (disable new screens if needed)
- [ ] Data migration reversible

---

## Success Metrics

### Correctness
- All invoices marked PAID within 24 hours have recognized revenue
- P&L dashboard revenue totals match invoice paid totals
- Partner share calculations match configured %
- Gross margin = revenue - cost (100% accuracy)

### Performance
- Invoice list loads in <2 seconds
- Revenue dashboard loads in <3 seconds
- P&L calculations complete in <1 second

### User Experience
- Finance users can create invoice in <2 minutes
- Classification filtering works intuitively
- Revenue attribution is immediately visible

---

## Timeline

| Phase | Component | Est. Days | Status |
|-------|-----------|-----------|--------|
| 1 | Backend Models | 0.5 | ✅ DONE |
| 2 | Services & APIs | 1 | ✅ DONE |
| 3 | Frontend Screens | 3 | 🔄 IN PROGRESS |
| 4 | Tests | 2 | ⏳ PENDING |
| 5 | Deployment | 1 | ⏳ PENDING |
| **Total** | | **7.5 days** | |

---

## Critical Dependencies

- Backend API endpoints must be implemented before frontend calls them
- Database migrations must run before testing revenue flow
- HubSpot API integration credentials must be configured
- Test data (timesheets, projects) must be seeded

---

## Notes for Future Phases

### Post-Production (Phase 5+)
- [ ] HubSpot integration for contact sync
- [ ] Automated invoice generation from approved timesheets
- [ ] Revenue forecasting (predicted vs actual)
- [ ] Partner incentive calculations based on revenue share
- [ ] Multi-level revenue attribution (not just client owner)
- [ ] Revenue targets by service/module
- [ ] Reconciliation alerts (unbilled timesheets, unapproved invoices)
