// S-251 (Allocate Employee to Project) + S-252 (Allocation Conflict
// Detection -- the 409 from over-100% concurrent utilization is the
// existing allocate_employee_to_project() gate, surfaced here, not a
// second implementation).
import { useEffect, useState } from "react";
import { Briefcase, RefreshCw, LogOut } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import cx from "../utils/cx";
import { createAllocation, getAllocations, endAllocation } from "../services/api/allocations";

export default function AllocationsScreen() {
  const [employeeId, setEmployeeId] = useState("");
  const [demandId, setDemandId] = useState("");
  const [utilizationPct, setUtilizationPct] = useState("100");
  const [allowConcurrent, setAllowConcurrent] = useState(false);
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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

  const handleCreate = async () => {
    if (!employeeId.trim() || !demandId.trim()) {
      setError("Employee ID and Demand ID are both required.");
      return;
    }
    setError("");
    setNotice("");
    try {
      await createAllocation({
        employeeId: employeeId.trim(),
        demandId: demandId.trim(),
        utilizationPct: utilizationPct ? Number(utilizationPct) : undefined,
        allowConcurrent,
      });
      setNotice("Employee allocated.");
      setDemandId("");
      await load();
    } catch (err) {
      setError(err.message || "Allocation blocked.");
    }
  };

  const handleEnd = async (allocationId) => {
    setError("");
    try {
      await endAllocation(allocationId);
      await load();
    } catch (err) {
      setError(err.message || "Failed to end allocation.");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Employee Allocations"
        subtitle="Allocate a bench employee to a demand. Concurrent allocations over 100% utilization are blocked -- same gate as the write path everywhere else in this app."
        icon={<Briefcase className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-3">
          <Input label="Employee ID" value={employeeId} onChange={setEmployeeId} placeholder="employee UUID" />
          <Input label="Demand ID" value={demandId} onChange={setDemandId} placeholder="demand UUID" />
          <Input label="Utilization %" value={utilizationPct} onChange={setUtilizationPct} placeholder="100" />
        </div>
        <label className="mt-3 flex items-center gap-2 text-xs text-gray-700">
          <input
            type="checkbox"
            checked={allowConcurrent}
            onChange={(e) => setAllowConcurrent(e.target.checked)}
          />
          Allow concurrent (multiple active allocations at once)
        </label>
        <div className="mt-3">
          <Button variant="primary" onClick={handleCreate}>
            Allocate
          </Button>
        </div>

        <div className="mt-5 overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Employee / Demand</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Status</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Utilization</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-500">Loading…</td>
                </tr>
              ) : allocations.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-500">No allocations yet.</td>
                </tr>
              ) : (
                allocations.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900">
                      <div className="font-semibold">{a.employee_name}</div>
                      <div className="text-xs text-gray-500">→ {a.demand_job_title}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">{a.status}</td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {a.utilization_pct != null ? `${a.utilization_pct}%` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {a.status === "ACTIVE" ? (
                        <Button variant="secondary" onClick={() => handleEnd(a.id)}>
                          <LogOut className="h-4 w-4" /> End
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
      </Card>
    </div>
  );
}
