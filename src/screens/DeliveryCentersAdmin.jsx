import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import { apiRequest } from '../services/api/client';

const toast = {
  success: (msg) => console.log('✓', msg),
  error: (msg) => console.error('✗', msg)
};

export default function DeliveryCentersAdmin() {
  const [centers, setCenters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    name: '',
    code: '',
    location: '',
    contact_email: '',
    contact_phone: '',
    active: true
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    loadDeliveryCenters();
  }, []);

  const loadDeliveryCenters = async () => {
    try {
      setLoading(true);
      const res = await apiRequest('/delivery-centers');
      setCenters(res.data || []);
    } catch (err) {
      console.error("Failed to load delivery centers:", err);
      toast.error("Failed to load delivery centers");
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    const newErrors = {};
    if (!form.name?.trim()) newErrors.name = "Center name is required";
    if (!form.code?.trim()) newErrors.code = "Code is required";
    if (!form.location?.trim()) newErrors.location = "Location is required";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAdd = () => {
    setEditingId(null);
    setForm({
      name: '',
      code: '',
      location: '',
      contact_email: '',
      contact_phone: '',
      active: true
    });
    setShowForm(true);
  };

  const handleEdit = (center) => {
    setEditingId(center.id);
    setForm(center);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    try {
      if (editingId) {
        await apiRequest(`/delivery-centers/${editingId}`, {
          method: 'PUT',
          body: form
        });
        toast.success("Delivery center updated");
      } else {
        await apiRequest('/delivery-centers', {
          method: 'POST',
          body: form
        });
        toast.success("Delivery center created");
      }
      setShowForm(false);
      loadDeliveryCenters();
    } catch (err) {
      console.error("Failed to save delivery center:", err);
      toast.error(err.data?.detail || "Failed to save delivery center");
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Are you sure?")) return;

    try {
      await apiRequest(`/delivery-centers/${id}`, { method: 'DELETE' });
      toast.success("Delivery center deleted");
      loadDeliveryCenters();
    } catch (err) {
      console.error("Failed to delete delivery center:", err);
      toast.error("Failed to delete delivery center");
    }
  };

  return (
    <div className="space-y-6">
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

            {/* Code */}
            <div>
              <label className="block text-sm font-medium mb-1">Code *</label>
              <Input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="e.g., BNG"
                error={errors.code}
              />
              {errors.code && <p className="text-red-500 text-xs mt-1">{errors.code}</p>}
            </div>

            {/* Location */}
            <div>
              <label className="block text-sm font-medium mb-1">Location *</label>
              <Input
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                placeholder="e.g., Bangalore, India"
                error={errors.location}
              />
              {errors.location && <p className="text-red-500 text-xs mt-1">{errors.location}</p>}
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium mb-1">Contact Email</label>
              <Input
                type="email"
                value={form.contact_email || ''}
                onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                placeholder="center@company.com"
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium mb-1">Contact Phone</label>
              <Input
                value={form.contact_phone || ''}
                onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
                placeholder="+91 8000..."
              />
            </div>

            {/* Active */}
            <div>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm({ ...form, active: e.target.checked })}
                  className="w-4 h-4"
                />
                <span className="text-sm font-medium">Active</span>
              </label>
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
                    <span className="text-xs bg-gray-200 px-2 py-1 rounded">{center.code}</span>
                    {!center.active && <span className="text-xs bg-red-200 px-2 py-1 rounded">Inactive</span>}
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{center.location}</p>
                  {center.contact_email && (
                    <p className="text-sm text-gray-600">{center.contact_email}</p>
                  )}
                  {center.contact_phone && (
                    <p className="text-sm text-gray-600">{center.contact_phone}</p>
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
