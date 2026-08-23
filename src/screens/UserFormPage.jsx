import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';

const toast = {
  success: (msg) => console.log('✓', msg),
  error: (msg) => console.error('✗', msg)
};

/**
 * UserFormPage - Create/Edit login accounts only
 *
 * IMPORTANT: User = login/RBAC account only
 * Employee details (job title, reporting manager, delivery center) are
 * managed separately in Employee onboarding, NOT here.
 *
 * Link: User (wros_user_id) → Employee (employee details + org hierarchy)
 */
export default function UserFormPage() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const mode = userId ? 'edit' : 'create';

  const [form, setForm] = useState({
    user_name: "",
    user_email: "",
    user_password: "",
    business_unit_id: "",
    role_ids: []
  });

  const [roles, setRoles] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [loading, setLoading] = useState(mode === 'edit');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

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
      // Load role templates
      const rolesRes = await apiRequest('/rbac/role-templates');
      setRoles(rolesRes.data?.role_templates || []);

      // Load business units
      const buRes = await apiRequest('/bu-context/available-buses', { skipAuth: true });
      setBusinessUnits(buRes.data?.business_units || []);
    } catch (err) {
      console.error("Failed to load initial data:", err);
      toast.error("Failed to load form data");
    }
  };

  const loadUserData = async () => {
    try {
      setLoading(true);
      // Fetch user's assigned roles
      const rolesRes = await apiRequest(`/rbac/users/${userId}/roles`);
      const roleIds = (rolesRes.data?.roles || []).map(r => r.id);

      // Fetch the user details
      const usersRes = await apiRequest('/hr/users/all');
      const user = usersRes.data?.users?.find(u => u.user_id === userId);

      if (user) {
        setForm({
          user_name: user.user_name || "",
          user_email: user.user_email || "",
          user_password: "",
          business_unit_id: user.business_unit_id || "",
          role_ids: roleIds
        });
      }
    } catch (err) {
      console.error("Failed to load user data:", err);
      toast.error("Failed to load user details");
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    const newErrors = {};
    if (!form.user_name?.trim()) newErrors.user_name = "User name is required";
    if (!form.user_email?.trim()) newErrors.user_email = "Email is required";
    if (mode === 'create' && !form.user_password?.trim()) newErrors.user_password = "Password is required";
    if (!form.business_unit_id) newErrors.business_unit_id = "Business Unit is required";
    if (form.role_ids.length === 0) newErrors.role_ids = "At least one role must be selected";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    setBusy(true);
    try {
      const payload = {
        user_name: form.user_name,
        user_email: form.user_email,
        business_unit_id: form.business_unit_id ? parseInt(form.business_unit_id, 10) : null,
        role_ids: form.role_ids.map(id => parseInt(id, 10))
      };

      if (mode === 'create') {
        payload.user_password = form.user_password;
        await apiRequest('/hr/users', {
          method: 'POST',
          body: payload
        });
        toast.success("User created successfully");
      } else {
        await apiRequest(`/hr/users/${userId}`, {
          method: 'PUT',
          body: payload
        });
        toast.success("User updated successfully");
      }

      navigate('/admin/users-access-control/users');
    } catch (err) {
      console.error("Failed to save user:", err);
      toast.error(err.data?.detail || "Failed to save user");
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = () => {
    navigate('/admin/users-access-control/users');
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div>Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={handleCancel} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-2xl font-bold">
          {mode === 'create' ? 'Create User' : 'Edit User'}
        </h1>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* User Name */}
          <div>
            <label className="block text-sm font-medium mb-2">User Name *</label>
            <Input
              value={form.user_name}
              onChange={(e) => setForm({ ...form, user_name: e.target.value })}
              placeholder="Enter user name"
              error={errors.user_name}
            />
            {errors.user_name && <p className="text-red-500 text-sm mt-1">{errors.user_name}</p>}
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium mb-2">Email *</label>
            <Input
              type="email"
              value={form.user_email}
              onChange={(e) => setForm({ ...form, user_email: e.target.value })}
              placeholder="Enter email"
              error={errors.user_email}
            />
            {errors.user_email && <p className="text-red-500 text-sm mt-1">{errors.user_email}</p>}
          </div>

          {/* Password (create mode only) */}
          {mode === 'create' && (
            <div>
              <label className="block text-sm font-medium mb-2">Password *</label>
              <Input
                type="password"
                value={form.user_password}
                onChange={(e) => setForm({ ...form, user_password: e.target.value })}
                placeholder="Enter password"
                error={errors.user_password}
              />
              {errors.user_password && <p className="text-red-500 text-sm mt-1">{errors.user_password}</p>}
            </div>
          )}

          {/* Business Unit */}
          <div>
            <label className="block text-sm font-medium mb-2">Business Unit *</label>
            <select
              value={form.business_unit_id}
              onChange={(e) => setForm({ ...form, business_unit_id: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="">Select Business Unit</option>
              {businessUnits.map(bu => (
                <option key={bu.id} value={bu.id}>{bu.display_name}</option>
              ))}
            </select>
            {errors.business_unit_id && <p className="text-red-500 text-sm mt-1">{errors.business_unit_id}</p>}
          </div>

          {/* Roles */}
          <div>
            <label className="block text-sm font-medium mb-2">Roles *</label>
            <div className="space-y-2">
              {roles.map(role => (
                <label key={role.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.role_ids.includes(role.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setForm({ ...form, role_ids: [...form.role_ids, role.id] });
                      } else {
                        setForm({ ...form, role_ids: form.role_ids.filter(id => id !== role.id) });
                      }
                    }}
                  />
                  {role.name}
                </label>
              ))}
            </div>
            {errors.role_ids && <p className="text-red-500 text-sm mt-1">{errors.role_ids}</p>}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-6 border-t">
            <Button
              type="submit"
              disabled={busy}
              className="flex-1 bg-blue-600 text-white"
            >
              {busy ? 'Saving...' : (mode === 'create' ? 'Create User' : 'Update User')}
            </Button>
            <Button
              type="button"
              onClick={handleCancel}
              className="flex-1 bg-gray-200"
            >
              Cancel
            </Button>
          </div>
        </form>
      </Card>

      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm">
        <p className="font-semibold mb-2">Note: Employee Details Are Managed Separately</p>
        <p className="text-gray-700">
          This form creates login accounts (RBAC) only. Employee organizational details
          (job title, reporting manager, delivery center) are managed in the Employee onboarding flow.
        </p>
      </div>
    </div>
  );
}
