import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

const UserModal = ({ isOpen, onClose, onSuccess, mode = 'create', user = null }) => {
  const [formData, setFormData] = useState({
    user_name: '',
    user_email: '',
    user_password: '',
    job_title: '',
    business_unit_id: '',
    role_ids: []
  });

  const [businessUnits, setBusinessUnits] = useState([]);
  const [roles, setRoles] = useState([]);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPermissionsEditor, setShowPermissionsEditor] = useState(false);
  const [manualPermissions, setManualPermissions] = useState({});
  const [expandedModules, setExpandedModules] = useState({});
  const [modules, setModules] = useState([]);

  const loadData = async () => {
    try {
      const token = localStorage.getItem('hrms_token');

      // Load business units
      const buRes = await fetch('http://localhost:8080/api/admin/users-access-control/business-units', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (buRes.ok) {
        const data = await buRes.json();
        setBusinessUnits(data.business_units || data || []);
      }

      // Load roles
      const rolesRes = await fetch('http://localhost:8080/admin/role-templates', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (rolesRes.ok) {
        const data = await rolesRes.json();
        setRoles(data.role_templates || []);
      }

      // Load positions for job title dropdown
      const posRes = await fetch('http://localhost:8080/org/positions', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (posRes.ok) {
        const posData = await posRes.json();
        setPositions(posData || []);
      }

      // Load modules for permissions editor
      const modulesRes = await fetch('http://localhost:8080/admin/modules', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (modulesRes.ok) {
        const modulesData = await modulesRes.json();
        setModules(modulesData.modules || []);
      }
    } catch (err) {
      console.error('Error loading data:', err);
    }
  };

  // Load initial data
  useEffect(() => {
    if (!isOpen) return;

    if (mode === 'edit' && user) {
      setFormData({
        user_name: user.user_name || '',
        user_email: user.user_email || '',
        user_password: '',
        job_title: user.job_title || '',
        business_unit_id: user.business_unit_id || '',
        role_ids: user.role_ids || []
      });
    } else {
      setFormData({
        user_name: '',
        user_email: '',
        user_password: '',
        job_title: '',
        business_unit_id: '',
        role_ids: []
      });
    }

    loadData();
  }, [isOpen, mode, user]);


  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleRoleToggle = (roleId) => {
    setFormData(prev => {
      // Single-select: if already selected, deselect; otherwise select only this one
      const isSelected = prev.role_ids.includes(roleId);
      return {
        ...prev,
        role_ids: isSelected ? [] : [roleId]
      };
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // Validation
      if (!formData.user_name?.trim()) {
        setError('User name is required');
        setLoading(false);
        return;
      }
      if (!formData.user_email?.trim()) {
        setError('Email is required');
        setLoading(false);
        return;
      }
      if (mode === 'create' && !formData.user_password?.trim()) {
        setError('Password is required');
        setLoading(false);
        return;
      }
      if (!formData.business_unit_id) {
        setError('Business unit is required');
        setLoading(false);
        return;
      }

      // Either role template OR manual permissions must be set
      const hasManualPermissions = Object.keys(manualPermissions).length > 0;
      if (formData.role_ids.length === 0 && !hasManualPermissions) {
        setError('Select a role template or configure custom permissions');
        setLoading(false);
        return;
      }

      const token = localStorage.getItem('hrms_token');
      const endpoint = mode === 'create'
        ? 'http://localhost:8080/hr/users/create-with-roles'
        : `http://localhost:8080/hr/users/${user.user_id}/update-with-roles`;
      const method = mode === 'create' ? 'POST' : 'PUT';

      const payload = {
        user_name: formData.user_name,
        user_email: formData.user_email,
        ...(mode === 'create' && { user_password: formData.user_password }),
        job_title: formData.job_title || null,
        business_unit_id: parseInt(formData.business_unit_id),
        role_ids: formData.role_ids
      };

      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || 'Failed to save user');
        setLoading(false);
        return;
      }

      setLoading(false);
      try {
        onSuccess?.();
      } catch (successErr) {
        console.error('Error in onSuccess callback:', successErr);
      }
      onClose();
    } catch (err) {
      setError(err.message || 'An error occurred');
      setLoading(false);
    }
  };

  const handlePermissionSave = (permissions) => {
    setManualPermissions(permissions);
    setShowPermissionsEditor(false);
  };

  const handleTogglePermission = (moduleName, action) => {
    setManualPermissions(prev => ({
      ...prev,
      [moduleName]: {
        ...prev[moduleName],
        [action]: !prev[moduleName]?.[action]
      }
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {mode === 'create' ? 'Create New User' : 'Edit User'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {mode === 'create' ? 'Add a new user with roles and permissions' : 'Update user details and roles'}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
            ✕
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800">
              {error}
            </div>
          )}

          {/* User Details Section */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">User Details</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Name *</label>
              <input
                type="text"
                name="user_name"
                value={formData.user_name}
                onChange={handleInputChange}
                placeholder="e.g., John Doe"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email *</label>
              <input
                type="email"
                name="user_email"
                value={formData.user_email}
                onChange={handleInputChange}
                placeholder="e.g., john@example.com"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            {mode === 'create' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Password *</label>
                <input
                  type="password"
                  name="user_password"
                  value={formData.user_password}
                  onChange={handleInputChange}
                  placeholder="Enter password"
                  className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Job Title</label>
              <select
                name="job_title"
                value={formData.job_title}
                onChange={handleInputChange}
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select a position...</option>
                {positions.map((pos) => (
                  <option key={pos.id} value={pos.name}>{pos.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Organization Section */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Organization</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Business Unit *</label>
              <select
                name="business_unit_id"
                value={formData.business_unit_id}
                onChange={handleInputChange}
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select Business Unit</option>
                {businessUnits.map(bu => (
                  <option key={bu.id} value={bu.id}>
                    {bu.name}
                  </option>
                ))}
              </select>
            </div>

          </div>

          {/* Role Template Section */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Role Template *</h3>
            <p className="text-sm text-gray-600">Select one or more role templates for this user</p>
            <div className="space-y-2 max-h-48 overflow-y-auto border rounded-lg p-3">
              {roles.map(role => {
                const isSelected = formData.role_ids.includes(role.id);
                const hasSelection = formData.role_ids.length > 0;
                const isDisabled = hasSelection && !isSelected;

                return (
                  <label
                    key={role.id}
                    className={`flex items-center gap-3 p-2 rounded cursor-pointer ${
                      isDisabled
                        ? 'opacity-50 cursor-not-allowed bg-gray-100'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleRoleToggle(role.id)}
                      disabled={isDisabled}
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 disabled:cursor-not-allowed"
                    />
                    <span className={`text-sm font-medium ${isDisabled ? 'text-gray-500' : 'text-gray-900'}`}>
                      {role.name}
                    </span>
                    {role.description && (
                      <span className={`text-xs ${isDisabled ? 'text-gray-400' : 'text-gray-600'}`}>
                        ({role.description})
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
            {formData.role_ids.length === 0 && !Object.values(manualPermissions).some(p => p) && (
              <p className="text-sm text-gray-600">Or set custom permissions below</p>
            )}
          </div>

          {/* Manual Permissions Section - Show only if no role template selected */}
          {formData.role_ids.length === 0 && (
            <div className="space-y-4 border-t pt-4">
              <div>
                <h3 className="font-medium text-gray-900 mb-2">Custom Permissions</h3>
                <p className="text-sm text-gray-600 mb-4">Granularly select permissions for this user</p>
                <button
                  type="button"
                  onClick={() => setShowPermissionsEditor(true)}
                  className="px-4 py-2 text-sm font-medium text-white bg-bx-orange rounded-xl hover:bg-bx-orange-hover"
                >
                  Configure Permissions
                </button>
                {Object.keys(manualPermissions).length > 0 && (
                  <p className="text-xs text-green-600 mt-2">✓ Custom permissions configured</p>
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 justify-end pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-bx-orange rounded-xl hover:bg-bx-orange-hover disabled:bg-gray-400"
            >
              {loading ? 'Saving...' : mode === 'create' ? 'Create User' : 'Update User'}
            </button>
          </div>
        </form>
      </div>

      {/* Permissions Editor Modal */}
      {showPermissionsEditor && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Configure Permissions</h2>
                <p className="text-sm text-gray-600 mt-1">Select granular permissions for this user</p>
              </div>
              <button onClick={() => setShowPermissionsEditor(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
                ✕
              </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              <div className="border rounded-lg divide-y max-h-[400px] overflow-y-auto">
                {modules.map(module => {
                  const enabled = Object.values(manualPermissions[module.name] || {}).some(p => p);
                  const count = Object.values(manualPermissions[module.name] || {}).filter(Boolean).length;

                  return (
                    <div key={module.id}>
                      <div className="bg-blue-50 px-4 py-3">
                        <div className="flex items-center justify-between">
                          <div
                            className="flex items-center gap-3 flex-1 cursor-pointer hover:opacity-70"
                            onClick={() => setExpandedModules(prev => ({ ...prev, [module.id]: !prev[module.id] }))}
                          >
                            <span className="text-gray-600 text-lg">{expandedModules[module.id] ? '▼' : '▶'}</span>
                            <div>
                              <h4 className="font-semibold text-gray-900 capitalize">{module.name}</h4>
                              <p className="text-xs text-gray-600">{count}/4 permissions</p>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              if (enabled) {
                                setManualPermissions(prev => ({
                                  ...prev,
                                  [module.name]: { view: false, create: false, edit: false, delete: false }
                                }));
                              } else {
                                setExpandedModules(prev => ({ ...prev, [module.id]: true }));
                              }
                            }}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              enabled ? 'bg-green-500' : 'bg-red-500'
                            }`}
                            title={enabled ? 'Disable module' : 'Enable module'}
                          >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                              enabled ? 'translate-x-6' : 'translate-x-1'
                            }`} />
                          </button>
                        </div>
                      </div>

                      {expandedModules[module.id] && (
                        <div className="bg-white px-4 py-3 space-y-2">
                          {['view', 'create', 'edit', 'delete'].map(action => (
                            <label key={action} className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded">
                              <input
                                type="checkbox"
                                checked={manualPermissions[module.name]?.[action] || false}
                                onChange={() => handleTogglePermission(module.name, action)}
                                className="w-4 h-4 rounded border-gray-300 text-blue-600"
                              />
                              <span className="text-sm font-medium text-gray-900 capitalize">{action}</span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 justify-end px-6 py-4 border-t">
              <button
                type="button"
                onClick={() => setShowPermissionsEditor(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  handlePermissionSave(manualPermissions);
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-bx-orange rounded-xl hover:bg-bx-orange-hover"
              >
                Save Permissions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserModal;
