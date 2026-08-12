// S-251 (Allocate Employee to Project) + S-252 (Allocation Conflict
// Detection -- the 409 from over-100% concurrent utilization is the
// existing allocate_employee_to_project() gate, surfaced here, not a
// second implementation).
// REDESIGNED 2026-08-12: Professional table view with filtering, sorting,
// and secondary allocation form modal (DEFECT-2026-08-12T5).
import { useEffect, useState } from "react";
import { Briefcase, RefreshCw, LogOut, Plus, Download } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import cx from "../utils/cx";
import { createAllocation, getAllocations, endAllocation, getAllocationDropdowns } from "../services/api/allocations";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const formatDate = (d) => d ? new Date(d).toLocaleDateString() : "—";

function AllocationForm({ onCancel, onSaved }) {
  const [employeeId, setEmployeeId] = useState("");
  const [demandId, setDemandId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [utilizationPct, setUtilizationPct] = useState("100");
  const [allowConcurrent, setAllowConcurrent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [employees, setEmployees] = useState([]);
  const [demands, setDemands] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getAllocationDropdowns();
        setEmployees((data?.employees || []).map((e) => ({ value: e.id, label: e.name })));
        setDemands((data?.demands || []).map((d) => ({ value: d.id, label: d.name })));
      } catch (err) {
        console.error("Failed to load dropdown data:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    if (!employeeId || !demandId) {
      setError("Employee and Demand are both required.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      await createAllocation({
        employeeId,
        demandId,
        projectId: projectId.trim() || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        utilizationPct: utilizationPct ? Number(utilizationPct) : undefined,
        allowConcurrent,
      });
      onSaved();
    } catch (err) {
      setError(err.message || "Allocation blocked.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mb-6 rounded-2xl border border-gray-200 bg-gray-50 p-4">
        <div className="py-4 text-center text-sm text-gray-500">Loading form...</div>
      </div>
    );
  }

  return (
    <div className="mb-6 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-4 text-sm font-semibold text-gray-900">Add Allocation</div>
      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-6">
        <Select
          label="Employee"
          value={employeeId}
          onChange={setEmployeeId}
          options={employees}
          placeholder="Select employee"
        />
        <Select
          label="Demand"
          value={demandId}
          onChange={setDemandId}
          options={demands}
          placeholder="Select demand"
        />
        <Input
          label="Start Date"
          type="date"
          value={startDate}
          onChange={setStartDate}
        />
        <Input
          label="End Date"
          type="date"
          value={endDate}
          onChange={setEndDate}
        />
        <Input
          label="Utilization %"
          type="number"
          value={utilizationPct}
          onChange={setUtilizationPct}
          placeholder="100"
        />
        <Input
          label="Project ID (optional)"
          type="text"
          value={projectId}
          onChange={setProjectId}
          placeholder="optional"
        />
      </div>
      <label className="mt-3 flex items-center gap-2 text-xs text-gray-700">
        <input
          type="checkbox"
          checked={allowConcurrent}
          onChange={(e) => setAllowConcurrent(e.target.checked)}
        />
        Allow concurrent (multiple active allocations at once)
      </label>
      <div className="mt-4 flex gap-2">
        <Button variant="primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save Allocation"}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export default function AllocationsScreen() {
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [endingId, setEndingId] = useState(null);

  // Filters & Sorting
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [clientFilter, setClientFilter] = useState("");
  const [sortBy, setSortBy] = useState("created_at_desc");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getAllocations();
      setAllocations(res?.allocations || []);
    } catch (err) {
      setError(err.message || "Failed to load allocations.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleFormSaved = () => {
    setShowForm(false);
    load();
  };

  const handleEnd = async (allocationId) => {
    setError("");
    setEndingId(allocationId);
    try {
      await endAllocation(allocationId);
      setNotice("Allocation ended.");
      await load();
    } catch (err) {
      setError(err.message || "Failed to end allocation.");
    } finally {
      setEndingId(null);
    }
  };

  const handleExport = () => {
    if (filtered.length === 0) return;
    const headers = ["Employee", "Job Title", "Client", "Status", "Utilization", "Bill Rate", "Start Date", "End Date"];
    const rows = filtered.map((a) => [
      a.employee_name,
      a.demand_job_title,
      a.client_name,
      a.status,
      a.utilization_pct ? `${a.utilization_pct}%` : "—",
      formatUsdCents(a.billing_rate_usd_cents),
      formatDate(a.start_date),
      formatDate(a.end_date),
    ]);
    const csv = [headers, ...rows].map((r) => r.map((v) => `"${v}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "allocations.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  // Apply filters & sorting
  let filtered = allocations;

  if (statusFilter !== "ALL") {
    filtered = filtered.filter((a) => a.status === statusFilter);
  }
  if (clientFilter.trim()) {
    const q = clientFilter.toLowerCase();
    filtered = filtered.filter((a) => a.client_name?.toLowerCase().includes(q));
  }

  // Sort
  if (sortBy === "created_at_desc") {
    filtered = [...filtered].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  } else if (sortBy === "employee_name") {
    filtered = [...filtered].sort((a, b) => (a.employee_name || "").localeCompare(b.employee_name || ""));
  } else if (sortBy === "bill_rate_desc") {
    filtered = [...filtered].sort((a, b) => (b.billing_rate_usd_cents || 0) - (a.billing_rate_usd_cents || 0));
  }

  const clientOptions = [...new Set(allocations.map((a) => a.client_name).filter(Boolean))].map((c) => ({
    value: c,
    label: c,
  }));

  return (
    <div className="space-y-4 p-6">
      <Card
        title="Employee Allocations"
        subtitle="Allocate bench employees to demands and projects. Concurrent allocations over 100% utilization are blocked."
        icon={<Briefcase className="h-4 w-4" />}
        right={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={load} disabled={loading}>
              <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} />
            </Button>
            <Button variant="primary" onClick={() => setShowForm(!showForm)}>
              <Plus className="h-4 w-4" /> Add Allocation
            </Button>
          </div>
        }
      >
        {error && (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}
        {notice && (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </div>
        )}

        {showForm && (
          <AllocationForm
            onCancel={() => setShowForm(false)}
            onSaved={handleFormSaved}
          />
        )}

        {/* Filters & Export */}
        <div className="mb-4 grid gap-3 sm:grid-cols-4">
          <Select
            label="Status"
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: "ALL", label: "All Statuses" },
              { value: "ACTIVE", label: "Active" },
              { value: "ENDED", label: "Ended" },
              { value: "CORE_PULLED", label: "Core Pulled" },
            ]}
          />
          <Select
            label="Client"
            value={clientFilter}
            onChange={setClientFilter}
            options={clientOptions}
            placeholder="Filter by client"
          />
          <Select
            label="Sort By"
            value={sortBy}
            onChange={setSortBy}
            options={[
              { value: "created_at_desc", label: "Newest First" },
              { value: "employee_name", label: "Employee Name" },
              { value: "bill_rate_desc", label: "Bill Rate (High→Low)" },
            ]}
          />
          <Button variant="secondary" onClick={handleExport} disabled={filtered.length === 0}>
            <Download className="h-4 w-4" /> Export CSV
          </Button>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Employee</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Job Title</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Client</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Bill Rate</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Utilization</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Status</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Start Date</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">End Date</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Business Unit</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-sm text-gray-500">
                    Loading…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-sm text-gray-500">
                    {allocations.length === 0 ? "No allocations yet." : "No allocations match your filters."}
                  </td>
                </tr>
              ) : (
                filtered.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900 font-medium">{a.employee_name}</td>
                    <td className="px-4 py-3 text-gray-700">{a.demand_job_title}</td>
                    <td className="px-4 py-3 text-gray-700">{a.client_name}</td>
                    <td className="px-4 py-3 text-gray-700">{formatUsdCents(a.billing_rate_usd_cents)}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {a.utilization_pct ? `${a.utilization_pct}%` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={cx(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
                        a.status === "ACTIVE" ? "bg-emerald-100 text-emerald-800" :
                        a.status === "ENDED" ? "bg-gray-100 text-gray-800" :
                        "bg-amber-100 text-amber-800"
                      )}>
                        {a.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{formatDate(a.start_date)}</td>
                    <td className="px-4 py-3 text-gray-700">{formatDate(a.end_date)}</td>
                    <td className="px-4 py-3 text-gray-700 text-xs">{a.business_unit_name || "—"}</td>
                    <td className="px-4 py-3">
                      {a.status === "ACTIVE" ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleEnd(a.id)}
                          disabled={endingId === a.id}
                        >
                          <LogOut className="h-3 w-3" /> {endingId === a.id ? "…" : "End"}
                        </Button>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Summary */}
        {filtered.length > 0 && (
          <div className="mt-4 text-xs text-gray-600">
            Showing {filtered.length} of {allocations.length} allocation{allocations.length !== 1 ? "s" : ""}
          </div>
        )}
      </Card>
    </div>
  );
}
