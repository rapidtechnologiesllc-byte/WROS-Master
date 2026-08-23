import React, { useState, useEffect } from 'react';
import { roleTemplatesAPI } from '../../services/api/roleTemplates';
import PermissionMatrix from './PermissionMatrix';
import './RoleTemplateForm.css';

const RoleTemplateForm = ({ template, businessUnits, onSave, onCancel, loading }) => {
  const [formData, setFormData] = useState({
    name: '',
    display_name: '',
    description: '',
    permissions: [],
  });

  const [allResources, setAllResources] = useState([]);
  const [selectedPermissions, setSelectedPermissions] = useState({});
  const [loadingResources, setLoadingResources] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (template) {
      setFormData({
        name: template.name || '',
        display_name: template.display_name || '',
        description: template.description || '',
        permissions: template.permissions || [],
      });

      // Build selected permissions map
      const permMap = {};
      template.permissions?.forEach((perm) => {
        const key = `${perm.resource_id}`;
        if (!permMap[key]) {
          permMap[key] = { view: false, create: false, edit: false, delete: false };
        }
        if (perm.can_view) permMap[key].view = true;
        if (perm.can_create) permMap[key].create = true;
        if (perm.can_edit) permMap[key].edit = true;
        if (perm.can_delete) permMap[key].delete = true;
      });
      setSelectedPermissions(permMap);
    }

    loadResources();
  }, [template]);

  const loadResources = async () => {
    try {
      setLoadingResources(true);
      // Get permission hierarchy rules to know what resources exist
      const response = await roleTemplatesAPI.getPermissionHierarchyRules();
      // For now, we'll use a static list of common resources
      const commonResources = [
        { id: 1, name: 'candidates', display_name: 'Candidates' },
        { id: 2, name: 'interviews', display_name: 'Interviews' },
        { id: 3, name: 'offers', display_name: 'Offers' },
        { id: 4, name: 'employees', display_name: 'Employees' },
        { id: 5, name: 'reports', display_name: 'Reports' },
        { id: 6, name: 'users', display_name: 'Users' },
        { id: 7, name: 'roles', display_name: 'Roles' },
        { id: 8, name: 'business_unit', display_name: 'Business Units' },
        { id: 9, name: 'recruitment', display_name: 'Recruitment' },
        { id: 10, name: 'invoices', display_name: 'Invoices' },
      ];
      setAllResources(commonResources);
    } catch (err) {
      console.error('Failed to load resources', err);
    } finally {
      setLoadingResources(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    // Clear error for this field
    if (errors[name]) {
      setErrors((prev) => ({
        ...prev,
        [name]: '',
      }));
    }
  };

  const handlePermissionChange = (resourceId, action, checked) => {
    const key = `${resourceId}`;
    setSelectedPermissions((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        [action]: checked,
      },
    }));
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Template name is required';
    }

    if (!formData.display_name.trim()) {
      newErrors.display_name = 'Display name is required';
    }

    // Check if at least one permission is selected
    const hasPermissions = Object.values(selectedPermissions).some((perm) =>
      Object.values(perm).some((v) => v)
    );

    if (!hasPermissions) {
      newErrors.permissions = 'At least one permission must be selected';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    // Convert selected permissions to API format
    const permissions = [];
    Object.entries(selectedPermissions).forEach(([resourceId, actions]) => {
      if (Object.values(actions).some((v) => v)) {
        permissions.push({
          resource_id: parseInt(resourceId),
          can_view: actions.view,
          can_create: actions.create,
          can_edit: actions.edit,
          can_delete: actions.delete,
        });
      }
    });

    const submitData = {
      ...formData,
      permissions,
    };

    onSave(submitData);
  };

  return (
    <div className="role-template-form">
      <form onSubmit={handleSubmit}>
        {/* Basic Info Section */}
        <section className="form-section">
          <h3>Basic Information</h3>

          <div className="form-group">
            <label htmlFor="name">Template Name *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="e.g., Senior Recruiter"
              disabled={template?.is_system}
              className={errors.name ? 'error' : ''}
            />
            {errors.name && <span className="error-text">{errors.name}</span>}
            <small>Internal identifier (cannot contain spaces)</small>
          </div>

          <div className="form-group">
            <label htmlFor="display_name">Display Name *</label>
            <input
              type="text"
              id="display_name"
              name="display_name"
              value={formData.display_name}
              onChange={handleInputChange}
              placeholder="e.g., Senior Recruiter"
              disabled={template?.is_system}
              className={errors.display_name ? 'error' : ''}
            />
            {errors.display_name && <span className="error-text">{errors.display_name}</span>}
            <small>User-facing name</small>
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="What is this role for?"
              disabled={template?.is_system}
              rows={3}
            />
            <small>Optional description of this role's purpose</small>
          </div>
        </section>

        {/* Permissions Section */}
        <section className="form-section">
          <h3>Permissions</h3>
          {errors.permissions && <span className="error-text">{errors.permissions}</span>}

          {loadingResources ? (
            <p>Loading resources...</p>
          ) : (
            <div className="permissions-grid">
              <table className="permissions-table">
                <thead>
                  <tr>
                    <th>Resource</th>
                    <th>View</th>
                    <th>Create</th>
                    <th>Edit</th>
                    <th>Delete</th>
                  </tr>
                </thead>
                <tbody>
                  {allResources.map((resource) => (
                    <tr key={resource.id}>
                      <td className="resource-name">{resource.display_name}</td>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedPermissions[resource.id]?.view || false}
                          onChange={(e) =>
                            handlePermissionChange(resource.id, 'view', e.target.checked)
                          }
                          disabled={template?.is_system}
                        />
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedPermissions[resource.id]?.create || false}
                          onChange={(e) =>
                            handlePermissionChange(resource.id, 'create', e.target.checked)
                          }
                          disabled={template?.is_system}
                        />
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedPermissions[resource.id]?.edit || false}
                          onChange={(e) =>
                            handlePermissionChange(resource.id, 'edit', e.target.checked)
                          }
                          disabled={template?.is_system}
                        />
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedPermissions[resource.id]?.delete || false}
                          onChange={(e) =>
                            handlePermissionChange(resource.id, 'delete', e.target.checked)
                          }
                          disabled={template?.is_system}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Actions */}
        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || template?.is_system}
          >
            {loading ? 'Saving...' : template ? 'Update Template' : 'Create Template'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default RoleTemplateForm;
