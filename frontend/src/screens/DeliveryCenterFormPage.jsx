import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, X } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';
import { hasPermission } from '../utils/permissionsRoleTemplate';

// The delivery-centers CRUD lives in users_access_control.py, which is
// mounted at /api/admin/users-access-control (not the bare /delivery-centers
// this screen used to call) - pass the full path so apiRequest's "starts
// with /api" check uses it as-is instead of prepending /api/v1 again.
const DELIVERY_CENTERS_PATH = '/api/v1/api/admin/users-access-control/delivery-centers';

export default function DeliveryCenterFormPage() {
  // Permission Gate: Only users with delivery-centers.edit can create/edit delivery centers
  if (!hasPermission('delivery-centers', 'edit')) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg p-6 max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">You do not have permission to manage delivery centers.</p>
          <button
            onClick={() => window.history.back()}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const { dcId } = useParams();
  const navigate = useNavigate();
  const mode = dcId ? 'edit' : 'create';

  const [formData, setFormData] = useState({
    name: '',
    center_type: 'Delivery',
    city: '',
    country: '',
    headcount: 0
  });
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    if (mode === 'edit' && dcId) {
      loadDeliveryCenter();
    }
  }, [dcId, mode]);

  const loadDeliveryCenter = async () => {
    try {
      setLoading(true);
      const res = await apiRequest(DELIVERY_CENTERS_PATH);
      const dc = (res.data?.delivery_centers || []).find(d => String(d.id) === String(dcId));
      if (dc) {
        setFormData({
          name: dc.name || '',
          center_type: dc.center_type || 'Delivery',
          city: dc.city || '',
          country: dc.country || '',
          headcount: dc.headcount || 0
        });
      } else {
        setActionError('Delivery Center not found');
      }
    } catch (err) {
      console.error('Failed to load delivery center:', err);
      setActionError('Failed to load delivery center');
    } finally {
      setLoading(false);
    }
  };

  // Input (components/ui/Input.js) calls onChange with the raw string value,
  // not a synthetic event; the native <select> below still passes a real event.
  // Accept either shape so both control types can share one handler per field.
  const setField = (field) => (valOrEvent) => {
    const value = valOrEvent && valOrEvent.target ? valOrEvent.target.value : valOrEvent;
    setFormData(prev => ({
      ...prev,
      [field]: field === 'headcount' ? parseInt(value, 10) || 0 : value
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setActionError('Delivery Center name is required');
      return;
    }

    setSaving(true);
    try {
      if (mode === 'create') {
        await apiRequest(DELIVERY_CENTERS_PATH, {
          method: 'POST',
          body: JSON.stringify(formData)
        });
      } else {
        await apiRequest(`${DELIVERY_CENTERS_PATH}/${dcId}`, {
          method: 'PUT',
          body: JSON.stringify(formData)
        });
      }
      setActionError(null);
      navigate('/admin/users-access-control/delivery-centers');
    } catch (err) {
      setActionError(err?.data?.detail || err?.message || 'Failed to save delivery center');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    navigate('/admin/users-access-control/delivery-centers');
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
            {mode === 'create' ? 'Add Delivery Center' : 'Edit Delivery Center'}
          </h1>
        </div>
      </div>

      {/* Form */}
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
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Delivery Center Name *
            </label>
            <Input
              type="text"
              value={formData.name}
              onChange={setField('name')}
              placeholder="e.g., Mumbai, India"
              disabled={saving}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Type
            </label>
            <select
              name="center_type"
              value={formData.center_type}
              onChange={setField('center_type')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              disabled={saving}
            >
              <option value="Delivery">Delivery Center</option>
              <option value="HQ">Headquarters</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                City
              </label>
              <Input
                type="text"
                value={formData.city}
                onChange={setField('city')}
                placeholder="City"
                disabled={saving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Country
              </label>
              <Input
                type="text"
                value={formData.country}
                onChange={setField('country')}
                placeholder="Country"
                disabled={saving}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Headcount
            </label>
            <Input
              type="number"
              value={formData.headcount}
              onChange={setField('headcount')}
              placeholder="Number of employees"
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
              disabled={saving || !formData.name.trim()}
              className="bg-bx-orange hover:bg-bx-orange-hover text-white"
            >
              {saving ? (mode === 'create' ? 'Adding...' : 'Updating...') : (mode === 'create' ? 'Add Delivery Center' : 'Update Delivery Center')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
