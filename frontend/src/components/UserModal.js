import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

const UserModal = ({ isOpen, onClose, onSuccess, mode = 'create', user = null }) => {
  const [formData, setFormData] = useState({
    user_name: '',
    user_email: '',
    user_password: '',
    job_title: '',
    business_unit_id: '',
    partner_id: '',
    role_ids: []
  });

  const [businessUnits, setBusinessUnits] = useState([]);
  const [partners, setPartners] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
        partner_id: user.partner_id || '',
        role_ids: user.role_ids || []
      });
    } else {
      setFormData({
        user_name: '',
        user_email: '',
        user_password: '',
        job_title: '',
        business_unit_id: '',
        partner_id: '',
        role_ids: []
      });
    }

    loadData();
  }, [isOpen, mode, user]);

  const loadData = async () => {
    try {
      const token = localStorage.getItem('access_token');

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
    } catch (err) {
      console.error('Error loading data:', err);
    }
  };

  // Load partners when business unit changes
  useEffect(() => {
    if (formData.business_unit_id) {
      loadPartners(formData.business_unit_id);
    }
  }, [formData.business_unit_id]);

  const loadPartners = async (buId) => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`http://localhost:8080/hr/users/all`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        // Filter users by business unit
        const buPartners = data.users?.filter(u => u.business_unit_id == buId) || [];
        setPartners(buPartners);
      }
    } catch (err) {
      console.error('Error loading partners:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleRoleToggle = (roleId) => {
    setFormData(prev => ({
      ...prev,
      role_ids: prev.role_ids.includes(roleId)
        ? prev.role_ids.filter(id => id !== roleId)
        : [...prev.role_ids, roleId]
    }));
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
      if (formData.role_ids.length === 0) {
        setError('At least one role is required');
        setLoading(false);
        return;
      }

      const token = localStorage.getItem('access_token');
      const endpoint = mode === 'create'
        ? 'http://localhost:8080/hr/users/create-with-roles'
        : `http://localhost:8080/hr/users/${user.user_id}`;
      const method = mode === 'create' ? 'POST' : 'PUT';

      const payload = {
        user_name: formData.user_name,
        user_email: formData.user_email,
        ...(mode === 'create' && { user_password: formData.user_password }),
        job_title: formData.job_title || null,
        business_unit_id: parseInt(formData.business_unit_id),
        partner_id: formData.partner_id ? parseInt(formData.partner_id) : null,
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
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || 'An error occurred');
      setLoading(false);
    }
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
              <input
                type="text"
                name="job_title"
                value={formData.job_title}
                onChange={handleInputChange}
                placeholder="e.g., Senior Recruiter"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
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

            {formData.business_unit_id && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Partner (Employee)</label>
                <select
                  name="partner_id"
                  value={formData.partner_id}
                  onChange={handleInputChange}
                  className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select Partner</option>
                  {partners.map(partner => (
                    <option key={partner.user_id} value={partner.user_id}>
                      {partner.user_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Roles Section */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Roles *</h3>
            <p className="text-sm text-gray-600">Select one or more roles for this user</p>
            <div className="space-y-2 max-h-48 overflow-y-auto border rounded-lg p-3">
              {roles.map(role => (
                <label key={role.id} className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded">
                  <input
                    type="checkbox"
                    checked={formData.role_ids.includes(role.id)}
                    onChange={() => handleRoleToggle(role.id)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600"
                  />
                  <span className="text-sm font-medium text-gray-900">{role.name}</span>
                  {role.description && (
                    <span className="text-xs text-gray-600">({role.description})</span>
                  )}
                </label>
              ))}
            </div>
            {formData.role_ids.length === 0 && (
              <p className="text-sm text-red-600">At least one role is required</p>
            )}
          </div>

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
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 disabled:bg-gray-400"
            >
              {loading ? 'Saving...' : mode === 'create' ? 'Create User' : 'Update User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserModal;
