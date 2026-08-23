import React, { useState, useEffect } from 'react';
import { Input, Button } from './ui';
import { toast } from 'react-toastify';
import { apiRequest } from '../services/api/client';

const RoleTemplateEditor = ({ mode = 'create', templateId = null, onClose, onSuccess, modules }) => {
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: ''
  });
  const [permissions, setPermissions] = useState({});
  const [expandedModules, setExpandedModules] = useState({});

  // Load template data when editing
  useEffect(() => {
    if (mode === 'edit' && templateId) {
      const fetchTemplate = async () => {
        try {
          const { data } = await apiRequest(`/admin/role-templates/${templateId}`, {
            method: 'GET'
          });

          // Populate form data
          setFormData({
            name: data.name || '',
            description: data.description || ''
          });

          // Convert permissions to hierarchical structure
          const permsHierarchy = {};
          if (Array.isArray(data.permissions)) {
            data.permissions.forEach(perm => {
              if (perm.resource_id !== undefined) {
                const resourceName = perm.resource_name || `resource_${perm.resource_id}`;
                if (!permsHierarchy[resourceName]) {
                  permsHierarchy[resourceName] = {};
                }
                permsHierarchy[resourceName].view = perm.can_view || false;
                permsHierarchy[resourceName].create = perm.can_create || false;
                permsHierarchy[resourceName].edit = perm.can_edit || false;
                permsHierarchy[resourceName].delete = perm.can_delete || false;
              } else if (perm.name) {
                const parts = perm.name.split('_');
                if (parts.length >= 2) {
                  const verb = parts[parts.length - 1];
                  const module = parts.slice(0, -1).join('_');
                  if (!permsHierarchy[module]) {
                    permsHierarchy[module] = {};
                  }
                  permsHierarchy[module][verb] = true;
                }
              }
            });
          }
          setPermissions(permsHierarchy);
        } catch (err) {
          console.error('Failed to load template:', err);
          toast.error('Failed to load template data');
        } finally {
          setLoading(false);
        }
      };

      fetchTemplate();
    }
  }, [mode, templateId]);

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Template name is required');
      return;
    }

    setSaving(true);
    try {
      if (mode === 'create') {
        // Create new template
        const response = await apiRequest('/admin/role-templates', {
          method: 'POST',
          body: JSON.stringify({
            name: formData.name,
            display_name: formData.name,
            description: formData.description,
            permissions: []
          })
        });

        toast.success('Role template created successfully');
        if (onSuccess) onSuccess(response.data);
        onClose();
      } else {
        // Update existing template
        await apiRequest(`/admin/role-templates/${templateId}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: formData.name,
            description: formData.description
          })
        });

        toast.success('Role template updated successfully');
        if (onSuccess) onSuccess();
        onClose();
      }
    } catch (err) {
      toast.error(err.message || `Failed to ${mode === 'create' ? 'create' : 'update'} template`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 max-w-md w-full">
          <p className="text-gray-600">Loading template...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {mode === 'create' ? 'Create New Role Template' : 'Edit Role Template'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {mode === 'create'
                ? 'Create a new role template and configure permissions'
                : 'Update template details and manage permissions'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ✕
          </button>
        </div>

        {/* Form Content */}
        <div className="p-6 space-y-6">
          {/* Template Details */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Template Details</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Template Name *
              </label>
              <Input
                type="text"
                value={formData.name}
                onChange={(val) => setFormData({ ...formData, name: val })}
                placeholder="e.g., Senior Recruiter"
                disabled={mode === 'edit'}
                className={mode === 'edit' ? 'bg-gray-100' : ''}
              />
              {mode === 'edit' && (
                <p className="text-xs text-gray-500 mt-1">Template name cannot be changed</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe what this role template is for..."
                rows="3"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Note about permissions */}
          {mode === 'create' && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
              <p className="text-sm text-blue-800">
                <strong>Note:</strong> After creating this template, you can configure its permissions by clicking "Edit Permissions" on the template card.
              </p>
            </div>
          )}

          {mode === 'edit' && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
              <p className="text-sm text-blue-800">
                <strong>Manage Permissions:</strong> To configure resource permissions for this template, use the "Edit Permissions" interface. This form is for updating basic template information.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t px-6 py-4 flex items-center justify-end gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            loading={saving}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            {mode === 'create' ? 'Create Template' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default RoleTemplateEditor;
