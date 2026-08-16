import React, { useState, useEffect } from "react";
import { ChevronDown, Plus, Check, X } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import { toast } from "react-toastify";
import { apiRequest } from "../services/api/client";
import { getAllCandidates } from "../services/api/candidates";
import { getBusinessUnitId } from "../utils/permissions";

export default function EmployeeConversionScreen() {
  const [candidates, setCandidates] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [formData, setFormData] = useState({
    candidate_id: "",
    employee_name: "",
    employee_email: "",
    business_unit_id: getBusinessUnitId() || "",
    role_ids: [],
    position: "",
    joining_date: "",
  });

  const [selectedCandidate, setSelectedCandidate] = useState(null);

  // Load initial data
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      // Load candidates
      const candidatesRes = await getAllCandidates();
      const candidatesList = Array.isArray(candidatesRes)
        ? candidatesRes
        : candidatesRes?.candidates || [];

      // Filter to only OFFER status candidates who are ready for conversion
      const offerCandidates = candidatesList.filter(
        (c) =>
          c.status?.toUpperCase() === "OFFER" ||
          c.pipeline_status?.toUpperCase() === "OFFER" ||
          c.candidate_is_verified
      );
      setCandidates(offerCandidates);

      // Load business units
      const busRes = await apiRequest("/business-units");
      setBusinessUnits(Array.isArray(busRes) ? busRes : busRes?.data || []);

      // Load roles for conversion
      const rolesRes = await apiRequest("/employees/roles-for-conversion");
      setRoles(Array.isArray(rolesRes) ? rolesRes : rolesRes?.roles || []);
    } catch (error) {
      console.error("Error loading conversion data:", error);
      toast.error("Failed to load conversion data");
    } finally {
      setLoading(false);
    }
  };

  const handleCandidateSelect = (candidateId) => {
    const candidate = candidates.find(
      (c) => String(c.candidate_id || c.id) === String(candidateId)
    );
    if (candidate) {
      setSelectedCandidate(candidate);
      setFormData((prev) => ({
        ...prev,
        candidate_id: candidateId,
        employee_name:
          candidate.candidate_name || candidate.name || prev.employee_name,
        employee_email:
          candidate.candidate_email || candidate.email || prev.employee_email,
      }));
    }
  };

  const handleRoleToggle = (roleId) => {
    setFormData((prev) => ({
      ...prev,
      role_ids: prev.role_ids.includes(roleId)
        ? prev.role_ids.filter((id) => id !== roleId)
        : [...prev.role_ids, roleId],
    }));
  };

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const validateForm = () => {
    if (!formData.candidate_id.trim()) {
      toast.error("Please select a candidate");
      return false;
    }
    if (!formData.employee_name.trim()) {
      toast.error("Please enter employee name");
      return false;
    }
    if (!formData.employee_email.trim()) {
      toast.error("Please enter employee email");
      return false;
    }
    if (!formData.business_unit_id) {
      toast.error("Please select a business unit");
      return false;
    }
    if (formData.role_ids.length === 0) {
      toast.error("Please select at least one role");
      return false;
    }
    if (!formData.position.trim()) {
      toast.error("Please enter position/title");
      return false;
    }
    if (!formData.joining_date) {
      toast.error("Please enter joining date");
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      const payload = {
        candidate_id: formData.candidate_id,
        employee_name: formData.employee_name,
        employee_email: formData.employee_email,
        business_unit_id: parseInt(formData.business_unit_id, 10),
        role_ids: formData.role_ids.map((id) => parseInt(id, 10)),
        position: formData.position,
        joining_date: formData.joining_date,
      };

      const result = await apiRequest(
        "/employees/convert-from-candidate",
        "POST",
        payload
      );

      if (result?.status === "success" || result?.employee_user_id) {
        toast.success(
          `Employee created successfully! ID: ${result.employee_user_id}`
        );
        // Reset form
        setFormData({
          candidate_id: "",
          employee_name: "",
          employee_email: "",
          business_unit_id: getBusinessUnitId() || "",
          role_ids: [],
          position: "",
          joining_date: "",
        });
        setSelectedCandidate(null);
        // Reload candidates
        loadInitialData();
      } else {
        toast.error("Failed to convert candidate to employee");
      }
    } catch (error) {
      console.error("Conversion error:", error);
      toast.error(error?.message || "Failed to convert candidate");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-600">Loading conversion data...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">
          Convert Candidate to Employee
        </h1>
        <p className="mt-1 text-gray-600">
          Convert a candidate in OFFER status to an active employee with role
          and business unit assignment
        </p>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Candidate Selection */}
          <div className="border-b pb-6">
            <h2 className="text-lg font-semibold mb-4">1. Select Candidate</h2>
            <Select
              label="Candidate"
              value={formData.candidate_id}
              onChange={(value) => handleCandidateSelect(value)}
              disabled={submitting}
              options={candidates.map((c) => ({
                value: String(c.candidate_id || c.id),
                label: `${c.candidate_name || c.name} (${c.candidate_email || c.email})`,
              }))}
            />
            {selectedCandidate && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-gray-600">
                  <strong>Status:</strong>{" "}
                  {selectedCandidate.status ||
                    selectedCandidate.pipeline_status ||
                    "Verified"}
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  <strong>Phone:</strong>{" "}
                  {selectedCandidate.candidate_mobile ||
                    selectedCandidate.phone ||
                    "N/A"}
                </p>
              </div>
            )}
          </div>

          {/* Employee Details */}
          <div className="border-b pb-6">
            <h2 className="text-lg font-semibold mb-4">2. Employee Details</h2>
            <div className="space-y-4">
              <Input
                label="Employee Name"
                value={formData.employee_name}
                onChange={(value) =>
                  handleInputChange("employee_name", value)
                }
                disabled={submitting}
                required
              />
              <Input
                label="Employee Email"
                type="email"
                value={formData.employee_email}
                onChange={(value) =>
                  handleInputChange("employee_email", value)
                }
                disabled={submitting}
                required
              />
              <Input
                label="Position/Job Title"
                value={formData.position}
                onChange={(value) => handleInputChange("position", value)}
                disabled={submitting}
                required
              />
              <Input
                label="Joining Date"
                type="date"
                value={formData.joining_date}
                onChange={(value) =>
                  handleInputChange("joining_date", value)
                }
                disabled={submitting}
                required
              />
            </div>
          </div>

          {/* Business Unit & Roles */}
          <div className="border-b pb-6">
            <h2 className="text-lg font-semibold mb-4">
              3. Business Unit & Roles
            </h2>
            <div className="space-y-4">
              <Select
                label="Business Unit"
                value={formData.business_unit_id}
                onChange={(value) =>
                  handleInputChange("business_unit_id", value)
                }
                disabled={submitting}
                options={businessUnits.map((bu) => ({
                  value: String(bu.id),
                  label: bu.bu_name || bu.name || `BU ${bu.id}`,
                }))}
                required
              />

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-3">
                  Assign Roles (select one or more)
                </label>
                <div className="space-y-2">
                  {roles.length === 0 ? (
                    <p className="text-sm text-gray-500">
                      No roles available for assignment
                    </p>
                  ) : (
                    roles.map((role) => (
                      <label
                        key={role.id}
                        className="flex items-center p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={formData.role_ids.includes(role.id)}
                          onChange={() => handleRoleToggle(role.id)}
                          disabled={submitting}
                          className="w-4 h-4 text-blue-600 rounded"
                        />
                        <div className="ml-3">
                          <p className="font-medium text-gray-900">
                            {role.name}
                          </p>
                          {role.description && (
                            <p className="text-xs text-gray-500">
                              {role.description}
                            </p>
                          )}
                        </div>
                      </label>
                    ))
                  )}
                </div>
                {formData.role_ids.length > 0 && (
                  <div className="mt-3 p-3 bg-green-50 rounded border border-green-200">
                    <p className="text-sm text-green-800">
                      <strong>Selected roles:</strong>{" "}
                      {roles
                        .filter((r) => formData.role_ids.includes(r.id))
                        .map((r) => r.name)
                        .join(", ")}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white"
            >
              <Check className="w-4 h-4" />
              {submitting ? "Converting..." : "Convert to Employee"}
            </Button>
            <Button
              type="button"
              onClick={() => {
                setFormData({
                  candidate_id: "",
                  employee_name: "",
                  employee_email: "",
                  business_unit_id: getBusinessUnitId() || "",
                  role_ids: [],
                  position: "",
                  joining_date: "",
                });
                setSelectedCandidate(null);
              }}
              disabled={submitting}
              className="flex items-center gap-2 bg-gray-300 hover:bg-gray-400 text-gray-900"
            >
              <X className="w-4 h-4" />
              Clear
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
