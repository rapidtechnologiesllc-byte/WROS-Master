/**
 * Permission Context - Global permission state management for React
 *
 * Provides:
 * - Centralized permission state
 * - Permission caching after login
 * - Permission refresh capability
 * - Context-aware permission checks throughout the app
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import * as permUtils from '../utils/permissionsRbac';

const PermissionContext = createContext();

/**
 * Permission provider component - wrap your app with this
 *
 * Usage:
 *   <PermissionProvider>
 *     <App />
 *   </PermissionProvider>
 */
export const PermissionProvider = ({ children }) => {
  const [permissions, setPermissions] = useState([]);
  const [modules, setModules] = useState([]);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Fetch user permissions from backend
   */
  const fetchPermissions = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setPermissions([]);
        setModules([]);
        setIsSuperAdmin(false);
        return;
      }

      const response = await fetch('/api/v1/users/me/permissions', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch permissions: ${response.statusText}`);
      }

      const data = await response.json();

      // Update state
      setPermissions(data.permissions || []);
      setModules(data.modules || []);
      setIsSuperAdmin(data.is_super_admin || false);

      // Cache in localStorage for offline access
      const userStr = localStorage.getItem('user') || '{}';
      const user = JSON.parse(userStr);
      user.permissions = data.permissions;
      user.modules = data.modules;
      user.is_super_admin = data.is_super_admin;
      localStorage.setItem('user', JSON.stringify(user));
    } catch (err) {
      console.error('Error fetching permissions:', err);
      setError(err.message);

      // Fall back to cached permissions
      const cached = permUtils.getUserPermissions();
      setPermissions(cached);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Load cached permissions on mount
   */
  useEffect(() => {
    const cached = permUtils.getUserPermissions();
    if (cached && cached.length > 0) {
      setPermissions(cached);

      try {
        const userStr = localStorage.getItem('user');
        const user = JSON.parse(userStr);
        setIsSuperAdmin(user.is_super_admin || false);
        setModules(user.modules || []);
      } catch (e) {
        console.error('Error parsing cached user data:', e);
      }
    }
  }, []);

  /**
   * Check if user has a specific permission
   */
  const hasPermission = useCallback((permission) => {
    return permissions.includes(permission.toLowerCase());
  }, [permissions]);

  /**
   * Check if user has any of the given permissions
   */
  const hasAnyPermission = useCallback((permissionList) => {
    return permissionList.some(perm => permissions.includes(perm.toLowerCase()));
  }, [permissions]);

  /**
   * Check if user has all of the given permissions
   */
  const hasAllPermissions = useCallback((permissionList) => {
    return permissionList.every(perm => permissions.includes(perm.toLowerCase()));
  }, [permissions]);

  /**
   * Check if user can perform an action in a module
   */
  const canAction = useCallback((moduleName, action) => {
    return hasPermission(`${moduleName}.${action}`);
  }, [hasPermission]);

  /**
   * Check if user can view a module
   */
  const canViewModule = useCallback((moduleName) => {
    return isSuperAdmin || hasPermission(`${moduleName}.view`);
  }, [isSuperAdmin, hasPermission]);

  /**
   * Check if user can create in a module
   */
  const canCreateInModule = useCallback((moduleName) => {
    return isSuperAdmin || hasPermission(`${moduleName}.create`);
  }, [isSuperAdmin, hasPermission]);

  /**
   * Check if user can edit in a module
   */
  const canEditInModule = useCallback((moduleName) => {
    return isSuperAdmin || hasPermission(`${moduleName}.edit`);
  }, [isSuperAdmin, hasPermission]);

  /**
   * Check if user can delete in a module
   */
  const canDeleteInModule = useCallback((moduleName) => {
    return isSuperAdmin || hasPermission(`${moduleName}.delete`);
  }, [isSuperAdmin, hasPermission]);

  const value = {
    permissions,
    modules,
    isSuperAdmin,
    loading,
    error,
    fetchPermissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    canAction,
    canViewModule,
    canCreateInModule,
    canEditInModule,
    canDeleteInModule
  };

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
};

/**
 * Hook to use permission context
 *
 * Usage:
 *   const { hasPermission, canCreateInModule } = usePermissions();
 *
 *   if (!hasPermission('candidates.view')) {
 *     return <div>You don't have permission to view candidates</div>;
 *   }
 */
export const usePermissions = () => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error('usePermissions must be used within PermissionProvider');
  }
  return context;
};

/**
 * Hook to require a specific permission
 * Renders nothing if permission is not granted
 *
 * Usage:
 *   const CanCreateCandidates = useRequirePermission('candidates.create');
 *   return CanCreateCandidates ? <Button>Create Candidate</Button> : null;
 */
export const useRequirePermission = (permission) => {
  const { hasPermission } = usePermissions();
  return hasPermission(permission);
};

/**
 * HOC to require permission - wraps component and conditionally renders
 *
 * Usage:
 *   const ProtectedComponent = withPermission(MyComponent, 'candidates.create');
 */
export const withPermission = (Component, permission) => {
  return (props) => {
    const { hasPermission } = usePermissions();

    if (!hasPermission(permission)) {
      return null;
    }

    return <Component {...props} />;
  };
};

/**
 * Hook to require any of multiple permissions
 *
 * Usage:
 *   const canManageRecruitment = useRequireAnyPermission(['recruitment.view', 'recruitment.manage']);
 */
export const useRequireAnyPermission = (permissions) => {
  const { hasAnyPermission } = usePermissions();
  return hasAnyPermission(permissions);
};

/**
 * Hook to require all of multiple permissions
 *
 * Usage:
 *   const canApproveOffers = useRequireAllPermissions(['offers.view', 'offers.approve']);
 */
export const useRequireAllPermissions = (permissions) => {
  const { hasAllPermissions } = usePermissions();
  return hasAllPermissions(permissions);
};

export default PermissionContext;
