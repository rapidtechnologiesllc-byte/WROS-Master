# Create User Form UX Improvements - TODO

## Completed
✅ Email is now the username (no separate user_name field needed)
✅ Removed "User name is required" error blocker
✅ Made Name, Job Title, Email, Password mandatory

## Pending Improvements

### 1. Reorder Form Fields
**Current order:**
- Name
- Job Title
- Partner
- Email
- Password
- Role Template
- Business Unit

**Desired order:**
- Name ✓
- Job Title ✓
- Email ✓
- Password ✓
- Role Template ✓
- **Business Unit** (moved UP, before Partner)
- **Partner** (moved DOWN, after Business Unit)

### 2. Auto-generate Partner from Business Unit
- When Business Unit is selected, auto-populate Partner based on Business Unit selection
- Get the partner associated with the selected BU
- This will simplify the form and ensure consistency

### 3. Add Required Indicators
- Add asterisks (*) to required fields in the form labels
- Current required: Name, Job Title, Email, Password, Role Template, Business Unit

## Implementation Notes
- All three improvements are cosmetic/UX in nature
- No backend changes needed
- Focus on form structure and conditional logic
- Test after implementing to ensure Business Unit selection properly auto-fills Partner

## Files to Update
- `/src/screens/UsersAndAccessControl.js` - lines 667-803 (Create User Modal JSX)

## Priority
- Medium: These are nice-to-have UX improvements
- User creation is now unblocked; these just polish the experience
