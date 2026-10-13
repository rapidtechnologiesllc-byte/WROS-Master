# URL-Based Navigation Refactor - Implementation Guide

## Overview

This guide documents the complete pattern for transforming tab-based pages to URL-routed sections. Phase 1 (AdminSettingsScreen) is complete and serves as a template for Phases 2-9.

## Phase 1: AdminSettingsScreen (COMPLETE)

### URL Structure
```
/admin/settings → (redirect to /admin/settings/organization)
/admin/settings/organization → Business Units (default)
/admin/settings/organization/business-units
/admin/settings/organization/delivery-centers
/admin/settings/organization/hierarchy
/admin/settings/ai-thresholds
/admin/settings/sla
/admin/settings/channels
/admin/settings/locale
```

### Files Created/Modified

**New Components:**
- `src/screens/admin/AdminSettingsLayout.jsx` - Sidebar navigation and layout wrapper
- `src/screens/admin/AIThresholdsSection.jsx` - AI Thresholds config rows
- `src/screens/admin/SLASection.jsx` - SLA config rows
- `src/screens/admin/ChannelsSection.jsx` - Channels config rows
- `src/screens/admin/LocaleSection.jsx` - Locale display + link to dedicated page
- `src/screens/admin/OrganizationSection.jsx` - Organization with internal tabs

**Modified Files:**
- `src/utils/Routes.js` - Added route constants
- `src/routes/Approutes.jsx` - Added nested routes + wrapper components

### Component Architecture

```
AdminSettingsLayout (provides sidebar navigation)
├── OrganizationSection (with useParams for tab)
│   ├── Business Units UI
│   ├── Delivery Centers UI
│   └── Organizational Hierarchy UI
├── AIThresholdsSection (config rows)
├── SLASection (config rows)
├── ChannelsSection (config rows)
└── LocaleSection (read-only display)
```

### Data Flow

1. Wrapper component loads settings from API
2. Settings passed to section component
3. Section renders based on URL param (orgTab)
4. Navigation links update URL
5. Browser back/forward work automatically

## Phase 2-9: Remaining Pages

### Pages to Refactor (in order)

| Phase | Page | Current Route | Tab Count | Estimated LOC |
|-------|------|---------------|-----------|--------------|
| 2 | UsersAndAccessControl | `/admin/users-access-control` | 5 | 2000+ |
| 3 | CandidateDetailsScreen | `/candidates/details` | 6+ | 1500+ |
| 4 | JobDetails | `/jobs/details` | 4 | 1200+ |
| 5 | EmployeesConsolidatedScreen | `/employees` | 3 | 1000+ |
| 6 | JobWorkspaceScreen | `/jobs/workspace` | 5 | 1500+ |
| 7 | CertificationManagementScreen | `/admin/certifications` | 3 | 800+ |
| 8 | CEOUnifiedDashboard | `/ceo-fy-progress` | 6+ | 1800+ |
| 9 | BIExplorerScreen | `/bi-explorer` | 2 | 1000+ |
| 10 | CFOAgentScreen | `/cfo-dashboard` | 4 | 1200+ |

### Implementation Template

For each page, follow this 6-step process:

#### Step 1: Analyze Current Page

Read the existing component and identify:
- All tabs/sections
- Section names and keys
- Data loaded for each section
- Modals and nested state
- Permission checks

**Example from AdminSettingsScreen:**
```javascript
const CATEGORIES = [
  { key: "ORGANIZATION", label: "Organization" },
  { key: "AI_THRESHOLDS", label: "AI Thresholds" },
  // ...
];
```

#### Step 2: Design URL Structure

Create URL patterns for each tab:
```
/admin/settings → Main page
/admin/settings/organization → First tab
/admin/settings/ai-thresholds → Second tab
...
```

**Guidelines:**
- Use lowercase with hyphens (kebab-case)
- Group related sections under parent routes
- Keep URLs short but descriptive
- Avoid numeric IDs in section routes (only in detail/edit routes)

#### Step 3: Add Route Constants

Update `src/utils/Routes.js`:

```javascript
// Add to ROUTES object
ADMIN_SETTINGS: "/admin/settings",
ADMIN_SETTINGS_ORGANIZATION: "/admin/settings/organization",
ADMIN_SETTINGS_AI_THRESHOLDS: "/admin/settings/ai-thresholds",
// ... for each section
```

#### Step 4: Create Section Components

Create individual section components in `src/screens/{feature}/`:

```javascript
// src/screens/admin/AIThresholdsSection.jsx
export default function AIThresholdsSection({ panel, onSave, loading }) {
  // Render section content
  // Accept data via props instead of state
}
```

**Key principles:**
- Each section is a separate component
- Accept all data via props
- No state management for tab selection
- Use callbacks for data mutations

#### Step 5: Create Layout Component

Create a layout wrapper with sidebar navigation:

```javascript
// src/screens/admin/AdminSettingsLayout.jsx
export default function AdminSettingsLayout({ section, children, title, subtitle }) {
  return (
    <div className="flex gap-6">
      <aside>
        {/* Navigation buttons linking to URLs */}
      </aside>
      <main>
        {/* Render children */}
      </main>
    </div>
  );
}
```

#### Step 6: Update Routes in Approutes.jsx

1. Import new components
2. Create wrapper components for data loading
3. Add routes to Approutes.jsx

```javascript
// Imports
import MyLayout from "../screens/myfeature/MyLayout";
import MySection from "../screens/myfeature/MySection";

// Wrapper components (before export default)
const MyFeaturePage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  return (
    <MyLayout section="section-key">
      <MySection data={data} />
    </MyLayout>
  );
};

// Routes (in the Route tree)
<Route path="my-feature" element={<MyFeatureRedirect />} />
<Route path="my-feature/section-one" element={<MyFeatureSectionOnePage />} />
<Route path="my-feature/section-two" element={<MyFeatureSectionTwoPage />} />
```

## Common Patterns

### Redirect on Main Route

```javascript
const MyFeatureRedirect = () => {
  const navigate = useNavigate();
  useEffect(() => {
    navigate(ROUTES.MY_FEATURE_FIRST_SECTION);
  }, [navigate]);
  return <div>Redirecting...</div>;
};
```

### Nested Tabs (like Organization)

Use useParams to get the tab from URL:

```javascript
// Route
<Route path="admin/settings/organization/:tab" element={<OrganizationPage />} />

// Component
function OrganizationPage() {
  const { tab } = useParams();
  const [activeTab] = useState(tab || 'business-units');
  
  return <OrganizationSection activeTab={activeTab} />;
}

// Navigation
<button onClick={() => navigate('/admin/settings/organization/delivery-centers')}>
  Delivery Centers
</button>
```

### Role-Based Section Visibility

```javascript
// Layout component
const SECTIONS = [
  { key: 'users', label: 'Users', permission: 'user.manage' },
  { key: 'roles', label: 'Roles', permission: 'role.manage' },
];

const visibleSections = SECTIONS.filter(s => hasPermission(s.permission));

{visibleSections.map(section => (
  <button key={section.key} onClick={() => navigate(section.route)}>
    {section.label}
  </button>
))}
```

### Form Validation and Error Handling

```javascript
const handleSave = async (key, value) => {
  try {
    await updateSetting(key, value);
    toast.success('Settings updated');
    // Reload data
    await loadPanel();
  } catch (err) {
    if (err.status === 403) setForbidden(true);
    else toast.error(err.message);
  }
};
```

## Testing Checklist

For each page, verify:

- [ ] URL loads correct section
- [ ] Invalid URLs show 404 or redirect
- [ ] Browser back/forward work
- [ ] Bookmarks/deep links work
- [ ] Super User can access all sections
- [ ] Admin can access admin sections only
- [ ] HR Manager sees only permitted sections
- [ ] Recruiter sees only permitted sections
- [ ] Employee sees minimal sections
- [ ] Data saves correctly
- [ ] Modals close/open correctly
- [ ] Mobile responsive
- [ ] No console errors
- [ ] Permission checks work
- [ ] Role templates respected

## Performance Considerations

1. **Lazy Loading**: Each wrapper component loads its own data
2. **Caching**: Consider React Query or SWR for API caching
3. **Code Splitting**: Use React.lazy() for large sections
4. **State Management**: Keep state local to section components

## Backward Compatibility

- Keep old routes working during transition (optional)
- Old `/admin/settings` can redirect to new structure
- API endpoints unchanged

## Rollout Plan

**Week 1-2:**
- Phase 1: AdminSettingsScreen (DONE)
- Phase 2: UsersAndAccessControl

**Week 2-3:**
- Phase 3: CandidateDetailsScreen
- Phase 4: JobDetails

**Week 3-4:**
- Phase 5: EmployeesConsolidatedScreen
- Phase 6: JobWorkspaceScreen

**Week 4-5:**
- Phase 7: CertificationManagementScreen
- Phase 8: CEOUnifiedDashboard

**Week 5:**
- Phase 9: BIExplorerScreen
- Phase 10: CFOAgentScreen (optional)

## Key Files Reference

### Route Constants
- `src/utils/Routes.js` - All route definitions

### Components
- `src/screens/admin/` - Admin section components
- `src/screens/{feature}/` - Feature-specific sections

### Routing
- `src/routes/Approutes.jsx` - Main route definitions

## API Endpoints Used

By Phase and feature:

**Admin Settings:**
- GET `/system-config/settings` - Read all settings
- PUT `/system-config/settings/{key}` - Update setting
- GET `/bu-context/available-buses` - Business units
- GET `/org/nodes` - Organizational structure

**Users & Access Control:**
- GET `/hr/users/all` - All users
- POST `/users/create` - Create user
- PUT `/users/{id}` - Update user
- GET `/rbac/roles` - Available roles

**Candidates:**
- GET `/candidates/{id}` - Candidate details
- PUT `/candidates/{id}` - Update candidate
- GET `/candidates/{id}/interviews` - Candidate interviews

**Jobs:**
- GET `/jobs/{id}` - Job details
- GET `/jobs/{id}/candidates` - Job candidates

## Troubleshooting

### Routes Not Rendering
- Check imports in Approutes.jsx
- Verify route paths match ROUTES constants
- Ensure all wrapper components are exported

### Data Not Loading
- Check useEffect dependencies
- Verify API endpoints are accessible
- Check console for 403/404 errors

### Browser History Not Working
- Ensure navigation uses navigate() from useNavigate
- Verify routes are properly nested
- Check that links point to valid ROUTES

### Mobile Issues
- Test with viewport at 375px width
- Verify sidebar collapses on mobile
- Check button touch targets (min 48px)

## Future Enhancements

1. **URL Params for Filters:**
   ```
   /admin/users?role=admin&bu=north-america
   ```

2. **URL Params for Modals:**
   ```
   /admin/users/edit/12345?modal=true
   ```

3. **Query String State:**
   ```
   /candidates/search?query=jane&status=interview
   ```

4. **Dynamic Sections:**
   Load section list from API based on permissions

5. **Analytics:**
   Track page views by URL structure

## Summary

The URL-based routing refactor:
- ✅ Makes all sections independently bookmarkable
- ✅ Enables browser history (back/forward)
- ✅ Improves share-ability of specific sections
- ✅ Prepares for advanced features (filters, modals in URL)
- ✅ Maintains backward API compatibility
- ✅ Supports role-based section visibility
- ✅ Scales across all 9+ pages

Each page follows the same 6-step pattern, making Phase 2-9 faster and more consistent.
