import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, X } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import LocationCascadeSelect, { parseLocation } from '../components/ui/LocationCascadeSelect';
import { Country, State } from "../utils/geo";
import { apiRequest } from '../services/api/client';
import { hasPermission } from '../utils/permissionsRoleTemplate';

// The delivery-centers CRUD lives in users_access_control.py, which is
// mounted at /api/admin/users-access-control (not the bare /delivery-centers
// this screen used to call) - pass the full path so apiRequest's "starts
// with /api" check uses it as-is instead of prepending /api/v1 again.
const DELIVERY_CENTERS_PATH = '/api/v1/api/admin/users-access-control/delivery-centers';

export default function DeliveryCenterFormPage() {
  const { dcId } = useParams();
  const navigate = useNavigate();
  const mode = dcId ? 'edit' : 'create';
  // Permission Gate: Only users with delivery-centers.edit can create/edit delivery centers.
  // Evaluated before effects so no API calls fire for users without access.
  const canEditCenters = hasPermission('delivery-centers', 'edit');

  const [formData, setFormData] = useState({
    name: '',
    center_type: 'Delivery',
    // Country -> State -> City picker value (same component as Add Candidate)
    location: { countryCode: '', stateCode: '', city: '' },
    parent_company_id: '',
    headcount: 0
  });
  // Parent companies a subsidiary can belong to
  const [parents, setParents] = useState([]);
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState(null);

  const loadDeliveryCenter = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiRequest(DELIVERY_CENTERS_PATH);
      const dc = (res.data?.delivery_centers || []).find(d => String(d.id) === String(dcId));
      if (dc) {
        setFormData({
          name: dc.name || '',
          center_type: dc.center_type || 'Delivery',
          location: parseLocation([dc.city, dc.state, dc.country].filter(Boolean).join(', ')),
          parent_company_id: dc.parent_company_id || '',
          headcount: dc.headcount || 0
        });
      } else {
        setActionError('Company not found');
      }
    } catch (err) {
      console.error('[DeliveryCenterFormPage] Failed to load delivery center:', err);
      setActionError(`Failed to load company: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [dcId]);

  useEffect(() => {
    if (canEditCenters && mode === 'edit' && dcId) {
      loadDeliveryCenter();
    }
  }, [canEditCenters, dcId, mode, loadDeliveryCenter]);

  useEffect(() => {
    if (!canEditCenters) return;
    apiRequest(DELIVERY_CENTERS_PATH)
      .then((res) => {
        const parentList = (res.data?.delivery_centers || []).filter((c) => c.center_type === 'HQ' && String(c.id) !== String(dcId));
        setParents(parentList);
        // With no parent company yet, the first company added is the parent
        if (mode === 'create' && parentList.length === 0) {
          setFormData((prev) => ({ ...prev, center_type: 'HQ' }));
        }
      })
      .catch((err) => {
        console.error('[DeliveryCenterFormPage] Failed to load companies:', err);
        setActionError(`Could not load companies: ${err.message}`);
      });
  }, [canEditCenters, dcId, mode]);

  if (!canEditCenters) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg p-6 max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">You do not have permission to manage companies.</p>
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
      setActionError('Company name is required');
      return;
    }
    // Every company reports to the holding company; a parent company is optional

    setSaving(true);
    try {
      const { location, ...rest } = formData;
      const country = location.countryCode ? Country.getCountryByCode(location.countryCode) : null;
      const state = location.stateCode ? State.getStateByCodeAndCountry(location.stateCode, location.countryCode) : null;
      const body = JSON.stringify({
        ...rest,
        parent_company_id: rest.center_type === 'HQ' ? '' : rest.parent_company_id,
        country: country?.name || '',
        state: state?.name || '',
        city: location.city || '',
      });
      if (mode === 'create') {
        await apiRequest(DELIVERY_CENTERS_PATH, { method: 'POST', body });
      } else {
        await apiRequest(`${DELIVERY_CENTERS_PATH}/${dcId}`, { method: 'PUT', body });
      }
      setActionError(null);
      navigate('/admin/users-access-control/delivery-centers');
    } catch (err) {
      setActionError(err?.data?.detail || err?.message || 'Failed to save company');
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
            {mode === 'create' ? 'Add Company' : 'Edit Company'}
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
              Company Name *
            </label>
            <Input
              type="text"
              value={formData.name}
              onChange={setField('name')}
              placeholder="e.g., BX-US or BX-IN"
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
              <option value="HQ">Parent company</option>
              <option value="Delivery" disabled={parents.length === 0}>Subsidiary / subcontracting company</option>
            </select>
            {parents.length === 0 && (
              <p className="mt-1 text-xs text-gray-500">Add the parent company first; subsidiaries are added under it.</p>
            )}
          </div>

          {formData.center_type !== 'HQ' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Parent company *</label>
              <select
                value={formData.parent_company_id}
                onChange={setField('parent_company_id')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                disabled={saving}
              >
                <option value="">Select parent company</option>
                {parents.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          )}

          <div>
            <div className="block text-sm font-medium text-gray-700 mb-1">Location</div>
            <LocationCascadeSelect
              value={formData.location}
              onChange={(location) => setFormData(prev => ({ ...prev, location }))}
              disabled={saving}
            />
          </div>

          <p className="text-xs text-gray-500">
            Each company has its own revenue and headcount targets. Headcount is counted from the employees whose employer is this company.
          </p>

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
              {saving ? (mode === 'create' ? 'Adding...' : 'Updating...') : (mode === 'create' ? 'Add Company' : 'Update Company')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
