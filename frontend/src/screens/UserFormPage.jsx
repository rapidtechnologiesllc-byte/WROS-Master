import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';
import { toast } from 'react-toastify';

export default function UserFormPage() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const mode = userId ? 'edit' : 'create';

  const [formData, setFormData] = useState({
    user_name: '',
    user_email: '',
    user_password: '',
    job_title: '',
    business_unit_id: '',
    role_template_id: ''
  });

  const [roleTemplates, setRoleTemplates] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [selectedTemplatePermissions, setSelectedTemplatePermissions] = useState([]);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (mode === 'edit' && userId) {
      loadUserData();
    }
  }, [userId, mode]);

  const loadInitialData = async () => {
    try {
      const [rolesRes, busRes, posRes] = await Promise.all([
        apiRequest('/admin/role-templates'),
        apiRequest('/admin/certifications/business-units'),
        apiRequest('/org/positions')
      ]);
      // Filter to only enabled templates - disabled templates shouldn't be selectable
      const enabledTemplates = rolesRes.data?.role_templates?.filter(t => t.enabled !== false) || [];
      setRoleTemplates(enabledTemplates);
      setBusinessUnits(busRes.data || []);
      setPositions(posRes.data || []);
    } catch (err) {
      console.error('Failed to load form data:', err);
      const message = err?.message || 'Failed to load form data. Please check your permissions.';
      toast.error(message);
      throw err;
    }
  };

  const loadUserData = async () => {
    try {
      setLoading(true);
      console.log('[DEBUG] loadUserData: Starting, userId from URL:', userId);

      const usersRes = await apiRequest('/hr/users/all');
      console.log('[DEBUG] loadUserData: Users response:', usersRes);
      console.log('[DEBUG] loadUserData: Users array:', usersRes.data?.users);

      const user = usersRes.data?.users?.find(u => {
        console.log('[DEBUG] loadUserData: Comparing u.user_id:', u.user_id, 'type:', typeof u.user_id, 'with userId:', userId, 'type:', typeof userId, 'match:', u.user_id === userId);
        return u.user_id === userId;
      });

      console.log('[DEBUG] loadUserData: Found user:', user);

      if (user) {
        console.log('[DEBUG] loadUserData: User found, loaded from users list');
        console.log('[DEBUG] loadUserData: job_title =', user.job_title, 'role_template_id =', user.role_template_id, 'permission_role =', user.permission_role);

        // If role_template_id is not returned, try to find it by matching permission_role
        let roleTemplateId = user.role_template_id || '';
        if (!roleTemplateId && user.permission_role) {
          const matchingTemplate = roleTemplates.find(t =>
            (t.name || t.TemplateName || t.template_name) === user.permission_role
          );
          if (matchingTemplate) {
            roleTemplateId = matchingTemplate.id || matchingTemplate.TemplateID;
            console.log('[DEBUG] loadUserData: Mapped permission_role to role_template_id:', roleTemplateId);
          }
        }

        setFormData({
          user_name: user.user_name || '',
          user_email: user.user_email || '',
          user_password: '',
          job_title: user.job_title || '',
          business_unit_id: user.business_unit_id || '',
          role_template_id: roleTemplateId
        });

        console.log('[DEBUG] loadUserData: formData set to:', { job_title: user.job_title, role_template_id: roleTemplateId });
      } else {
        console.log('[DEBUG] loadUserData: User not found - showing error and navigating');
        toast.error('User not found');
        navigate('/admin/users-access-control/users');
      }
    } catch (err) {
      console.error('[DEBUG] loadUserData: ERROR:', err);
      console.error('[DEBUG] loadUserData: Error details:', err.message, err.response?.status, err.response?.data);
      toast.error('Failed to load user details');
      navigate('/admin/users-access-control/users');
    } finally {
      setLoading(false);
    }
  };

  const handleUserNameChange = (value) => {
    setFormData(prev => ({ ...prev, user_name: value }));
  };

  const handleEmailChange = (value) => {
    setFormData(prev => ({ ...prev, user_email: value }));
  };

  const handlePasswordChange = (value) => {
    setFormData(prev => ({ ...prev, user_password: value }));
  };

  const handleJobTitleChange = (value) => {
    setFormData(prev => ({ ...prev, job_title: value }));
  };

  const handleBusinessUnitChange = (e) => {
    setFormData(prev => ({ ...prev, business_unit_id: e.target.value }));
  };

  const handleRoleTemplateChange = async (e) => {
    const templateId = e.target.value;
    setFormData(prev => ({ ...prev, role_template_id: templateId }));

    // Fetch permissions for the selected template
    if (templateId) {
      try {
        const response = await apiRequest(`/admin/role-templates/${templateId}`);
        const permissions = response.data?.permissions || [];
        setSelectedTemplatePermissions(permissions);
      } catch (error) {
        console.error('Failed to fetch template permissions:', error);
        setSelectedTemplatePermissions([]);
      }
    } else {
      setSelectedTemplatePermissions([]);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();

    if (!formData.user_name.trim()) {
      toast.error('User name is required');
      return;
    }
    if (!formData.user_email.trim()) {
      toast.error('Email is required');
      return;
    }
    if (mode === 'create' && !formData.user_password.trim()) {
      toast.error('Password is required');
      return;
    }
    if (!formData.business_unit_id) {
      toast.error('Business Unit is required');
      return;
    }
    if (!formData.role_template_id) {
      toast.error('Role Template is required');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        user_name: formData.user_name.trim(),
        user_email: formData.user_email.trim(),
        job_title: formData.job_title.trim(),
        business_unit_id: parseInt(formData.business_unit_id, 10),
        role_template_id: parseInt(formData.role_template_id, 10)
      };

      if (mode === 'create') {
        payload.user_password = formData.user_password;
        await apiRequest('/hr/users/create-with-roles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        toast.success('User created successfully');
      } else {
        await apiRequest(`/hr/users/${userId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        toast.success('User updated successfully');
      }

      navigate('/admin/users-access-control/users');
    } catch (err) {
      console.error('Failed to save user:', err);
      toast.error(err?.message || 'Failed to save user');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    navigate('/admin/users-access-control/users');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleCancel}
          className="p-2 hover:bg-gray-100 rounded-lg transition"
          title="Go back"
        >
          <ArrowLeft className="h-5 w-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {mode === 'create' ? 'Create User' : 'Edit User'}
          </h1>
          <p className="text-gray-600 text-sm mt-0.5">
            {mode === 'create' ? 'Add a new login account with RBAC roles' : 'Update user account and role assignments'}
          </p>
        </div>
      </div>

      {/* Form Card */}
      <Card className="p-6 max-w-2xl">
        <form onSubmit={handleSave} className="space-y-4">
          {/* User Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              User Name *
            </label>
            <Input
              type="text"
              value={formData.user_name}
              onChange={handleUserNameChange}
              placeholder="Enter full name"
              disabled={saving}
              required
            />
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email *
            </label>
            <Input
              type="email"
              value={formData.user_email}
              onChange={handleEmailChange}
              placeholder="user@company.com"
              disabled={saving}
              required
            />
          </div>

          {/* Password (create mode only) */}
          {mode === 'create' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password *
              </label>
              <Input
                type="password"
                value={formData.user_password}
                onChange={handlePasswordChange}
                placeholder="Enter secure password"
                disabled={saving}
                required
              />
            </div>
          )}

          {/* Job Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Job Title
            </label>
            <select
              value={formData.job_title}
              onChange={(e) => setFormData(prev => ({ ...prev, job_title: e.target.value }))}
              disabled={saving}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
            >
              <option value="">Select Job Title</option>
              {positions.map(position => {
                const posId = position.id || position.PositionID;
                const posName = position.name || position.PositionName || position.position_name;
                return (
                  <option key={posId} value={posName}>{posName}</option>
                );
              })}
            </select>
          </div>

          {/* Business Unit */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Business Unit *
            </label>
            <select
              value={String(formData.business_unit_id || '')}
              onChange={handleBusinessUnitChange}
              disabled={saving}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
              required
            >
              <option value="">Select Business Unit</option>
              {businessUnits.map(bu => {
                const buId = String(bu.id || bu.BusinessUnitID);
                const buName = bu.display_name || bu.BusinessUnitName || bu.business_unit_name || bu.name;
                return (
                  <option key={buId} value={buId}>{buName}</option>
                );
              })}
            </select>
          </div>

          {/* Role Template */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Role Template *
            </label>
            <select
              value={String(formData.role_template_id || '')}
              onChange={handleRoleTemplateChange}
              disabled={saving || mode === 'edit'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
              required
            >
              <option value="">Select Role Template</option>
              {roleTemplates.map(template => {
                const templateId = String(template.id || template.TemplateID);
                const templateName = template.name || template.TemplateName || template.template_name;
                return (
                  <option key={templateId} value={templateId}>{templateName}</option>
                );
              })}
            </select>
          </div>

          {/* Template Permissions Display */}
          {selectedTemplatePermissions.length > 0 && (
            <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="font-semibold text-sm text-gray-800 mb-3">Access & Permissions</h3>
              <div className="space-y-2">
                {selectedTemplatePermissions.map((perm, idx) => {
                  const actions = [];
                  if (perm.can_view) actions.push('View');
                  if (perm.can_create) actions.push('Create');
                  if (perm.can_edit) actions.push('Edit');
                  if (perm.can_delete) actions.push('Delete');

                  return (
                    <div key={idx} className="flex items-start justify-between text-sm">
                      <span className="font-medium text-gray-700">{perm.resource_display || perm.resource_name}</span>
                      <span className="text-gray-600">{actions.join(', ')}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 justify-end pt-4 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={saving}
              className="bg-bx-orange hover:bg-bx-orange-hover text-white"
            >
              {saving ? (mode === 'create' ? 'Creating...' : 'Updating...') : (mode === 'create' ? 'Create User' : 'Update User')}
            </Button>
          </div>
        </form>
      </Card>

      {/* Note */}
      <Card className="p-4 bg-blue-50 border-blue-200">
        <p className="font-semibold text-blue-900 mb-1">Note: Employee Details Are Managed Separately</p>
        <p className="text-sm text-blue-800">
          This form creates login accounts (RBAC) only. Employee organizational details (job title, reporting manager, delivery center) are managed in the Employee onboarding flow.
        </p>
      </Card>
    </div>
  );
}
