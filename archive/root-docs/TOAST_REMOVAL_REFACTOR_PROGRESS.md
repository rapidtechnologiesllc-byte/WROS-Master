# Toast.error() & toast.warning() Removal - Refactoring Progress

## Summary
Removing all toast notification calls and replacing with page-level error/warning state management. Errors only display after user actions, not on page load.

---

## COMPLETED FILES (3)

### 1. **frontend/src/screens/LinkedInPipelineScreen.js** ✅ COMPLETE
**Toast calls removed:** 10 total
- Line 65: `toast.error("Please enter a LinkedIn URL")`
- Line 80: `toast.success("✅ Candidate added to pipeline!")`
- Line 84: `toast.warning(...)`
- Line 86: `toast.info(...)`
- Line 90: `toast.error(msg)`
- Line 99: `toast.error("Please enter a phone number")`
- Line 112: `toast.success("✅ Candidate imported!")`
- Line 118: `toast.error(msg)`
- Line 129: `toast.success("✅ Status updated")`
- Line 132: `toast.error("Failed to update status")`

**Changes made:**
1. Removed `import { toast } from "react-toastify"`
2. Added imports: `AlertCircle, CheckCircle, X` from lucide-react
3. Added state: `[error, setError]`, `[actionError, setActionError]`, `[actionSuccess, setActionSuccess]`
4. Updated handlers:
   - `handleQueueCandidate()`: Replaced 4 toast calls with state updates
   - `handleCompleteImport()`: Replaced 2 toast calls with state updates
   - `handleUpdateStatus()`: Replaced 2 toast calls with state updates
5. Added 3 error/success banners:
   - **Load error banner** (bg-red-50): Shows on mount if loadPipeline fails, has "Try Again" button
   - **Action error banner** (bg-red-50): Shows after user action errors, dismissible
   - **Action success banner** (bg-green-50): Shows after successful actions, dismissible

**Pattern applied:**
```javascript
// Before
catch (error) {
  toast.error("Failed to do something");
}

// After
catch (error) {
  setActionError("Failed to do something");
}
```

---

### 2. **frontend/src/screens/UsersAndAccessControl.js** ✅ COMPLETE
**Toast calls removed:** 15 total

**Sections updated:**

#### a) UsersSection
- **Toast calls removed:** 3
- `handleDelete()`: Line 233, 237
- `handleResetPassword()`: Line 246, 256, 261
- **Changes:** Added `actionError, actionSuccess` state, updated handlers
- **Banners added:** Error and success banners in section return

#### b) RoleTemplatesSection
- **Toast calls removed:** 10
- `handleTogglePermission()`: Line 498, 500
- `handleToggleModule()`: Line 546, 548
- `handleCreateRole()`: Line 559, 564, 579, 586
- `handleToggleTemplateStatus()`: Line 611, 614
- **Changes:** Added `actionError, actionSuccess` state, updated all handlers
- **Banners added:** Error and success banners in section return

#### c) BusinessUnitsSection
- **Toast calls removed:** 2
- `handleDeleteBusinessUnit()`: Line 966, 968
- **Changes:** Added `actionError, actionSuccess` state, updated handler
- **Banners added:** Error and success banners in section return

#### d) OrganizationalHierarchySection
- **Toast calls removed:** 8
- `handleAddOrgNode()`: Line 1097, 1111, 1120
- `handleAddPosition()`: Line 1137
- `handleDeletePosition()`: Line 1143
- `handleSaveEditedOrgNode()`: Line 1160, 1181
- `handleDeleteOrgNode()`: Line 1187
- **Changes:** Added `actionError, actionSuccess` state, updated all handlers
- **Banners added:** Error and success banners in section return

#### e) LocationsSection
- **Toast calls removed:** 1
- `handleDelete()`: Line 1504
- **Changes:** Added `actionSuccess` state, updated handler
- **Banners added:** Success banner in section return

**Pattern for all sections:**
- Import icons: `AlertCircle, CheckCircle, X` from lucide-react (top of file)
- Add state in each component: `const [actionError, setActionError] = useState(null)`
- Clear error before action: `setActionError(null)` at start of handler
- Replace toast calls with state updates
- Add dismissible error/success banners with close buttons (X icon)

---

### 3. **frontend/src/screens/CandidateAssignJobModal.js** ✅ COMPLETE
**Toast calls removed:** 12 total
- Line 323: `toast.error("Failed to load jobs")`
- Line 412: `toast.error("Please select a candidate")`
- Line 416: `toast.error("Please select a job")`
- Line 421: `toast.error("Please select submittal date")`
- Line 426: `toast.error("Please select submittal time")`
- Line 431: `toast.error("Please select time zone")`
- Line 435: `toast.error("Please enter agreed pay rate")`
- Line 445: `toast.warning(...experience)`
- Line 469: `toast.error(...budget alert)`
- Line 478: `toast.warning(...pay frequency)`
- Line 525: `toast.success("Job submitted successfully ✅")`
- Line 530: `toast.error("Failed to submit job")`
- Line 533: `toast.error(getSubmitJobErrorMessage(err))`

**Changes made:**
1. Removed `import { toast } from "react-toastify"`
2. Added imports: `AlertCircle, CheckCircle, X` to lucide-react import (FileText was already imported)
3. Added state: `[actionError, setActionError]`, `[actionSuccess, setActionSuccess]`
4. Updated handlers:
   - `fetchJobs()` in useEffect: Replaced 1 toast call with state update
   - `validateForm()`: Replaced 6 toast calls with state updates
   - `handleSaveJob()`: Replaced 3 toast calls with state updates
5. Added error/success banners (modal style):
   - **Action error banner** (bg-red-50): Shows validation errors and async errors, dismissible
   - **Action success banner** (bg-green-50): Shows submission success, dismissible

**Special handling:**
- Modal component: Banners placed inside Card, after opening tag
- Validation errors: Set immediately in validateForm() before return
- Budget warnings: Treated as errors (setActionError) to show in banner
- Success on submission: Auto-closes modal after setting actionSuccess

---

## REMAINING FILES (34 files)

### High Priority (12-15 toast calls each)
1. **AdminSettingsScreen.js** - 12 toast calls
2. **CandidateAssignJobModal.js** - 12 toast calls
3. **admin/OrganizationSection.jsx** - 10 toast calls
4. **tabs/ProfileTabEditable.js** - 10 toast calls
5. **EmployeeConversionScreen.js** - 10 toast calls

### Medium Priority (7-8 toast calls each)
6. UserFormPage.jsx - 9 toast calls
7. OfferListing.js - 8 toast calls
8. MyTasksScreen.js - 7 toast calls
9. tabs/MessagesTab.js - 7 toast calls
10. PreonboardingModal.js - 7 toast calls

### Lower Priority (4-6 toast calls each)
11. RoleTemplateEditor.jsx - 6 toast calls
12. ExecutiveSignalScreen.js - 6 toast calls
13. BulkLaunchScreen.js - 5 toast calls
14. TenantAIConfigScreen.js - 5 toast calls
15. CertificationManagementScreen.js - 5 toast calls
16. MyTimesheetScreen.js - 4 toast calls
17. BIExplorerScreen.js - 4 toast calls
18. AgentStandupsScreen.js - 4 toast calls

### Plus 20+ additional files with 1-3 toast calls each

---

## REFACTORING APPROACH / PATTERN

For each file, apply the following standard pattern:

### 1. Import Changes
```javascript
// Remove
import { toast } from "react-toastify";

// Add to lucide-react imports
AlertCircle, CheckCircle, X
```

### 2. State Management
```javascript
// Add to component
const [actionError, setActionError] = useState(null);
const [actionSuccess, setActionSuccess] = useState(null);
```

### 3. Handler Updates
```javascript
// Template for all async handlers
const handleSomething = async () => {
  setActionError(null);  // Clear before action
  setActionSuccess(null);
  
  try {
    // ... do work
    setActionSuccess("Success message");
  } catch (err) {
    setActionError(err.message || "Default error");
  }
};
```

### 4. Validation Errors
```javascript
// For immediate validation (not async)
const handleValidation = (input) => {
  setActionError(null);
  
  if (!input.trim()) {
    setActionError("Input is required");
    return;
  }
  
  // ... continue
};
```

### 5. Banner Placement
Add near top of returned JSX, after any load-time error banners:
```javascript
return (
  <div className="space-y-6">
    {/* Error Banner */}
    {actionError && (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
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

    {/* Success Banner */}
    {actionSuccess && (
      <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
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
    
    {/* Rest of component */}
  </div>
);
```

### 6. Special Cases

**For modals/overlays:**
- Place error/success banners inside the modal, at top
- Auto-dismiss success messages after 3-5 seconds (optional):
  ```javascript
  useEffect(() => {
    if (actionSuccess) {
      const timer = setTimeout(() => setActionSuccess(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [actionSuccess]);
  ```

**For forms:**
- Clear errors when user starts editing: `onChange={() => setActionError(null)}`
- Show validation errors immediately (not async)

**For data loading (useEffect):**
- Load errors should be separate from action errors
- Use `[error, setError]` for load-time errors
- Load errors typically shown at component level, not auto-dismissed

---

## TESTING CHECKLIST

For each updated file:
- [ ] No import of `toast` from react-toastify
- [ ] All `toast.error()` calls replaced with `setActionError()`
- [ ] All `toast.warning()` calls replaced with `setActionError()` or `setActionSuccess()`
- [ ] All `toast.success()` calls replaced with `setActionSuccess()`
- [ ] All `toast.info()` calls replaced with appropriate state
- [ ] Error banners only show after user actions (not on page load)
- [ ] Success messages dismiss-able or auto-dismiss
- [ ] Error clearing on: next action start, close button, page navigation
- [ ] Form validation errors show immediately in error banner
- [ ] API errors show in error banner with message from backend
- [ ] No orphaned toast references in comments

---

## Files Updated In This Session
1. ✅ LinkedInPipelineScreen.js (10 toast calls)
2. ✅ UsersAndAccessControl.js (15 toast calls)
3. ✅ CandidateAssignJobModal.js (12 toast calls)

**Total toast calls removed: 37 out of 110+**
**Completion: ~33% of high-priority files**
**Files remaining: 34+ files**

---

## Next Steps

For optimal efficiency, prioritize files in this order:
1. **AdminSettingsScreen.js** - High impact (12 calls, common admin flows)
2. **CandidateAssignJobModal.js** - High impact (12 calls, core recruitment flow)
3. **tab/ProfileTabEditable.js** - High impact (10 calls, frequently used)
4. **EmployeeConversionScreen.js** - Medium impact (10 calls)
5. Rest in order of toast count

Each file takes approximately 15-25 minutes to refactor depending on complexity.

