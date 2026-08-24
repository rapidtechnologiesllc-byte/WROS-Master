import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import RoleTemplateForm from '../components/AdminUI/RoleTemplateForm';
import { apiRequest } from '../services/api/client';
import { toast } from 'react-toastify';

export default function RoleTemplateFormPage() {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const mode = templateId ? 'edit' : 'create';

  const [template, setTemplate] = useState(null);
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [businessUnits, setBusinessUnits] = useState([]);

  useEffect(() => {
    loadBusinessUnits();
    if (mode === 'edit' && templateId) {
      loadTemplate();
    }
  }, [templateId, mode]);

  const loadBusinessUnits = async () => {
    try {
      const res = await apiRequest('/rbac/business-units');
      setBusinessUnits(res.data?.business_units || []);
    } catch (err) {
      console.error('Failed to load business units:', err);
    }
  };

  const loadTemplate = async () => {
    try {
      setLoading(true);
      const res = await apiRequest(`/admin/role-templates/${templateId}`);
      setTemplate(res.data || null);
    } catch (err) {
      console.error('Failed to load template:', err);
      toast.error('Failed to load role template');
      navigate('/admin/role-templates');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (formData) => {
    setSaving(true);
    try {
      if (mode === 'create') {
        await apiRequest('/admin/role-templates', {
          method: 'POST',
          body: JSON.stringify(formData)
        });
        toast.success('Role template created successfully');
      } else {
        await apiRequest(`/admin/role-templates/${templateId}`, {
          method: 'PUT',
          body: JSON.stringify(formData)
        });
        toast.success('Role template updated successfully');
      }
      navigate('/admin/role-templates');
    } catch (err) {
      toast.error(err.message || 'Failed to save role template');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    navigate('/admin/role-templates');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Loading template...</div>
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
            {mode === 'create' ? 'Create Role Template' : 'Edit Role Template'}
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            {mode === 'create'
              ? 'Define permissions for a new role'
              : `Update permissions for "${template?.display_name}"`}
          </p>
        </div>
      </div>

      {/* Form */}
      <Card className="p-6">
        <RoleTemplateForm
          template={mode === 'edit' ? template : null}
          businessUnits={businessUnits}
          onSave={handleSave}
          onCancel={handleCancel}
          loading={saving}
        />
      </Card>
    </div>
  );
}
