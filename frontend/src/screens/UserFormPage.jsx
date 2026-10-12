import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, X } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';
import { listBusinessUnits } from '../services/api/rbac';
import { toast } from 'react-toastify';
import { hasPermission } from '../utils/permissionsRoleTemplate';

export default function UserFormPage() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const mode = userId ? 'edit' : 'create';

  // Check permissions for create/edit
  useEffect(() => {
    if (mode === 'create' && !hasPermission('users', 'edit')) {
      toast.error('You do not have permission to create users');
      navigate('/admin/users-access-control/users');
    }
    if (mode === 'edit' && !hasPermission('users', 'edit')) {
      toast.error('You do not have permission to edit users');
      navigate('/admin/users-access-control/users');
    }
  }, [mode, navigate]);

  const [formData, setFormData] = useState({
    user_name: '',
    user_email: '',
    user_password: '',
    job_title: '',
    business_unit_id: '',
    role_template_id: '',
    whatsapp_number: '',
    hierarchy_level: '',
    specialization: '',
    parent_node_id: '',
    department_id: '',
    location_id: ''
  });

  const [roleTemplates, setRoleTemplates] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [positions, setPositions] = useState([]);
  // Org levels (1-17, each with the position/job title it holds) and specializations
  const [reference, setReference] = useState({ levels: [], specializations: [] });
  const [validSupervisors, setValidSupervisors] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [deliveryCenters, setDeliveryCenters] = useState([]);
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [selectedTemplatePermissions, setSelectedTemplatePermissions] = useState([]);
  const [actionError, setActionError] = useState(null);
  // Edit mode: whether the user already has a seat in the org chart
  const [hasSeat, setHasSeat] = useState(true);

  useEffect(() => {
    loadInitialData();
  }, []);


  const loadInitialData = async () => {
    try {
      const [rolesRes, busRes, posRes, dcRes, refRes] = await Promise.all([
        apiRequest('/admin/role-templates'),
        listBusinessUnits(),
        apiRequest('/org/positions'),
        apiRequest('/api/v1/api/admin/users-access-control/delivery-centers'),
        apiRequest('/org/hierarchy-reference')
      ]);
      setReference(refRes.data || { levels: [], specializations: [] });
      // Filter to only enabled templates - disabled templates shouldn't be selectable
      const enabledTemplates = rolesRes.data?.role_templates?.filter(t => t.enabled !== false) || [];
      setRoleTemplates(enabledTemplates);
      setBusinessUnits(busRes);

      // positions from /org/positions is an array of OrgPosition objects
      const positionArray = Array.isArray(posRes.data) ? posRes.data : posRes.data?.positions || [];
      setPositions(positionArray);
      setDeliveryCenters(dcRes.data?.delivery_centers || []);
    } catch (err) {
      console.error('Failed to load form data:', err);
      const message = err?.message || 'Failed to load form data. Please check your permissions.';
      setActionError(message);
      throw err;
    }
  };

  const loadUserData = useCallback(async () => {
    try {
      setLoading(true);
      const { data: user } = await apiRequest(`/hr/users/${userId}`);
      if (!user) {
        setActionError('User not found');
        navigate('/admin/users-access-control/users');
        return;
      }
      setFormData(prev => ({
        ...prev,
        user_name: user.user_name || '',
        user_email: user.user_email || '',
        user_password: '',
        job_title: user.job_title || '',
        business_unit_id: user.business_unit_id || '',
        department_id: user.department_id || '',
        role_template_id: user.role_template_id || '',
        location_id: user.location_id || '',
        // The org-chart seat (empty when the user is not in the org chart yet)
        hierarchy_level: user.hierarchy_level || '',
        specialization: user.specialization || '',
        parent_node_id: user.parent_node_id || '',
      }));
      setHasSeat(Boolean(user.org_node_id));
    } catch (err) {
      console.error('[UserFormPage] Failed to load user:', err);
      setActionError(`Failed to load user details: ${err.message}`);
      navigate('/admin/users-access-control/users');
    } finally {
      setLoading(false);
    }
  }, [userId, navigate]);

  useEffect(() => {
    if (mode === 'edit' && userId) {
      loadUserData();
    }
  }, [userId, mode, loadUserData]);

  const handleUserNameChange = (value) => {
    setFormData(prev => ({ ...prev, user_name: value }));
  };

  const handleEmailChange = (value) => {
    setFormData(prev => ({ ...prev, user_email: value }));
  };

  const handlePasswordChange = (value) => {
    setFormData(prev => ({ ...prev, user_password: value }));
  };

  const handleWhatsappChange = (value) => {
    setFormData(prev => ({ ...prev, whatsapp_number: value }));
  };

  const handleBusinessUnitChange = (e) => {
    // Departments and eligible supervisors are both scoped to the business unit
    setFormData(prev => ({ ...prev, business_unit_id: e.target.value, department_id: '', parent_node_id: '' }));
  };

  // Org-wide departments (HR, Recruitment, Finance ...) plus any team that
  // belongs to the chosen business unit
  useEffect(() => {
    apiRequest('/org/departments')
      .then(res => {
        const all = Array.isArray(res.data) ? res.data : [];
        setDepartments(all.filter(d => !d.business_unit_id || String(d.business_unit_id) === String(formData.business_unit_id)));
      })
      .catch(err => {
        console.error('[UserFormPage] Failed to load departments:', err);
        setActionError(`Could not load departments: ${err.message}`);
      });
  }, [formData.business_unit_id]);

  const handleRoleTemplateChange = async (e) => {
    const templateId = e.target.value;
    setFormData(prev => ({ ...prev, role_template_id: templateId }));

    // Fetch permissions for the selected template
    if (templateId) {
      try {
        const response = await apiRequest(`/admin/role-templates/${templateId}`);
        const permissions = response.data?.permissions || [];
        setSelectedTemplatePermissions(permissions);
        // The role template suggests a specialization (and a level when the
        // job title doesn't imply one); both stay editable on the form.
        setFormData(prev => ({
          ...prev,
          hierarchy_level: prev.hierarchy_level || (response.data?.hierarchy_level ?? ''),
          specialization: response.data?.specialization ?? prev.specialization,
          parent_node_id: '' // reset - valid supervisors depend on hierarchy_level/specialization
        }));
      } catch (error) {
        console.error('Failed to fetch template permissions:', error);
        setSelectedTemplatePermissions([]);
      }
    } else {
      setSelectedTemplatePermissions([]);
      setFormData(prev => ({ ...prev, parent_node_id: '' }));
    }
  };

  // Fetch valid supervisors whenever hierarchy_level/specialization/business_unit_id
  // (all needed by OrgHierarchyValidator) are known.
  const { hierarchy_level, specialization, business_unit_id } = formData;
  useEffect(() => {
    if (!hierarchy_level || !specialization) {
      setValidSupervisors([]);
      return;
    }
    // The top of the organization reports to nobody: the backend answers [] for it
    const params = new URLSearchParams({
      hierarchy_level: String(hierarchy_level),
      specialization,
    });
    if (business_unit_id) params.set('business_unit_id', String(business_unit_id));

    apiRequest(`/org/valid-supervisors?${params.toString()}`)
      .then(res => setValidSupervisors(Array.isArray(res.data) ? res.data : []))
      .catch(err => {
        console.error('[UserFormPage] Failed to fetch valid supervisors:', err);
        setValidSupervisors([]);
        setActionError(`Could not load eligible supervisors: ${err.message}`);
      });
  }, [hierarchy_level, specialization, business_unit_id]);

  // The org-chart seat. Level 17 is the CEO: top of the organization,
  // reports to no one. The job title suggests the level; the admin can change it.
  const isCeo = Number(formData.hierarchy_level) === 17;
  const seatLevel = formData.hierarchy_level;
  const seatSpecialization = formData.specialization || (isCeo ? 'General' : '');

  // Highest level whose position matches the picked job title (CEO -> 17, Partner -> 16, ...)
  const levelForJobTitle = (title) => {
    const position = positions.find((p) => (p.name || p.PositionName || p.position_name) === title);
    const code = position?.rbac_role_name;
    return reference.levels.find((l) => code && l.position_code === code)?.level || '';
  };

  const handleSave = async (e) => {
    e.preventDefault();

    if (!formData.user_name.trim()) {
      setActionError('User name is required');
      return;
    }
    if (!formData.user_email.trim()) {
      setActionError('Email is required');
      return;
    }
    if (mode === 'create' && !formData.user_password.trim()) {
      setActionError('Password is required');
      return;
    }
    if (!formData.business_unit_id) {
      setActionError('Business Unit is required');
      return;
    }
    if (!formData.role_template_id) {
      setActionError('Role Template is required');
      return;
    }
    if (mode === 'create' && (!seatLevel || !seatSpecialization)) {
      setActionError('Selected role template is missing a hierarchy level/specialization - pick a different role template');
      return;
    }
    if (seatLevel && Number(seatLevel) < 17 && !formData.parent_node_id) {
      setActionError('Reports To is required for this hierarchy level');
      return;
    }

    setSaving(true);
    try {
      if (mode === 'create') {
        const payload = {
          user_name: formData.user_name.trim(),
          user_email: formData.user_email.trim(),
          job_title: formData.job_title.trim(),
          business_unit_id: parseInt(formData.business_unit_id, 10),
          role_template_id: parseInt(formData.role_template_id, 10),
          hierarchy_level: parseInt(seatLevel, 10),
          specialization: seatSpecialization,
          parent_node_id: isCeo ? null : (formData.parent_node_id || null),
          department_id: formData.department_id || null,
          location_id: formData.location_id || null,
          user_password: formData.user_password
        };
        const { data: queued } = await apiRequest('/hr/users/create-with-roles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        setActionError(null);
        // Creation runs in the background: the Users list follows the job until the account exists
        navigate('/admin/users-access-control/users', {
          state: { pendingUser: { email: payload.user_email, name: payload.user_name, jobId: queued?.message_id } },
        });
        return;
      } else {
        const payload = {
          user_name: formData.user_name.trim(),
          user_email: formData.user_email.trim(),
          job_title: formData.job_title.trim(),
          business_unit_id: parseInt(formData.business_unit_id, 10),
          role_template_id: parseInt(formData.role_template_id, 10),
          department_id: formData.department_id || '',
        };
        // Org-chart seat: places the user in the organization (or moves their seat)
        if (seatLevel) {
          Object.assign(payload, {
            hierarchy_level: parseInt(seatLevel, 10),
            specialization: seatSpecialization,
            parent_node_id: isCeo ? null : (formData.parent_node_id || null),
            location_id: formData.location_id || null,
          });
        }
        await apiRequest(`/hr/users/${userId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        setActionError(null);
      }

      navigate('/admin/users-access-control/users');
    } catch (err) {
      console.error('Failed to save user:', err);
      setActionError(err?.message || 'Failed to save user');
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
        {actionError && (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 flex items-center justify-between">
            <span>{actionError}</span>
            <button onClick={() => setActionError(null)} className="text-rose-700 hover:text-rose-900">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
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
              onChange={(e) => {
                const title = e.target.value;
                const level = levelForJobTitle(title);
                setFormData(prev => ({
                  ...prev,
                  job_title: title,
                  hierarchy_level: level || prev.hierarchy_level,
                  specialization: level === 17 ? 'General' : prev.specialization,
                  parent_node_id: '',
                }));
              }}
              disabled={saving}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
            >
              <option value="">Select Job Title</option>
              {positions && positions.length > 0 ? positions.map(position => {
                const posId = position.id || position.PositionID;
                const posName = position.name || position.PositionName || position.position_name;
                return (
                  <option key={posId} value={posName}>{posName}</option>
                );
              }) : (
                <option disabled>Loading job titles...</option>
              )}
            </select>
          </div>

          {/* WhatsApp Number */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              WhatsApp Number (for Thunder outreach)
            </label>
            <Input
              type="tel"
              value={formData.whatsapp_number}
              onChange={handleWhatsappChange}
              placeholder="+1 (555) 123-4567 or +91 9876543210"
              disabled={saving}
              pattern="\+?[0-9\s\-()]*"
            />
            <p className="text-xs text-gray-500 mt-1">
              Optional. Used for Thunder candidate outreach. If empty, Thunder will fall back to email.
            </p>
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

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                <select
                  value={formData.department_id || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, department_id: e.target.value }))}
                  disabled={saving}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
                >
                  <option value="">No department</option>
                  {departments.map(dept => (
                    <option key={dept.id} value={dept.id}>{dept.business_unit_name ? `${dept.name} · ${dept.business_unit_name}` : dept.name}</option>
                  ))}
                </select>
                {departments.length === 0 && (
                  <p className="text-xs text-gray-500 mt-1">No departments yet - add them under Organizational Hierarchy → Manage Departments.</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company</label>
                <select
                  value={formData.location_id || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, location_id: e.target.value }))}
                  disabled={saving}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
                >
                  <option value="">Select company (BX-US / BX-IN)</option>
                  {deliveryCenters.map(dc => (
                    <option key={dc.id} value={dc.id}>{dc.name}</option>
                  ))}
                </select>
              </div>
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

          {mode === 'edit' && !hasSeat && (
            <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
              Not in the org chart yet. Choose a level, specialization and who they report to, then save to connect them to the organization.
            </p>
          )}

          {/* Org-chart seat: level suggested by the job title, specialization by the role template */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Hierarchy Level
                </label>
                <select
                  value={formData.hierarchy_level || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, hierarchy_level: e.target.value ? Number(e.target.value) : '', parent_node_id: '' }))}
                  disabled={saving}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
                >
                  <option value="">Select level</option>
                  {reference.levels.map((l) => (
                    <option key={l.level} value={l.level}>L{l.level} · {l.name}</option>
                  ))}
                </select>
                {isCeo && <p className="mt-1 text-xs text-gray-500">Top of the organization - reports to no one.</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Specialization
                </label>
                <select
                  value={formData.specialization || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, specialization: e.target.value, parent_node_id: '' }))}
                  disabled={saving}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
                >
                  <option value="">Select specialization</option>
                  {reference.specializations.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>

          {/* Reports To - required for anyone below CEO level */}
          {seatLevel && Number(seatLevel) < 17 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reports To *
              </label>
              <select
                value={formData.parent_node_id || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, parent_node_id: e.target.value }))}
                disabled={saving}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange disabled:bg-gray-100"
                required
              >
                <option value="">Select Supervisor</option>
                {validSupervisors.map(node => (
                  <option key={node.id} value={node.id}>{node.name} (Level {node.hierarchy_level}, {node.specialization})</option>
                ))}
              </select>
              {formData.specialization && validSupervisors.length === 0 && (
                <p className="text-xs text-amber-600 mt-1">
                  No eligible supervisors yet. This role must report to a Level {Number(formData.hierarchy_level) + 1}-{Math.min(Number(formData.hierarchy_level) + 2, 17)} node in this business unit (same specialization unless the supervisor is Level 13+) - add one under Organizational Hierarchy.
                </p>
              )}
            </div>
          )}

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

      {mode === 'create' && (
        <Card className="p-4 bg-blue-50 border-blue-200">
          <p className="text-sm text-blue-800">
            Creating a user also places them in the org chart under the selected supervisor, in the chosen department. Their hierarchy level and specialization come from the role template.
          </p>
        </Card>
      )}
    </div>
  );
}
