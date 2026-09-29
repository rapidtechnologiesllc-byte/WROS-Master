import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X, AlertCircle } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';

// The delivery-centers CRUD lives in users_access_control.py, which is
// mounted at /api/admin/users-access-control (not the bare /delivery-centers
// this screen used to call) - pass the full path so apiRequest's "starts
// with /api" check uses it as-is instead of prepending /api/v1 again.
const DELIVERY_CENTERS_PATH = '/api/v1/api/admin/users-access-control/delivery-centers';

export default function DeliveryCentersAdmin() {
  const [centers, setCenters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [form, setForm] = useState({
    name: '',
    city: '',
    country: '',
    center_type: 'Delivery',
    headcount: 0
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    loadDeliveryCenters();
  }, []);

  const loadDeliveryCenters = async () => {
    try {
      setLoading(true);
      const res = await apiRequest(DELIVERY_CENTERS_PATH);
      setCenters(res.data?.delivery_centers || []);
    } catch (err) {
      console.error("Failed to load delivery centers:", err);
      setActionError("Failed to load delivery centers");
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    const newErrors = {};
    if (!form.name?.trim()) newErrors.name = "Center name is required";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAdd = () => {
    setEditingId(null);
    setForm({
      name: '',
      city: '',
      country: '',
      center_type: 'Delivery',
      headcount: 0
    });
    setShowForm(true);
  };

  const handleEdit = (center) => {
    setEditingId(center.id);
    setForm({
      name: center.name || '',
      city: center.city || '',
      country: center.country || '',
      center_type: center.center_type || 'Delivery',
      headcount: center.headcount || 0
    });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    try {
      if (editingId) {
        await apiRequest(`${DELIVERY_CENTERS_PATH}/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(form)
        });
        setActionError(null);
      } else {
        await apiRequest(DELIVERY_CENTERS_PATH, {
          method: 'POST',
          body: JSON.stringify(form)
        });
        setActionError(null);
      }
      setShowForm(false);
      loadDeliveryCenters();
    } catch (err) {
      console.error("Failed to save delivery center:", err);
      setActionError(err.data?.detail || "Failed to save delivery center");
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Are you sure?")) return;

    try {
      await apiRequest(`${DELIVERY_CENTERS_PATH}/${id}`, { method: 'DELETE' });
      setActionError(null);
      loadDeliveryCenters();
    } catch (err) {
      console.error("Failed to delete delivery center:", err);
      setActionError("Failed to delete delivery center");
    }
  };

  return (
    <div className="space-y-6">
      {actionError && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-rose-700 hover:text-rose-900">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Delivery Centers</h1>
        <Button
          onClick={handleAdd}
          className="bg-blue-600 text-white flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Delivery Center
        </Button>
      </div>

      {showForm && (
        <Card className="bg-blue-50 border border-blue-200 p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">
              {editingId ? 'Edit' : 'Add'} Delivery Center
            </h2>
            <button
              onClick={() => setShowForm(false)}
              className="p-1 hover:bg-gray-200 rounded"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium mb-1">Center Name *</label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g., Bangalore"
                error={errors.name}
              />
              {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
            </div>

            {/* City */}
            <div>
              <label className="block text-sm font-medium mb-1">City</label>
              <Input
                value={form.city}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
                placeholder="e.g., Bangalore"
              />
            </div>

            {/* Country */}
            <div>
              <label className="block text-sm font-medium mb-1">Country</label>
              <Input
                value={form.country}
                onChange={(e) => setForm({ ...form, country: e.target.value })}
                placeholder="e.g., India"
              />
            </div>

            {/* Center Type */}
            <div>
              <label className="block text-sm font-medium mb-1">Center Type</label>
              <select
                value={form.center_type}
                onChange={(e) => setForm({ ...form, center_type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none"
              >
                <option value="HQ">HQ</option>
                <option value="Delivery">Delivery</option>
              </select>
            </div>

            {/* Headcount */}
            <div>
              <label className="block text-sm font-medium mb-1">Headcount</label>
              <Input
                type="number"
                min="0"
                value={form.headcount}
                onChange={(e) => setForm({ ...form, headcount: parseInt(e.target.value, 10) || 0 })}
                placeholder="0"
              />
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-4 border-t">
              <Button onClick={handleSave} className="flex-1 bg-blue-600 text-white">
                {editingId ? 'Update' : 'Create'} Center
              </Button>
              <Button onClick={() => setShowForm(false)} className="flex-1 bg-gray-300">
                Cancel
              </Button>
            </div>
          </div>
        </Card>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : centers.length === 0 ? (
        <Card className="text-center py-8 text-gray-500">
          <p>No delivery centers yet. Create one to get started.</p>
        </Card>
      ) : (
        <div className="grid gap-4">
          {centers.map(center => (
            <Card key={center.id} className="p-4">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-semibold text-lg">{center.name}</h3>
                    {center.center_type && (
                      <span className="text-xs bg-gray-200 px-2 py-1 rounded">{center.center_type}</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    {[center.city, center.country].filter(Boolean).join(', ') || 'No location set'}
                  </p>
                  {!!center.headcount && (
                    <p className="text-sm text-gray-600">{center.headcount} headcount</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEdit(center)}
                    className="p-2 hover:bg-blue-100 rounded text-blue-600"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(center.id)}
                    className="p-2 hover:bg-red-100 rounded text-red-600"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
