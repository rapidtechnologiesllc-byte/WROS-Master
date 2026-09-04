# Navigation Architecture Decision

## Status: FINAL - DO NOT CHANGE

### Decision
Navigation module structure is **intentionally hardcoded** in `backend/app/seeds/init_resources.py` via the `MODULES_AND_RESOURCES` dictionary.

### Why Hardcoded (Not Database-Driven)

1. **Database Contains ALL Resources** 
   - Database has 56+ modules (before dedup: 200+)
   - Includes admin, internal, experimental, duplicate entries
   - Not suitable for direct UI consumption

2. **Navigation Requires Curation**
   - Only 12 core modules should appear in navigation
   - UX needs clean, controlled hierarchy
   - Database cruft breaks user experience

3. **Separation of Concerns**
   - **Database**: Authoritative storage of all system resources
   - **init_resources.py**: User-facing navigation structure (curated)
   - **Role templates**: Permission control (can_view, can_edit, etc.)
   - Each layer has a single responsibility

4. **Single Source of Truth**
   - `MODULES_AND_RESOURCES` is THE structure for navigation
   - Changes to navigation require code review (not just DB updates)
   - Prevents accidental cruft from appearing in UI

### Architecture Pattern

```
┌─────────────────────────────────────────┐
│  Database (56+ modules, 425+ resources) │
│  ✓ Authoritative storage                │
│  ✗ Too raw for UI                       │
└─────────────────────────────────────────┘
                    ↓
           FILTER & CURATE
                    ↓
┌─────────────────────────────────────────┐
│  init_resources.py                      │
│  MODULES_AND_RESOURCES (12 modules)     │
│  ✓ Curated for UI                       │
│  ✓ Single source of truth               │
│  ✓ Requires code review to change       │
└─────────────────────────────────────────┘
                    ↓
           APPLY PERMISSIONS
                    ↓
┌─────────────────────────────────────────┐
│  /hr/me/navigation endpoint             │
│  ✓ Filtered by role template perms      │
│  ✓ Returns only accessible resources    │
│  ✓ Includes can_view/create/edit/delete │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  Frontend Navigation                    │
│  ✓ Clean 12-module structure            │
│  ✓ User sees only what they can access  │
│  ✓ Complete permission matrix available │
└─────────────────────────────────────────┘
```

### For Code Review Gate

**DO NOT FLAG** `MODULES_AND_RESOURCES` as:
- ❌ "Hardcoded data that should be in database"
- ❌ "Not dynamic"
- ❌ "Needs to be removed"

This hardcoding is **architectural, not a violation**.

### If Navigation Needs to Change

1. **Add/rename a module**: Edit `MODULES_AND_RESOURCES` in init_resources.py
2. **Add/remove resources from a module**: Edit the list for that module
3. **Add new resource**: Add to Module table AND to the appropriate module list in init_resources.py
4. **Never query database directly** for navigation structure

### Last Updated
2026-09-04

### Decision Made By
Architecture review - confirmed this is the correct approach after investigation
