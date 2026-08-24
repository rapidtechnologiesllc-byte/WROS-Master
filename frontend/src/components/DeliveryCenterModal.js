import React, { useState, useEffect } from 'react';

const DeliveryCenterModal = ({ isOpen, onClose, onSuccess, mode = 'create', dc = null }) => {
  const [formData, setFormData] = useState({
    name: '',
    dc_code: '',
    location_city: '',
    location_country: '',
    description: '',
    delivery_center_type: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;

    if (mode === 'edit' && dc) {
      setFormData({
        name: dc.name || '',
        dc_code: dc.dc_code || '',
        location_city: dc.location_city || '',
        location_country: dc.location_country || '',
        description: dc.description || '',
        delivery_center_type: dc.delivery_center_type || ''
      });
    } else {
      setFormData({
        name: '',
        dc_code: '',
        location_city: '',
        location_country: '',
        description: '',
        delivery_center_type: ''
      });
    }
    setError(null);
  }, [isOpen, mode, dc]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
      ...(name === 'name' && { dc_code: value.toUpperCase().replace(/\s+/g, '') })
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (!formData.name?.trim()) {
        setError('Name is required');
        setLoading(false);
        return;
      }
      if (!formData.location_city?.trim()) {
        setError('City is required');
        setLoading(false);
        return;
      }
      if (!formData.location_country?.trim()) {
        setError('Country is required');
        setLoading(false);
        return;
      }

      const token = localStorage.getItem('hrms_token');
      const endpoint = mode === 'create'
        ? 'http://localhost:8080/api/admin/users-access-control/delivery-centers'
        : `http://localhost:8080/api/admin/users-access-control/delivery-centers/${dc.id}`;
      const method = mode === 'create' ? 'POST' : 'PUT';

      const payload = {
        name: formData.name,
        dc_code: formData.dc_code,
        location_city: formData.location_city,
        location_country: formData.location_country,
        description: formData.description || '',
        delivery_center_type: formData.delivery_center_type || ''
      };

      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || 'Failed to save delivery center');
        setLoading(false);
        return;
      }

      setLoading(false);
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || 'An error occurred');
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {mode === 'create' ? 'Create Delivery Center' : 'Edit Delivery Center'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {mode === 'create' ? 'Add a new delivery center' : 'Update delivery center details'}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Basic Information</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Name *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                placeholder="e.g., New York Center"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Code</label>
              <input
                type="text"
                name="dc_code"
                value={formData.dc_code}
                onChange={handleInputChange}
                placeholder="Auto-generated from name"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                readOnly
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Type</label>
              <input
                type="text"
                name="delivery_center_type"
                value={formData.delivery_center_type}
                onChange={handleInputChange}
                placeholder="e.g., Regional, Global, Local"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Location</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">City *</label>
              <input
                type="text"
                name="location_city"
                value={formData.location_city}
                onChange={handleInputChange}
                placeholder="e.g., New York"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Country *</label>
              <input
                type="text"
                name="location_country"
                value={formData.location_country}
                onChange={handleInputChange}
                placeholder="e.g., United States"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                placeholder="Describe this delivery center"
                rows="3"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="flex gap-3 justify-end pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 disabled:bg-gray-400"
            >
              {loading ? 'Saving...' : mode === 'create' ? 'Create' : 'Update'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DeliveryCenterModal;
