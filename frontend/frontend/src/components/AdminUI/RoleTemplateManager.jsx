import React, { useState, useEffect } from 'react';
import { roleTemplatesAPI } from '../../services/api/roleTemplates';
import RoleTemplateList from './RoleTemplateList';
import RoleTemplateForm from './RoleTemplateForm';
import PermissionMatrix from './PermissionMatrix';
import PermissionValidation from './PermissionValidation';
import AuditTrail from './AuditTrail';
import PermissionHierarchyViewer from './PermissionHierarchyViewer';
import PermissionMatrixEditor from './PermissionMatrixEditor';
import './RoleTemplateManager.css';

const RoleTemplateManager = () => {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [activeTab, setActiveTab] = useState('list'); // list, edit, preview, matrix, audit
  const [expanded, setExpanded] = useState(null);
  const [auditTrail, setAuditTrail] = useState([]);
  const [validation, setValidation] = useState(null);
  const [resources, setResources] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [allResources, setAllResources] = useState([]);
  const [resourcesByModule, setResourcesByModule] = useState({});

  // Load all templates on mount
  useEffect(() => {
    loadTemplates();
    loadBusinessUnits();
  }, []);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const response = await roleTemplatesAPI.listTemplates();
      setTemplates(response.data.role_templates || []);
      setError(null);
    } catch (err) {
      setError('Failed to load role templates');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadBusinessUnits = async () => {
    try {
      const response = await roleTemplatesAPI.getBusinessUnits();
      setBusinessUnits(response.data.business_units || []);
    } catch (err) {
      console.error('Failed to load business units', err);
    }
  };

  const handleSelectTemplate = (template) => {
    setSelectedTemplate(template);
    setActiveTab('edit');
    loadAuditTrail(template.id);
    expandPermissions(template.id);
  };

  const handleCreateNew = () => {
    setSelectedTemplate(null);
    setActiveTab('edit');
    setExpanded(null);
    setAuditTrail([]);
    setValidation(null);
  };

  const handleSaveTemplate = async (formData) => {
    try {
      setLoading(true);

      if (selectedTemplate?.id) {
        // Update existing
        await roleTemplatesAPI.updateTemplate(selectedTemplate.id, formData);
        setSuccessMessage('Role template updated successfully');
      } else {
        // Create new
        await roleTemplatesAPI.createTemplate(formData);
        setSuccessMessage('Role template created successfully');
      }

      // Reload templates and reset
      await loadTemplates();
      setSelectedTemplate(null);
      setActiveTab('list');

      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to save role template');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTemplate = async (templateId) => {
    if (!window.confirm('Are you sure you want to delete this role template? This action cannot be undone.')) {
      return;
    }

    try {
      setLoading(true);
      await roleTemplatesAPI.deleteTemplate(templateId);
      setSuccessMessage('Role template deleted successfully');
      await loadTemplates();
      setSelectedTemplate(null);
      setActiveTab('list');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError('Failed to delete role template');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const expandPermissions = async (templateId) => {
    try {
      const response = await roleTemplatesAPI.expandPermissions(templateId);
      setExpanded(response.data);

      // Validate permissions
      if (response.data.permissions) {
        const validation = await roleTemplatesAPI.validatePermissions(response.data.permissions);
        setValidation(validation.data);
      }
    } catch (err) {
      console.error('Failed to expand permissions', err);
    }
  };

  const loadAuditTrail = async (templateId) => {
    try {
      const response = await roleTemplatesAPI.getAuditTrail(templateId);
      setAuditTrail(response.data.audit_trail || []);
    } catch (err) {
      console.error('Failed to load audit trail', err);
    }
  };

  if (!templates.length && !loading && activeTab === 'list') {
    return (
      <div className="role-template-manager">
        <div className="manager-header">
          <h1>Role Template Management</h1>
          <p className="subtitle">Manage role templates and permissions</p>
        </div>

        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h2>No Role Templates</h2>
          <p>Create your first role template to get started</p>
          <button className="btn btn-primary" onClick={handleCreateNew}>
            + Create Role Template
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="role-template-manager">
      {/* Header */}
      <div className="manager-header">
        <h1>Role Template Management</h1>
        <button className="btn btn-primary" onClick={handleCreateNew}>
          + Create New Template
        </button>
      </div>

      {/* Messages */}
      {error && <div className="alert alert-error">{error}</div>}
      {successMessage && <div className="alert alert-success">{successMessage}</div>}

      <div className="manager-content">
        {/* Sidebar */}
        <div className="manager-sidebar">
          <RoleTemplateList
            templates={templates}
            selectedId={selectedTemplate?.id}
            onSelect={handleSelectTemplate}
            onDelete={handleDeleteTemplate}
            loading={loading}
          />
        </div>

        {/* Main Content */}
        <div className="manager-main">
          {selectedTemplate || activeTab === 'edit' ? (
            <>
              {/* Tabs */}
              <div className="tabs">
                <button
                  className={`tab ${activeTab === 'edit' ? 'active' : ''}`}
                  onClick={() => setActiveTab('edit')}
                >
                  📝 Edit
                </button>
                <button
                  className={`tab ${activeTab === 'preview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('preview')}
                >
                  👁️ Preview
                </button>
                {selectedTemplate && (
                  <button
                    className={`tab ${activeTab === 'audit' ? 'active' : ''}`}
                    onClick={() => setActiveTab('audit')}
                  >
                    📊 Audit Trail
                  </button>
                )}
              </div>

              {/* Tab Content */}
              <div className="tab-content">
                {activeTab === 'edit' && (
                  <RoleTemplateForm
                    template={selectedTemplate}
                    businessUnits={businessUnits}
                    onSave={handleSaveTemplate}
                    onCancel={() => {
                      setSelectedTemplate(null);
                      setActiveTab('list');
                    }}
                    loading={loading}
                  />
                )}

                {activeTab === 'preview' && selectedTemplate && (
                  <div className="preview-container">
                    <div className="preview-section">
                      <h3>📊 Permission Matrix</h3>
                      <PermissionMatrix
                        template={selectedTemplate}
                        loading={loading}
                      />
                    </div>

                    <div className="preview-section">
                      <h3>🎯 Expanded Permissions</h3>
                      {expanded ? (
                        <div className="permissions-preview">
                          <div className="permission-group">
                            <h4>Direct Permissions</h4>
                            <div className="permission-list">
                              {expanded.permissions?.slice(0, 10).map((perm, idx) => (
                                <span key={idx} className="permission-tag">
                                  {perm}
                                </span>
                              ))}
                              {expanded.total_permissions > 10 && (
                                <span className="permission-more">
                                  +{expanded.total_permissions - 10} more
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <p>Loading permissions...</p>
                      )}
                    </div>

                    {validation && (
                      <div className="preview-section">
                        <h3>⚠️ Validation Results</h3>
                        <PermissionValidation validation={validation} />
                      </div>
                    )}

                    <div className="preview-section">
                      <h3>🔗 Permission Hierarchy</h3>
                      <PermissionHierarchyViewer templateId={selectedTemplate.id} />
                    </div>
                  </div>
                )}

                {activeTab === 'audit' && selectedTemplate && (
                  <div className="audit-container">
                    <h3>📋 Change History</h3>
                    <AuditTrail logs={auditTrail} />
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-selection">
              <div className="empty-icon">👈</div>
              <h2>Select a Role Template</h2>
              <p>Choose a template from the list to view or edit details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RoleTemplateManager;
