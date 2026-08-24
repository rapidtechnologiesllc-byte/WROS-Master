import React, { useState, useEffect } from 'react';

const BusinessUnitModal = ({ isOpen, onClose, onSuccess, mode = 'create', bu = null }) => {
  const [formData, setFormData] = useState({
    name: '',
    display_name: '',
    description: '',
    bu_code: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;

    if (mode === 'edit' && bu) {
      setFormData({
        name: bu.name || '',
        display_name: bu.display_name || '',
        description: bu.description || '',
        bu_code: bu.bu_code || ''
      });
    } else {
      setFormData({
        name: '',
        display_name: '',
        description: '',
        bu_code: ''
      });
    }
    setError(null);
  }, [isOpen, mode, bu]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
      ...(name === 'name' && { bu_code: value.toUpperCase().replace(/\s+/g, '') })
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
      if (!formData.display_name?.trim()) {
        setError('Display name is required');
        setLoading(false);
        return;
      }

      const token = localStorage.getItem('hrms_token');
      const endpoint = mode === 'create'
        ? 'http://localhost:8080/api/admin/users-access-control/business-units'
        : `http://localhost:8080/api/admin/users-access-control/business-units/${bu.id}`;
      const method = mode === 'create' ? 'POST' : 'PUT';

      const payload = {
        name: formData.name,
        display_name: formData.display_name,
        description: formData.description || '',
        bu_code: formData.bu_code
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
        setError(data.detail || 'Failed to save business unit');
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
              {mode === 'create' ? 'Create Business Unit' : 'Edit Business Unit'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {mode === 'create' ? 'Add a new business unit' : 'Update business unit details'}
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
            <h3 className="font-medium text-gray-900">Business Unit Details</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Name *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                placeholder="e.g., North America"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Display Name *</label>
              <input
                type="text"
                name="display_name"
                value={formData.display_name}
                onChange={handleInputChange}
                placeholder="e.g., North America (NA)"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Code</label>
              <input
                type="text"
                name="bu_code"
                value={formData.bu_code}
                onChange={handleInputChange}
                placeholder="Auto-generated from name"
                className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                readOnly
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                placeholder="Describe this business unit"
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
              className="px-4 py-2 text-sm font-medium text-white bg-bx-orange rounded-xl hover:bg-bx-orange-hover disabled:bg-gray-400"
            >
              {loading ? 'Saving...' : mode === 'create' ? 'Create' : 'Update'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default BusinessUnitModal;
