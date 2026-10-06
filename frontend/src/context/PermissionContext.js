import { apiFetch } from "../services/api/client";

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import * as permUtils from '../utils/permissionsRoleTemplate';

const PermissionContext = createContext();

export const PermissionProvider = ({ children }) => {
  const [permissions, setPermissions] = useState([]);
  const [modules, setModules] = useState([]);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchPermissions = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('hrms_token');
      if (!token) {
        setPermissions([]);
        setModules([]);
        setIsSuperAdmin(false);
        return;
      }

      const response = await apiFetch('/api/v1/hr/me/permissions', {
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

  const hasPermission = useCallback((permission) => {
    return permissions.includes(permission.toLowerCase());
  }, [permissions]);

  const hasAnyPermission = useCallback((permissionList) => {
    return permissionList.some(perm => permissions.includes(perm.toLowerCase()));
  }, [permissions]);

  const hasAllPermissions = useCallback((permissionList) => {
    return permissionList.every(perm => permissions.includes(perm.toLowerCase()));
  }, [permissions]);

  const canAction = useCallback((moduleName, action) => {
    return hasPermission(`${moduleName}.${action}`);
  }, [hasPermission]);

  const canViewModule = useCallback((moduleName) => {
    return isSuperAdmin || hasPermission(`${moduleName}.view`);
  }, [isSuperAdmin, hasPermission]);

  const canCreateInModule = useCallback((moduleName) => {
    return isSuperAdmin || hasPermission(`${moduleName}.create`);
  }, [isSuperAdmin, hasPermission]);

  const canEditInModule = useCallback((moduleName) => {
    return isSuperAdmin || hasPermission(`${moduleName}.edit`);
  }, [isSuperAdmin, hasPermission]);

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

export const usePermissions = () => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error('usePermissions must be used within PermissionProvider');
  }
  return context;
};

export const useRequirePermission = (permission) => {
  const { hasPermission } = usePermissions();
  return hasPermission(permission);
};

export const withPermission = (Component, permission) => {
  return (props) => {
    const { hasPermission } = usePermissions();

    if (!hasPermission(permission)) {
      return null;
    }

    return <Component {...props} />;
  };
};

export const useRequireAnyPermission = (permissions) => {
  const { hasAnyPermission } = usePermissions();
  return hasAnyPermission(permissions);
};

export const useRequireAllPermissions = (permissions) => {
  const { hasAllPermissions } = usePermissions();
  return hasAllPermissions(permissions);
};

export default PermissionContext;
