import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';
import { toast } from 'react-toastify';

export default function BusinessUnitFormPage() {
  const { buId } = useParams();
  const navigate = useNavigate();
  const mode = buId ? 'edit' : 'create';

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    region: '',
    continent: ''
  });
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (mode === 'edit' && buId) {
      loadBusinessUnit();
    }
  }, [buId, mode]);

  const loadBusinessUnit = async () => {
    try {
      setLoading(true);
      const { data } = await apiRequest(`/rbac/business-units/${buId}`, { skipAuth: true });
      if (data) {
        setFormData({
          name: data.name || '',
          description: data.description || '',
          region: data.region || '',
          continent: data.continent || ''
        });
      }
    } catch (err) {
      console.error('Failed to load business unit:', err);
      toast.error('Failed to load business unit');
      navigate('/admin/users-access-control/business-units');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      toast.error('Business Unit Name is required');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim() || null,
        ...(formData.region && { region: formData.region.trim() }),
        ...(formData.continent && { continent: formData.continent.trim() })
      };

      if (mode === 'create') {
        await apiRequest('/rbac/business-units', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        toast.success('Business Unit created successfully');
      } else {
        await apiRequest(`/rbac/business-units/${buId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        toast.success('Business Unit updated successfully');
      }
      navigate('/admin/users-access-control/business-units');
    } catch (err) {
      toast.error(err?.message || 'Failed to save business unit');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    navigate('/admin/users-access-control/business-units');
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
            {mode === 'create' ? 'Create Business Unit' : 'Edit Business Unit'}
          </h1>
        </div>
      </div>

      {/* Form */}
      <Card className="p-6 max-w-2xl">
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Business Unit Name *
            </label>
            <Input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="e.g., Asia Pacific"
              disabled={saving}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              placeholder="Add a description..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              rows="3"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Region
            </label>
            <Input
              type="text"
              name="region"
              value={formData.region}
              onChange={handleInputChange}
              placeholder="e.g., Asia, Europe, North America"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Continent
            </label>
            <Input
              type="text"
              name="continent"
              value={formData.continent}
              onChange={handleInputChange}
              placeholder="e.g., Asia, Europe, North America"
              disabled={saving}
            />
          </div>

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
              {saving ? (mode === 'create' ? 'Creating...' : 'Updating...') : (mode === 'create' ? 'Create' : 'Update')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
