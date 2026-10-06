import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertCircle, X } from 'lucide-react';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';
import { toast } from 'react-toastify';
import { hasPermission } from '../utils/permissionsRoleTemplate';

// users_access_control router is mounted under /api/admin/users-access-control
const DELIVERY_CENTERS_PATH = '/api/v1/api/admin/users-access-control/delivery-centers';

export default function BusinessUnitFormPage() {
  // Permission Gate: Only users with business-units.edit can create/edit business units
  if (!hasPermission('business-units', 'edit')) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg p-6 max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">You do not have permission to manage business units.</p>
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

  const { buId } = useParams();
  const navigate = useNavigate();
  const mode = buId ? 'edit' : 'create';

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    location_id: '',
    partner_node_id: ''
  });
  // Goal tree: Location (Delivery Centers, e.g. BXUS/BXIN) -> Partner -> BU
  const [locations, setLocations] = useState([]);
  const [partners, setPartners] = useState([]);
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    if (mode === 'edit' && buId) {
      loadBusinessUnit();
    }
  }, [buId, mode]);

  useEffect(() => {
    Promise.all([
      apiRequest(DELIVERY_CENTERS_PATH),
      apiRequest('/org/nodes'),
      apiRequest('/org/hierarchy-reference'),
    ])
      .then(([locRes, nodesRes, refRes]) => {
        setLocations(locRes.data?.delivery_centers || []);
        const partnerLevel = (refRes.data?.levels || []).find((l) => /^partner/i.test(l.name))?.level;
        const nodes = Array.isArray(nodesRes.data) ? nodesRes.data : [];
        setPartners(partnerLevel ? nodes.filter((n) => n.hierarchy_level === partnerLevel) : []);
      })
      .catch((err) => setActionError(`Could not load locations/partners: ${err.message}`));
  }, []);

  const loadBusinessUnit = async () => {
    try {
      setLoading(true);
      const { data } = await apiRequest(`/rbac/business-units/${buId}`);
      if (data) {
        setFormData({
          name: data.name || '',
          description: data.description || '',
          location_id: data.location_id || '',
          partner_node_id: data.partner_node_id || ''
        });
      }
    } catch (err) {
      console.error('Failed to load business unit:', err);
      setActionError('Failed to load business unit');
      navigate('/admin/users-access-control/business-units');
    } finally {
      setLoading(false);
    }
  };

  // Input (components/ui/Input.js) calls onChange with the raw string value,
  // not a synthetic event, so this handler must be curried per field rather
  // than reading e.target.name/e.target.value.
  const setField = (field) => (val) => {
    setFormData(prev => ({ ...prev, [field]: val }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      setActionError('Business Unit Name is required');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim() || null,
        // "" clears the link on the backend
        location_id: formData.location_id,
        partner_node_id: formData.partner_node_id
      };

      if (mode === 'create') {
        await apiRequest('/rbac/business-units', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        setActionError(null);
      } else {
        await apiRequest(`/rbac/business-units/${buId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        setActionError(null);
      }
      navigate('/admin/users-access-control/business-units');
    } catch (err) {
      setActionError(err?.message || 'Failed to save business unit');
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
              Business Unit Name *
            </label>
            <Input
              type="text"
              value={formData.name}
              onChange={setField('name')}
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
              onChange={(e) => setField('description')(e.target.value)}
              placeholder="Add a description..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              rows="3"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Location (legal entity)
            </label>
            <select
              value={formData.location_id}
              onChange={(e) => setField('location_id')(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              disabled={saving}
            >
              <option value="">Not assigned</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>{l.name}{l.country ? ` (${l.country})` : ''}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">Locations are managed under Delivery Centers (e.g. BXUS, BXIN).</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Partner
            </label>
            <select
              value={formData.partner_node_id}
              onChange={(e) => setField('partner_node_id')(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              disabled={saving}
            >
              <option value="">Not assigned</option>
              {partners.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">Partners are org-chart members at the Partner level (Organizational Hierarchy).</p>
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
