# Toast Removal Progress Tracking

**Started:** 2026-09-16  
**Target:** Remove ALL toast notifications from WROS frontend + replace with page-level state management

---

## 📊 Overall Statistics

| Metric | Count |
|--------|-------|
| **Files with toast imports** | 62 |
| **Total toast calls** | 263 |
| **Files completed** | 3 |
| **Toast calls removed** | 37 |
| **Files remaining** | 59 |
| **Toast calls remaining** | 226 |

---

## ✅ COMPLETED FILES (3)

1. ✅ `frontend/src/screens/LinkedInPipelineScreen.js` - 37 toast calls → state management
2. ✅ `frontend/src/screens/UsersAndAccessControl.js` - Already uses state pattern
3. ✅ `frontend/src/screens/CandidateAssignJobModal.js` - Already uses state pattern

**Pattern Reference:** See LinkedInPipelineScreen.js for the established pattern

---

## 🔴 REMAINING FILES BY PRIORITY (59 files, 226 calls)

### HIGH PRIORITY (Core workflows - 15 files, 102 calls)

| # | File | Calls | Status |
|---|------|-------|--------|
| 1 | `frontend/src/routes/wrappers/JobWorkspaceWrapper.jsx` | 2 | TODO |
| 2 | `frontend/src/routes/wrappers/CandidateDetailsWrapper.jsx` | 2 | TODO |
| 3 | `frontend/src/routes/Approutes.jsx` | 1 | TODO |
| 4 | `frontend/src/screens/CandidateDetailsScreen.js` | 3 | TODO |
| 5 | `frontend/src/screens/CandidateSearch.js` | 9 | TODO |
| 6 | `frontend/src/screens/CandidateEditModal.js` | ? | TODO |
| 7 | `frontend/src/screens/JobCreate.js` | 8 | TODO |
| 8 | `frontend/src/screens/JobWorkspaceScreen.js` | 8 | TODO |
| 9 | `frontend/src/screens/OfferListing.js` | 11 | TODO |
| 10 | `frontend/src/screens/PreonboardingModal.js` | 12 | TODO |
| 11 | `frontend/src/screens/InterviewsTab.js` | 4 | TODO |
| 12 | `frontend/src/screens/ProfileTabEditable.js` | 16 | TODO |
| 13 | `frontend/src/screens/MessagesTab.js` | 12 | TODO |
| 14 | `frontend/src/components/RoleTemplateEditor.jsx` | 8 | TODO |
| 15 | `frontend/src/screens/MyTasksScreen.js` | 11 | TODO |

### MEDIUM PRIORITY (Admin/Config - 20 files, 78 calls)

| # | File | Calls | Status |
|---|------|-------|--------|
| 16 | `frontend/src/screens/ChecklistTemplatesScreen.js` | 2 | TODO |
| 17 | `frontend/src/screens/EmployeeConversionScreen.js` | 11 | TODO |
| 18 | `frontend/src/screens/EmployeeKPIDashboard.js` | 3 | TODO |
| 19 | `frontend/src/screens/CEOGoalsSettingScreen.js` | 3 | TODO |
| 20 | `frontend/src/screens/CEOFYProgressScreen.js` | 1 | TODO |
| 21 | `frontend/src/screens/GoalsManagementScreen.js` | 3 | TODO |
| 22 | `frontend/src/screens/TenantAIConfigScreen.js` | 7 | TODO |
| 23 | `frontend/src/screens/TicketRoutingAdminScreen.js` | 4 | TODO |
| 24 | `frontend/src/screens/BusinessUnitFormPage.jsx` | 4 | TODO |
| 25 | `frontend/src/screens/DeliveryCenterFormPage.jsx` | 3 | TODO |
| 26 | `frontend/src/screens/DeliveryCentersAdmin.jsx` | 7 | TODO |
| 27 | `frontend/src/screens/UserFormPage.jsx` | 12 | TODO |
| 28 | `frontend/src/components/BUSwitcher.js` | 2 | TODO |
| 29 | `frontend/src/screens/admin/SLASection.jsx` | 2 | TODO |
| 30 | `frontend/src/screens/admin/AIThresholdsSection.jsx` | 2 | TODO |
| 31 | `frontend/src/screens/admin/ChannelsSection.jsx` | 2 | TODO |
| 32 | `frontend/src/screens/BulkLaunchScreen.js` | 7 | TODO |
| 33 | `frontend/src/screens/CertificationManagementScreen.js` | 6 | TODO |
| 34 | `frontend/src/screens/BuddyProgramScreen.js` | 4 | TODO |
| 35 | `frontend/src/screens/BuddyProgramListScreen.js` | 1 | TODO |

### LOW PRIORITY (Features/Dashboards - 24 files, 46 calls)

| # | File | Calls | Status |
|---|------|-------|--------|
| 36 | `frontend/src/components/FlashWidget.js` | 1 | TODO |
| 37 | `frontend/src/components/ThunderMemorySection.js` | 1 | TODO |
| 38 | `frontend/src/components/ThunderCandidateMetrics.js` | 5 | TODO |
| 39 | `frontend/src/components/NoShowConfirmation.js` | 1 | TODO |
| 40 | `frontend/src/components/L1ToL2WorkflowPanel.js` | 1 | TODO |
| 41 | `frontend/src/screens/AssignJobModal.js` | 5 | TODO |
| 42 | `frontend/src/screens/AgentStandupsScreen.js` | 4 | TODO |
| 43 | `frontend/src/screens/BIExplorerScreen.js` | 4 | TODO |
| 44 | `frontend/src/screens/CandidateSelfService.js` | 2 | TODO |
| 45 | `frontend/src/screens/CFOAgentScreen.js` | 1 | TODO |
| 46 | `frontend/src/screens/ErrorLogScreen.js` | 1 | TODO |
| 47 | `frontend/src/screens/ExecutiveSignalScreen.js` | 8 | TODO |
| 48 | `frontend/src/screens/InterventionQueueScreen.js` | 4 | TODO |
| 49 | `frontend/src/screens/MyReferralsScreen.js` | 2 | TODO |
| 50 | `frontend/src/screens/MyTimesheetScreen.js` | 6 | TODO |
| 51 | `frontend/src/screens/PartnerROIAgentScreen.js` | 1 | TODO |
| 52 | `frontend/src/screens/PreviousOfferModal.js` | 2 | TODO |
| 53 | `frontend/src/screens/RehireApprovalsScreen.js` | 3 | TODO |
| 54 | `frontend/src/screens/RiskDashboardScreen.js` | 2 | TODO |
| 55 | `frontend/src/screens/TroyPartnerDashboard.js` | 1 | TODO |
| 56 | `frontend/src/screens/tabs/IntelligenceTab.js` | 2 | TODO |
| 57 | `frontend/src/screens/ThunderAnalyticsScreen.js` | 1 | TODO |
| 58 | `frontend/src/components/timeline/FileUploadPanel.js` | 1 | TODO |
| 59 | `frontend/src/components/assignment/ThunderAssignmentSection.jsx` | 2 | TODO |

### OTHER FILES (5 files)

| # | File | Calls | Status |
|---|------|-------|--------|
| 60 | `frontend/src/components/ui/SignatureModal.js` | ? | TODO |
| 61 | `frontend/src/components/ui/MoveStageDrawer.js` | 1 | TODO |
| 62 | `frontend/src/components/ui/PreonboardingDrawer.js` | 1 | TODO |
| 63 | `frontend/src/components/FlashVsPanelComparison.js` | ? | TODO |
| 64 | `frontend/src/components/RoleTemplateEditor.jsx` | (already counted) | TODO |

---

## 📋 ESTABLISHED PATTERN

**Reference File:** `frontend/src/screens/LinkedInPipelineScreen.js`

### State Management
```javascript
// Page-level error (on load)
const [error, setError] = useState(null);

// User action errors/success (after interaction)
const [actionError, setActionError] = useState(null);
const [actionSuccess, setActionSuccess] = useState(null);
```

### Imports
```javascript
import { AlertCircle, CheckCircle, X } from "lucide-react";
// NO toast import
```

### Replacement Rules
- `toast.error()` → `setActionError()`
- `toast.success()` → `setActionSuccess()`
- `toast.warning()` → `setActionError()`
- `toast.info()` → `setActionSuccess()` or `setActionError()` based on context

### Banners (After user actions ONLY)
```javascript
{/* Error Banner - shows AFTER user action */}
{actionError && (
  <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
    <div className="flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-red-700 text-sm font-medium">{actionError}</p>
      </div>
      <button
        onClick={() => setActionError(null)}
        className="text-red-600 hover:text-red-800 flex-shrink-0"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  </div>
)}

{/* Success Banner - shows AFTER user action */}
{actionSuccess && (
  <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
    <div className="flex items-start gap-3">
      <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-green-700 text-sm font-medium">{actionSuccess}</p>
      </div>
      <button
        onClick={() => setActionSuccess(null)}
        className="text-green-600 hover:text-green-800 flex-shrink-0"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  </div>
)}
```

### Key Rules
1. ✅ Error/success banners show ONLY after user actions
2. ✅ NEVER show errors/successes on page load
3. ✅ Clear banners with X button
4. ✅ Use Lucide icons (AlertCircle, CheckCircle)
5. ✅ No toast library anywhere

---

## 🚀 EXECUTION PLAN

1. **Phase 1 (This session):** HIGH PRIORITY files (1-15)
2. **Phase 2 (Next session):** MEDIUM PRIORITY files (16-35)
3. **Phase 3 (Later):** LOW PRIORITY files (36-59)

**Goal:** Maintain 100% code quality while removing all toast references

---

## 📝 Session Notes

- Audit created: 2026-09-16
- Pattern verified against LinkedInPipelineScreen.js
- Ready to begin systematic removal starting with HIGH PRIORITY files

