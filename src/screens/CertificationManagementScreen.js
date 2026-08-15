// Admin screen for managing certifications and employee KPI targets
import { useEffect, useState } from "react";
import { Plus, Trash2, CheckCircle2, Clock, AlertCircle } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import { toast } from "react-toastify";

const CERT_LEVELS = ["Foundation", "Intermediate", "Advanced", "Expert"];

export default function CertificationManagementScreen() {
  const [activeTab, setActiveTab] = useState("certifications"); // certifications | targets
  const [certifications, setCertifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreateCert, setShowCreateCert] = useState(false);

  // Create certification form
  const [certForm, setCertForm] = useState({
    cert_name: "",
    cert_code: "",
    description: "",
    level: "Foundation",
    validity_months: 24,
    is_core_certification: false,
  });

  // Assign target form
  const [showAssignTarget, setShowAssignTarget] = useState(false);
  const [targetForm, setTargetForm] = useState({
    employee_id: "",
    certification_id: "",
    target_date: "",
    weight: 0.1,
  });
  const [employees, setEmployees] = useState([]);
  const [kpiTargets, setKPITargets] = useState([]);

  // Load data
  useEffect(() => {
    loadCertifications();
  }, []);

  useEffect(() => {
    if (activeTab === "targets") {
      loadKPITargets();
      loadEmployees();
    }
  }, [activeTab]);

  const loadCertifications = async () => {
    setLoading(true);
    try {
      const response = await fetch("/admin/certifications/list", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (!response.ok) throw new Error("Failed to load certifications");
      const data = await response.json();
      setCertifications(data);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadEmployees = async () => {
    try {
      const { getAllEmployees } = await import("../services/api/employees");
      const data = await getAllEmployees();
      setEmployees(data || []);
    } catch (err) {
      console.error("Failed to load employees:", err);
    }
  };

  const loadKPITargets = async () => {
    setLoading(true);
    try {
      // Will load all targets via admin endpoint
      // For now, show empty state
      setKPITargets([]);
    } catch (err) {
      console.error("Failed to load targets:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCertification = async () => {
    if (!certForm.cert_name || !certForm.cert_code) {
      toast.error("Name and Code are required");
      return;
    }

    try {
      const response = await fetch("/admin/certifications/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(certForm),
      });

      if (!response.ok) throw new Error("Failed to create certification");

      toast.success("Certification created successfully");
      setCertForm({
        cert_name: "",
        cert_code: "",
        description: "",
        level: "Foundation",
        validity_months: 24,
        is_core_certification: false,
      });
      setShowCreateCert(false);
      loadCertifications();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleAssignTarget = async () => {
    if (!targetForm.employee_id || !targetForm.certification_id || !targetForm.target_date) {
      toast.error("All fields are required");
      return;
    }

    try {
      const response = await fetch("/admin/certifications/assign-target", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          ...targetForm,
          weight: parseFloat(targetForm.weight),
        }),
      });

      if (!response.ok) throw new Error("Failed to assign target");

      toast.success("KPI target assigned successfully");
      setTargetForm({
        employee_id: "",
        certification_id: "",
        target_date: "",
        weight: 0.1,
      });
      setShowAssignTarget(false);
      loadKPITargets();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab("certifications")}
          className={`px-4 py-2 font-medium ${activeTab === "certifications" ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-600"}`}
        >
          📚 Certifications
        </button>
        <button
          onClick={() => setActiveTab("targets")}
          className={`px-4 py-2 font-medium ${activeTab === "targets" ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-600"}`}
        >
          🎯 KPI Targets
        </button>
      </div>

      {/* Certifications Tab */}
      {activeTab === "certifications" && (
        <Card className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Certification Master</h2>
            <Button variant="primary" onClick={() => setShowCreateCert(!showCreateCert)}>
              <Plus className="h-4 w-4 mr-2" /> Add Certification
            </Button>
          </div>

          {showCreateCert && (
            <div className="border p-4 rounded-lg space-y-3 bg-blue-50">
              <div>
                <label className="block text-sm font-medium mb-1">Certification Name</label>
                <input
                  type="text"
                  placeholder="e.g., Guidewire Core Certification"
                  value={certForm.cert_name}
                  onChange={(e) => setCertForm({ ...certForm, cert_name: e.target?.value || "" })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Certification Code</label>
                <input
                  type="text"
                  placeholder="e.g., GW-CORE"
                  value={certForm.cert_code}
                  onChange={(e) => setCertForm({ ...certForm, cert_code: e.target?.value || "" })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <input
                  type="text"
                  placeholder="Brief description"
                  value={certForm.description}
                  onChange={(e) => setCertForm({ ...certForm, description: e.target?.value || "" })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Level</label>
                <select
                  value={certForm.level}
                  onChange={(e) => setCertForm({ ...certForm, level: e.target?.value || "Foundation" })}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  {CERT_LEVELS.map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Validity (months)</label>
                <input
                  type="number"
                  value={certForm.validity_months}
                  onChange={(e) => setCertForm({ ...certForm, validity_months: parseInt(e.target?.value || "24") })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={certForm.is_core_certification}
                  onChange={(e) => setCertForm({ ...certForm, is_core_certification: e.target?.checked || false })}
                />
                <span>Core Certification</span>
              </label>
              <div className="flex gap-2">
                <Button variant="primary" onClick={handleCreateCertification}>
                  Create
                </Button>
                <Button variant="ghost" onClick={() => setShowCreateCert(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          <div className="grid gap-2">
            {loading ? (
              <div className="text-center text-gray-500 py-8">Loading...</div>
            ) : certifications.length === 0 ? (
              <div className="text-center text-gray-500 py-8">No certifications yet</div>
            ) : (
              certifications.map((cert) => (
                <div key={cert.id} className="border rounded-lg p-3 flex justify-between items-start">
                  <div>
                    <div className="font-semibold">{cert.cert_name}</div>
                    <div className="text-sm text-gray-600">{cert.cert_code}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      Level: {cert.level} • Validity: {cert.validity_months || 24} months
                      {cert.is_core_certification && " • Core Certification"}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm">
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" className="text-red-600">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      )}

      {/* KPI Targets Tab */}
      {activeTab === "targets" && (
        <Card className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Employee KPI Targets</h2>
            <Button variant="primary" onClick={() => setShowAssignTarget(!showAssignTarget)}>
              <Plus className="h-4 w-4 mr-2" /> Assign Target
            </Button>
          </div>

          {showAssignTarget && (
            <div className="border p-4 rounded-lg space-y-3 bg-green-50">
              <div>
                <label className="block text-sm font-medium mb-1">Employee</label>
                <select
                  value={targetForm.employee_id}
                  onChange={(e) => setTargetForm({ ...targetForm, employee_id: e.target?.value || "" })}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="">Select employee</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Certification</label>
                <select
                  value={targetForm.certification_id}
                  onChange={(e) => setTargetForm({ ...targetForm, certification_id: e.target?.value || "" })}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="">Select certification</option>
                  {certifications.map((cert) => (
                    <option key={cert.id} value={cert.id}>
                      {cert.cert_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Target Date</label>
                <input
                  type="date"
                  value={targetForm.target_date}
                  onChange={(e) => setTargetForm({ ...targetForm, target_date: e.target?.value || "" })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Weight (0.0-1.0)</label>
                <input
                  type="number"
                  value={targetForm.weight}
                  step="0.1"
                  onChange={(e) => setTargetForm({ ...targetForm, weight: e.target?.value || "0.1" })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div className="flex gap-2">
                <Button variant="primary" onClick={handleAssignTarget}>
                  Assign
                </Button>
                <Button variant="ghost" onClick={() => setShowAssignTarget(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          <div className="grid gap-2">
            {loading ? (
              <div className="text-center text-gray-500 py-8">Loading...</div>
            ) : kpiTargets.length === 0 ? (
              <div className="text-center text-gray-500 py-8">No KPI targets assigned yet</div>
            ) : (
              kpiTargets.map((target) => (
                <div key={target.id} className="border rounded-lg p-3">
                  <div className="font-semibold">{target.certification_id}</div>
                  <div className="text-sm text-gray-600">Employee: {target.employee_id}</div>
                  <div className="text-sm text-gray-600">Target: {new Date(target.target_date).toLocaleDateString()}</div>
                  <div className="flex items-center gap-2 mt-2">
                    {target.is_achieved ? (
                      <>
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                        <span className="text-green-600 font-medium">Achieved</span>
                      </>
                    ) : (
                      <>
                        <Clock className="h-5 w-5 text-blue-600" />
                        <span className="text-blue-600 font-medium">Pending</span>
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
