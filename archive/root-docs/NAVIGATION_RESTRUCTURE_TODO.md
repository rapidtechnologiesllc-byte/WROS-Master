# TODO: Administration Navigation Restructure

## Issue
Current Administration nav menu shows "Role Templates" as a separate nav item, but it should be:
- Accessible only via tabs in "Users & Access Control" page
- Not as a standalone sidebar menu item

## Desired Navigation Structure
The Administration menu group should have:
1. **Users & Access Control** → `/admin/users-access-control` (with tabs: Users, Business Units, Delivery Centers, Org Hierarchy, Role Templates)
2. **System Settings** → `/admin/system-settings` (new page for Organization, Error Log, AI Thresholds, SLA, Channels, Locale)
3. **Templates** → `/admin/system-settings/message-templates` (or separate page)
4. **Certifications** → `/admin/certifications`

## Current State
Navigation is generated from backend `/hr/me/navigation` endpoint.
Items currently showing under Administration sidebar:
- Users (nav item) - ❌ Should not be standalone sidebar item
- Role Templates (nav item) - ❌ Should be removed from sidebar (access via Users & Access Control tabs)
- Business Units (nav item) - ❌ Should not be standalone sidebar item
- Error Log (nav item) - ❌ Should move to System Settings group
- Certifications (nav item) - ✓ Keep
- Message Templates (nav item) - ❌ Should move to System Settings or Templates group

## Files to Update
1. **Backend Navigation Builder** - Update how `/hr/me/navigation` generates Administration group items
   - Remove: Users, Role Templates, Business Units, Error Log as standalone nav items
   - Consolidate under proper groups: Users & Access Control, System Settings
   
2. **Frontend moduleConfig.js** - Update to reflect new navigation structure

3. **Frontend Routes.js** - Add routes for new System Settings pages if needed

## Implementation Steps
1. Update backend navigation generation to create proper Administration structure
2. Create System Settings landing page component
3. Move Error Log, AI Config, Locale settings to System Settings group
4. Verify all admin features remain accessible
5. Test permission enforcement with new navigation

## Status
- [x] Fix #1: Role template creation modal - DONE
- [ ] Fix #2: Administration navigation restructure - PENDING

## Priority
HIGH - Users need clear navigation to find Admin features
