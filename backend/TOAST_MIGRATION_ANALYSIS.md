# Toast → ScreenLevelBanner Migration Analysis

**Status**: DEFECT-5 Integration - 51 files using toast

---

## Toast Pattern Categories

### 1. **VALIDATION ERRORS** (Hard Stop - Red, Persistent)
**Pattern**: Early return prevents operation  
**Current**: `toast.error("...")` + `return`  
**Migration**: ScreenLevelBanner type="error" (persistent until dismissed)

**Examples**:
- Missing required fields (email, password, name)
- Invalid input format
- No selections made
- Precondition failures

**Behavior**: 
- Show error banner at top of screen
- User must dismiss to continue
- Disable form submission until fixed

### 2. **API/OPERATION ERRORS** (Hard Stop - Red, Persistent)  
**Pattern**: API call fails after user action  
**Current**: `toast.error(err.message)` in catch block  
**Migration**: ScreenLevelBanner type="error" with retry capability

**Examples**:
- "Failed to create user"
- "Failed to update candidate"
- "Failed to delete job"
- Network errors

**Behavior**:
- Show error banner with full error message
- Offer "Retry" button on error banner
- Persist until dismissed
- Log full error to console

### 3. **SUCCESS MESSAGES** (Green, Auto-Dismiss)
**Pattern**: Operation completed successfully  
**Current**: `toast.success("Operation successful")`  
**Migration**: ScreenLevelBanner type="success" (auto-dismiss 3-5s)

**Examples**:
- "User created successfully"
- "Candidate updated successfully"
- "Job assigned successfully ✅"

**Behavior**:
- Show success banner
- Auto-dismiss after 3-5 seconds
- No manual dismiss needed

### 4. **PARTIAL WARNINGS** (Yellow/Info, Dismissible)
**Pattern**: Operation succeeded but with side effects  
**Current**: `toast.success()` with explanation text  
**Migration**: ScreenLevelBanner type="warning" (custom handling)

**Examples**:
- "Candidate created but resume upload failed"
- "User created. Email notification failed to send"
- "Candidate assigned but interview scheduling incomplete"

**Behavior**:
- Show warning banner
- Let user know operation partially succeeded
- Auto-dismiss or allow manual dismiss

---

## File-by-File Breakdown

### TIER 1: CREATE/EDIT/DELETE CORE WORKFLOWS (Priority)

**Priority 1a - Candidate Management** (User-facing, frequent)
- [ ] CandidateCreate.js (8 toasts: 2 success, 4 error, 2 warning)
- [ ] CandidateDetailsScreen.js (needs review)
- [ ] CandidateAssignJobModal.js (needs review)
- [ ] CandidateSelfService.js (needs review)
- [ ] CandidateSearch.js (needs review)

**Priority 1b - User Management** (Admin workflows)
- [ ] UsersAndAccessControl.js (15+ toasts: 5 success, 7 error, 1 validation)
- [ ] AdminSettingsScreen.js (needs review)

**Priority 1c - Job Management** (Core business)
- [ ] JobCreate.js (needs review)
- [ ] AssignJobModal.js (needs review)

### TIER 2: WORKFLOWS & FEATURES (Important)
- [ ] EmployeeConversionScreen.js
- [ ] MyTimesheetScreen.js
- [ ] PreonboardingModal.js
- [ ] OfferListing.js
- [ ] InterventionQueueScreen.js
- [ ] MyTasksScreen.js
- [ ] RehireApprovalsScreen.js

### TIER 3: DASHBOARDS & ANALYTICS (Lower impact)
- [ ] TroyPartnerDashboard.js
- [ ] CFOAgentScreen.js
- [ ] ThunderAnalyticsScreen.js
- [ ] RiskDashboardScreen.js
- [ ] ExecutiveSignalScreen.js
- [ ] CEOFYProgressScreen.js

### TIER 4: MODALS & COMPONENTS (Isolated)
- [ ] PreonboardingDrawer.js
- [ ] SignatureModal.js
- [ ] MoveStageDrawer.js
- [ ] L1ToL2WorkflowPanel.js
- [ ] NoShowConfirmation.js
- [ ] PreviousOfferModal.js

### TIER 5: ADMIN & CONFIGURATION
- [ ] TenantAIConfigScreen.js
- [ ] ChecklistTemplatesScreen.js
- [ ] TicketRoutingAdminScreen.js
- [ ] BuddyProgramScreen.js
- [ ] BuddyProgramListScreen.js
- [ ] ErrorLogScreen.js

### TIER 6: COMPLEX FEATURES (Agent-driven, lower priority)
- [ ] FlashWidget.js
- [ ] ThunderMemorySection.js
- [ ] ThunderAssignmentSection.jsx
- [ ] BulkLaunchScreen.js
- [ ] PartnerROIAgentScreen.js
- [ ] AgentStandupsScreen.js
- [ ] BISExplorerScreen.js
- [ ] BUSwitcher.js
- [ ] MessagesTab.js
- [ ] InterviewsTab.js
- [ ] IntelligenceTab.js
- [ ] ProfileTabEditable.js
- [ ] FileUploadPanel.js
- [ ] JobWorkspaceScreen.js
- [ ] Others...

---

## Migration Strategy

### Phase 1: Core CRUD (High Impact)
1. **Candidate operations** - 5 files
2. **User operations** - 2 files
3. **Job operations** - 2 files
4. Total impact: ~50% of daily operations

### Phase 2: Workflows (Medium Impact)
1. **Timesheets, Offers, Pre-boarding** - 5 files
2. Total impact: ~30% of operations

### Phase 3: Dashboards & Polish (Low Impact)
1. **Analytics, Configuration** - 20+ files
2. Total impact: ~20% of operations

---

## Implementation Plan

### Step 1: Create Wrapper Hook (1 screen = template)
- Use CandidateCreate as template
- Show pattern for: validation errors, API errors, success
- Document best practices

### Step 2: Migrate TIER 1 (Top priority)
- [ ] CandidateCreate.js (1 hour)
- [ ] CandidateDetailsScreen.js (1.5 hours)
- [ ] UsersAndAccessControl.js (2 hours)
- [ ] JobCreate.js (1 hour)

### Step 3: Migrate TIER 2 (Medium impact)
- [ ] 5 workflow screens (3-4 hours)

### Step 4: Migrate TIER 3-6 (Polish)
- [ ] Remaining 35+ files (6-8 hours)

---

## Key Decisions

1. **Validation errors** → ScreenLevelBanner type="error" (red, persistent)
2. **API errors** → ScreenLevelBanner type="error" + retry button
3. **Success** → ScreenLevelBanner type="success" (auto-dismiss 3s)
4. **Warnings** → ScreenLevelBanner type="warning" or type="error" with context
5. **No toasts anywhere** - complete removal from all imports

---

## Testing Checklist (per screen)

- [ ] Validation error shows at top (no toast)
- [ ] Validation error dismissible
- [ ] API error shows with message
- [ ] Retry button works on API error
- [ ] Success message auto-dismisses
- [ ] No toasts appear anywhere
- [ ] Multiple errors don't stack
- [ ] Banner doesn't block UI

---

**Total Files**: 51  
**Estimated Time**: 12-16 hours  
**Priority**: TIER 1 first (4 files, ~4 hours)

