/**
 * Convert permission object from backend to array format for frontend
 * Backend returns: {"candidates": {"can_create": true, "can_view": true}}
 * Frontend expects: ["candidates.create", "candidates.view"]
 */
export const convertPermissionsToArray = (permissionsData) => {
  let permissionsArray = [];

  if (Array.isArray(permissionsData)) {
    return permissionsData;
  }

  if (typeof permissionsData === 'object' && permissionsData !== null) {
    Object.entries(permissionsData).forEach(([resource, actions]) => {
      if (actions && typeof actions === 'object') {
        if (actions.can_view) permissionsArray.push(`${resource}.view`);
        if (actions.can_create) permissionsArray.push(`${resource}.create`);
        if (actions.can_edit) permissionsArray.push(`${resource}.edit`);
        if (actions.can_delete) permissionsArray.push(`${resource}.delete`);
      }
    });
  }

  return permissionsArray;
};
