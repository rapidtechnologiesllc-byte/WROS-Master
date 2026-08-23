import React, { useState, useEffect } from 'react';
import { X, AlertCircle } from 'lucide-react';
import { apiRequest } from '../services/api/client';

/**
 * Employee Onboarding Modal
 * Called from: Offer Screen (Convert Candidate to Employee)
 *
 * Purpose: Capture organizational details when creating an employee
 * - Position (org_node_id)
 * - Reporting Manager (reporting_manager_id, filtered by BU + position)
 * - Delivery Center (delivery_center_id, from DB)
 * - Business Unit (business_unit_id)
 * - User Link (email to link to existing login)
 */
export default function EmployeeOnboardingModal({
  isOpen,
  onClose,
  onSuccess,
  candidateId,
  candidateEmail,
  candidateName
}) {
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: candidateEmail || '',
    org_node_id: '',
    reporting_manager_id: '',
    delivery_center_id: '',
    business_unit_id: '',
    joining_date: new Date().toISOString().split('T')[0],
    employment_type: 'PERMANENT',
    work_location: 'ONSITE'
  });

  const [orgNodes, setOrgNodes] = useState([]);
  const [deliveryCenters, setDeliveryCenters] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  // Load data on mount
  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  // Filter employees for Reports To dropdown
  const getAvailableManagers = () => {
    if (!formData.business_unit_id || !formData.org_node_id) return [];

    // Get position level of selected org node
    const selectedPosition = orgNodes.find(n => n.id === formData.org_node_id);
    if (!selectedPosition) return [];

    // Filter to employees in same BU with higher position level
    return employees.filter(emp =>
      emp.business_unit_id === formData.business_unit_id &&
      emp.org_node_id && // Must have a position
      // Employee position must be higher (lower position_level number = higher in hierarchy)
      parseInt(emp.org_node_id) < parseInt(formData.org_node_id)
    );
  };

  const loadData = async () => {
    try {
      setLoading(true);

      // Load org nodes (position levels)
      const orgNodesRes = await apiRequest('/org-nodes');
      setOrgNodes(orgNodesRes.data || []);

      // Load delivery centers
      const centersRes = await apiRequest('/delivery-centers');
      setDeliveryCenters(centersRes.data || []);

      // Load business units
      const busRes = await apiRequest('/business-units');
      setBusinessUnits(busRes.data || []);

      // Load employees (for reporting manager dropdown)
      const empRes = await apiRequest('/employees');
      setEmployees(empRes.data || []);
    } catch (err) {
      console.error('Failed to load data:', err);
      setErrors({ load: 'Failed to load form data' });
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.first_name?.trim()) newErrors.first_name = 'First name is required';
    if (!formData.last_name?.trim()) newErrors.last_name = 'Last name is required';
    if (!formData.email?.trim()) newErrors.email = 'Email is required';
    if (!formData.org_node_id) newErrors.org_node_id = 'Position is required';
    if (!formData.delivery_center_id) newErrors.delivery_center_id = 'Delivery center is required';
    if (!formData.business_unit_id) newErrors.business_unit_id = 'Business unit is required';
    if (!formData.joining_date) newErrors.joining_date = 'Joining date is required';

    // Reporting manager required unless CEO level
    if (formData.org_node_id !== '1' && !formData.reporting_manager_id) {
      newErrors.reporting_manager_id = 'Reporting manager required (except for CEO level)';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) return;

    try {
      setSubmitting(true);

      // Prepare payload
      const payload = {
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        email: formData.email.trim(),
        org_node_id: formData.org_node_id,
        reporting_manager_id: formData.reporting_manager_id || null,
        delivery_center_id: formData.delivery_center_id,
        business_unit_id: formData.business_unit_id,
        joining_date: formData.joining_date,
        employment_type: formData.employment_type,
        work_location: formData.work_location
      };

      // Create employee
      const response = await apiRequest('/employees', {
        method: 'POST',
        body: payload
      });

      if (onSuccess) {
        onSuccess(response);
      }

      onClose();
    } catch (err) {
      console.error('Failed to create employee:', err);
      setErrors({
        submit: err.data?.detail || 'Failed to create employee'
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const availableManagers = getAvailableManagers();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Employee Onboarding</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Info note */}
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700 flex gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>Email MUST match existing user login account. Employee is linked to their user for authentication.</span>
        </div>

        {/* Error message */}
        {errors.submit && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            {errors.submit}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name fields */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                First Name *
              </label>
              <input
                type="text"
                value={formData.first_name}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                placeholder="John"
                className={`w-full px-3 py-2 border rounded-md text-sm ${
                  errors.first_name ? 'border-red-500 bg-red-50' : 'border-gray-300'
                }`}
              />
              {errors.first_name && <p className="text-xs text-red-600 mt-1">{errors.first_name}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Last Name *
              </label>
              <input
                type="text"
                value={formData.last_name}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                placeholder="Doe"
                className={`w-full px-3 py-2 border rounded-md text-sm ${
                  errors.last_name ? 'border-red-500 bg-red-50' : 'border-gray-300'
                }`}
              />
              {errors.last_name && <p className="text-xs text-red-600 mt-1">{errors.last_name}</p>}
            </div>
          </div>

          {/* Email - MUST match existing user login */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email (must match existing user login) *
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="john@example.com"
              className={`w-full px-3 py-2 border rounded-md text-sm ${
                errors.email ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
            />
            {errors.email && <p className="text-xs text-red-600 mt-1">{errors.email}</p>}
          </div>

          {/* Business Unit */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Business Unit *
            </label>
            <select
              value={formData.business_unit_id}
              onChange={(e) => {
                setFormData({
                  ...formData,
                  business_unit_id: e.target.value,
                  reporting_manager_id: '' // Reset manager when BU changes
                });
              }}
              className={`w-full px-3 py-2 border rounded-md text-sm ${
                errors.business_unit_id ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
            >
              <option value="">Select a business unit...</option>
              {businessUnits.map(bu => (
                <option key={bu.id} value={bu.id}>
                  {bu.bu_name || bu.name}
                </option>
              ))}
            </select>
            {errors.business_unit_id && <p className="text-xs text-red-600 mt-1">{errors.business_unit_id}</p>}
          </div>

          {/* Position */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Position *
            </label>
            <select
              value={formData.org_node_id}
              onChange={(e) => {
                setFormData({
                  ...formData,
                  org_node_id: e.target.value,
                  reporting_manager_id: '' // Reset manager when position changes
                });
              }}
              className={`w-full px-3 py-2 border rounded-md text-sm ${
                errors.org_node_id ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
            >
              <option value="">Select a position...</option>
              {orgNodes.map(node => (
                <option key={node.id} value={node.id}>
                  {node.name}
                </option>
              ))}
            </select>
            {errors.org_node_id && <p className="text-xs text-red-600 mt-1">{errors.org_node_id}</p>}
          </div>

          {/* Reporting Manager */}
          {formData.org_node_id !== '1' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reports To (Manager) *
              </label>
              <select
                value={formData.reporting_manager_id}
                onChange={(e) => setFormData({ ...formData, reporting_manager_id: e.target.value })}
                className={`w-full px-3 py-2 border rounded-md text-sm ${
                  errors.reporting_manager_id ? 'border-red-500 bg-red-50' : 'border-gray-300'
                }`}
              >
                <option value="">Select a manager...</option>
                {availableManagers.length === 0 ? (
                  <option disabled>No eligible managers in this BU</option>
                ) : (
                  availableManagers.map(emp => (
                    <option key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name} ({emp.org_node_id})
                    </option>
                  ))
                )}
              </select>
              {errors.reporting_manager_id && (
                <p className="text-xs text-red-600 mt-1">{errors.reporting_manager_id}</p>
              )}
              {availableManagers.length === 0 && formData.org_node_id && (
                <p className="text-xs text-orange-600 mt-1">
                  No managers available. Create higher-level position first.
                </p>
              )}
            </div>
          )}

          {/* Delivery Center */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Delivery Center (Office) *
            </label>
            <select
              value={formData.delivery_center_id}
              onChange={(e) => setFormData({ ...formData, delivery_center_id: e.target.value })}
              className={`w-full px-3 py-2 border rounded-md text-sm ${
                errors.delivery_center_id ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
            >
              <option value="">Select a delivery center...</option>
              {deliveryCenters.map(dc => (
                <option key={dc.id} value={dc.id}>
                  {dc.name} ({dc.code})
                </option>
              ))}
            </select>
            {errors.delivery_center_id && (
              <p className="text-xs text-red-600 mt-1">{errors.delivery_center_id}</p>
            )}
          </div>

          {/* Joining Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Joining Date *
            </label>
            <input
              type="date"
              value={formData.joining_date}
              onChange={(e) => setFormData({ ...formData, joining_date: e.target.value })}
              className={`w-full px-3 py-2 border rounded-md text-sm ${
                errors.joining_date ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
            />
            {errors.joining_date && <p className="text-xs text-red-600 mt-1">{errors.joining_date}</p>}
          </div>

          {/* Employment Type & Work Location */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Employment Type
              </label>
              <select
                value={formData.employment_type}
                onChange={(e) => setFormData({ ...formData, employment_type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="PERMANENT">Permanent</option>
                <option value="CONTRACT">Contract</option>
                <option value="FIXED_TERM">Fixed Term</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Work Location
              </label>
              <select
                value={formData.work_location}
                onChange={(e) => setFormData({ ...formData, work_location: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="ONSITE">Onsite</option>
                <option value="REMOTE">Remote</option>
                <option value="HYBRID">Hybrid</option>
              </select>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || loading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create Employee'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
