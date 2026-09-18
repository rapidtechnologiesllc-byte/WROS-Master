
import React from 'react';
import { usePermissions } from '../context/PermissionContext';
import * as permUtils from '../utils/permissionsRoleTemplate';

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

export const IfPermission = ({ permission, children, fallback = null }) => {
  const { hasPermission } = usePermissions();

  if (hasPermission(permission)) {
    return <>{children}</>;
  }

  return fallback;
};

export const IfAnyPermission = ({ permissions, children, fallback = null }) => {
  const { hasAnyPermission } = usePermissions();

  if (hasAnyPermission(permissions)) {
    return <>{children}</>;
  }

  return fallback;
};

export const IfAllPermissions = ({ permissions, children, fallback = null }) => {
  const { hasAllPermissions } = usePermissions();

  if (hasAllPermissions(permissions)) {
    return <>{children}</>;
  }

  return fallback;
};

export const IfCanViewModule = ({ module, children, fallback = null }) => {
  const { canViewModule } = usePermissions();

  if (canViewModule(module)) {
    return <>{children}</>;
  }

  return fallback;
};

export const IfCanAction = ({ module, action, children, fallback = null }) => {
  const { canAction } = usePermissions();

  if (canAction(module, action)) {
    return <>{children}</>;
  }

  return fallback;
};

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
