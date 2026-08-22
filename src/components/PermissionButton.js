/**
 * PermissionButton - Button component that respects user permissions
 *
 * Automatically disables or hides button based on permission checks.
 * Shows tooltip explaining why button is disabled if no permission.
 */

import React from 'react';
import { usePermissions } from '../context/PermissionContext';
import * as permUtils from '../utils/permissionsRbac';

/**
 * Button that requires a specific permission to be enabled
 *
 * Usage:
 *   <PermissionButton
 *     permission="candidates.create"
 *     onClick={handleCreateCandidate}
 *   >
 *     Create Candidate
 *   </PermissionButton>
 *
 * Props:
 *   - permission: Permission string (e.g., 'candidates.create')
 *   - onClick: Click handler
 *   - hideIfDenied: If true, hide button instead of disabling it (default false)
 *   - children: Button text
 *   - ... any other Button props (className, style, etc.)
 */
export const PermissionButton = ({
  permission,
  onClick,
  hideIfDenied = false,
  children,
  showTooltip = true,
  ...buttonProps
}) => {
  const { hasPermission } = usePermissions();
  const granted = hasPermission(permission);

  // Hide button if no permission and hideIfDenied is true
  if (!granted && hideIfDenied) {
    return null;
  }

  // Build tooltip text
  const tooltip = showTooltip && !granted
    ? permUtils.getPermissionTooltip(permission)
    : '';

  return (
    <button
      onClick={onClick}
      disabled={!granted}
      title={tooltip}
      {...buttonProps}
    >
      {children}
    </button>
  );
};

/**
 * Link component that requires permission
 *
 * Usage:
 *   <PermissionLink to="/admin" permission="administration.view">
 *     Admin Panel
 *   </PermissionLink>
 */
export const PermissionLink = ({
  permission,
  to,
  hideIfDenied = false,
  showTooltip = true,
  children,
  ...linkProps
}) => {
  const { hasPermission } = usePermissions();
  const granted = hasPermission(permission);

  if (!granted && hideIfDenied) {
    return null;
  }

  const tooltip = showTooltip && !granted
    ? permUtils.getPermissionTooltip(permission)
    : '';

  if (!granted) {
    // Return disabled link element
    return (
      <a
        href="#"
        onClick={(e) => e.preventDefault()}
        style={{ opacity: 0.5, cursor: 'not-allowed', pointerEvents: 'none' }}
        title={tooltip}
        {...linkProps}
      >
        {children}
      </a>
    );
  }

  return (
    <a href={to} {...linkProps}>
      {children}
    </a>
  );
};

/**
 * Conditional render component - renders children only if permission is granted
 *
 * Usage:
 *   <IfPermission permission="candidates.create">
 *     <CreateCandidateForm />
 *   </IfPermission>
 *
 *   <IfPermission permission="candidates.delete" fallback={<p>No delete access</p>}>
 *     <DeleteButton />
 *   </IfPermission>
 */
export const IfPermission = ({ permission, children, fallback = null }) => {
  const { hasPermission } = usePermissions();

  if (hasPermission(permission)) {
    return <>{children}</>;
  }

  return fallback;
};

/**
 * Conditional render if user has ANY of the permissions
 *
 * Usage:
 *   <IfAnyPermission permissions={['candidates.edit', 'candidates.manage']}>
 *     <EditCandidateForm />
 *   </IfAnyPermission>
 */
export const IfAnyPermission = ({ permissions, children, fallback = null }) => {
  const { hasAnyPermission } = usePermissions();

  if (hasAnyPermission(permissions)) {
    return <>{children}</>;
  }

  return fallback;
};

/**
 * Conditional render if user has ALL permissions
 *
 * Usage:
 *   <IfAllPermissions permissions={['offers.view', 'offers.approve']}>
 *     <ApproveOfferForm />
 *   </IfAllPermissions>
 */
export const IfAllPermissions = ({ permissions, children, fallback = null }) => {
  const { hasAllPermissions } = usePermissions();

  if (hasAllPermissions(permissions)) {
    return <>{children}</>;
  }

  return fallback;
};

/**
 * Conditional render based on module access
 *
 * Usage:
 *   <IfCanViewModule module="administration">
 *     <AdminPanel />
 *   </IfCanViewModule>
 */
export const IfCanViewModule = ({ module, children, fallback = null }) => {
  const { canViewModule } = usePermissions();

  if (canViewModule(module)) {
    return <>{children}</>;
  }

  return fallback;
};

/**
 * Conditional render for action in module
 *
 * Usage:
 *   <IfCanAction module="candidates" action="create">
 *     <CreateButton />
 *   </IfCanAction>
 */
export const IfCanAction = ({ module, action, children, fallback = null }) => {
  const { canAction } = usePermissions();

  if (canAction(module, action)) {
    return <>{children}</>;
  }

  return fallback;
};

/**
 * Permission-aware input component
 *
 * Usage:
 *   <PermissionInput
 *     permission="candidates.edit"
 *     value={candidateName}
 *     onChange={handleChange}
 *   />
 */
export const PermissionInput = ({
  permission,
  children,
  showTooltip = true,
  ...inputProps
}) => {
  const { hasPermission } = usePermissions();
  const granted = hasPermission(permission);

  const tooltip = showTooltip && !granted
    ? permUtils.getPermissionTooltip(permission)
    : '';

  return (
    <input
      disabled={!granted}
      title={tooltip}
      {...inputProps}
    />
  );
};

/**
 * Permission denied fallback component
 *
 * Usage:
 *   <PermissionDeniedFallback permission="candidates.delete" />
 */
export const PermissionDeniedFallback = ({ permission }) => {
  const message = permUtils.getPermissionErrorMessage(
    permission.split('.')[1],
    permission.split('.')[0]
  );

  return (
    <div style={{
      padding: '16px',
      backgroundColor: '#fee',
      border: '1px solid #fcc',
      borderRadius: '4px',
      color: '#c00'
    }}>
      <strong>Permission Denied</strong>
      <p>{message}</p>
    </div>
  );
};

export default PermissionButton;
