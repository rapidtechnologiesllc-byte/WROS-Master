import React, { useState, useEffect } from "react";
import { ChevronDown, Plus, Check, X, AlertCircle, CheckCircle } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import { apiRequest } from "../services/api/client";
import { getAllCandidates } from "../services/api/candidates";
import { listBusinessUnits } from "../services/api/rbac";
import { listRoleTemplates } from "../services/api/role_templates";
import { getHrMe } from "../services/api/users";
import { getBusinessUnitId } from "../utils/permissionsRoleTemplate";

export default function EmployeeConversionScreen() {
  const [candidates, setCandidates] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

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
      // (/candidates/all spells the pipeline key "pipline_status")
      const offerCandidates = candidatesList.filter(
        (c) =>
          c.status?.toUpperCase() === "OFFER" ||
          (c.pipeline_status || c.pipline_status)?.toUpperCase() === "OFFER" ||
          c.candidate_is_verified
      );
      setCandidates(offerCandidates);

      // Business units from the same source as Users & Access Control > Business Units
      const bus = await listBusinessUnits();
      setBusinessUnits(bus);

      // Default BU = the logged-in user's BU, only if it exists in the list
      const me = await getHrMe();
      const myBu = me?.business_unit_id;
      if (myBu != null && bus.some((b) => String(b.id) === String(myBu))) {
        setFormData((prev) =>
          prev.business_unit_id ? prev : { ...prev, business_unit_id: String(myBu) }
        );
      }

      // Roles = enabled role templates (Users & Access Control > Roles)
      const templates = await listRoleTemplates();
      setRoles(templates.filter((t) => t.enabled !== false));
    } catch (error) {
      console.error("Error loading conversion data:", error);
      setActionError("Failed to load conversion data");
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

  const handleRoleSelect = (roleId) => {
    setFormData((prev) => ({
      ...prev,
      role_ids: roleId ? [roleId] : [],
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
      setActionError("Please select a candidate");
      return false;
    }
    if (!formData.employee_name.trim()) {
      setActionError("Please enter employee name");
      return false;
    }
    if (!formData.employee_email.trim()) {
      setActionError("Please enter employee email");
      return false;
    }
    if (!formData.business_unit_id) {
      setActionError("Please select a business unit");
      return false;
    }
    if (formData.role_ids.length === 0) {
      setActionError("Please select a role");
      return false;
    }
    if (!formData.position.trim()) {
      setActionError("Please enter position/title");
      return false;
    }
    if (!formData.joining_date) {
      setActionError("Please enter joining date");
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      // Contract: EmployeeConversionRequest (backend/app/schemas/employee_conversion.py)
      const nameParts = formData.employee_name.trim().split(/\s+/);
      const payload = {
        candidate_id: formData.candidate_id,
        employee_email: formData.employee_email,
        first_name: nameParts[0],
        last_name: nameParts.slice(1).join(" ") || null,
        business_unit_id: parseInt(formData.business_unit_id, 10),
        role_ids: formData.role_ids.map((id) => parseInt(id, 10)),
        job_title: formData.position,
        joining_date: formData.joining_date,
      };

      const { data: result } = await apiRequest("/employees/convert-candidate", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (result?.status === "success") {
        setActionSuccess(
          `Employee created successfully! Employee ID: ${result.employee_id}`
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
        setActionError("Failed to convert candidate to employee");
      }
    } catch (error) {
      console.error("Conversion error:", error);
      setActionError(error?.message || "Failed to convert candidate");
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
        {actionError && (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 flex items-center justify-between">
            <span>{actionError}</span>
            <button onClick={() => setActionError(null)} className="text-rose-700 hover:text-rose-900">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
        {actionSuccess && (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 flex items-center justify-between">
            <span>{actionSuccess}</span>
            <button onClick={() => setActionSuccess(null)} className="text-emerald-700 hover:text-emerald-900">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Candidate Selection */}
          <div className="border-b pb-6">
            <h2 className="text-lg font-semibold mb-4">1. Select Candidate</h2>
            <Select
              label="Candidate"
              value={formData.candidate_id}
              onChange={(value) => handleCandidateSelect(value)}
              disabled={submitting}
              options={[
                { value: "", label: "Select a candidate" },
                ...candidates.map((c) => ({
                  value: String(c.candidate_id || c.id),
                  label: `${c.candidate_name || c.name} (${c.candidate_email || c.email})`,
                })),
              ]}
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
                options={[
                  { value: "", label: "Select a business unit" },
                  ...businessUnits.map((bu) => ({
                    value: String(bu.id),
                    label: bu.bu_name || bu.name || `BU ${bu.id}`,
                  })),
                ]}
              />

              {/* One role template per user (Users.role_template_id) */}
              <Select
                label="Role"
                value={formData.role_ids[0] != null ? String(formData.role_ids[0]) : ""}
                onChange={(value) => handleRoleSelect(value)}
                disabled={submitting}
                options={[
                  { value: "", label: roles.length ? "Select a role" : "No roles available" },
                  ...roles.map((role) => ({
                    value: String(role.id),
                    label: role.display_name || role.name,
                  })),
                ]}
              />
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
