// One employee's live allocations (active + awaiting margin approval): project link, client job,
// state, and Add / Extend-Edit / End. Ending needs allocations.create, as the end endpoint checks.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { Button } from "./ui";
import AllocationForm from "./AllocationForm";
import AllocationEditModal from "./AllocationEditModal";
import { AllocationState } from "./EmployeeStatus";
import { endAllocation, getAllocations } from "../services/api/allocations";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { confirmDialog } from "../utils/dialogs";

export default function EmployeeAllocations({ employee, onChanged, canAdd = true }) {
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);
  const [message, setMessage] = useState("");
  const canAllocate = hasPermission("allocations", "create");
  const canEdit = hasPermission("allocations", "edit");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAllocations({ employeeId: employee.id });
      setAllocations(data.filter((a) => a.status === "ACTIVE" || a.status === "PENDING_MARGIN_APPROVAL"));
    } catch (err) {
      console.error("[EmployeeAllocations] Failed to load:", err);
      setMessage(`Could not load allocations: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [employee.id]);

  useEffect(() => {
    load();
  }, [load]);

  const changed = () => {
    load();
    onChanged();
  };

  const end = async (alloc) => {
    if (!(await confirmDialog(`End ${employee.first_name}'s allocation to ${alloc.project_name || alloc.client_name}?`))) return;
    setMessage("");
    try {
      await endAllocation(alloc.id);
      changed();
    } catch (err) {
      console.error("[EmployeeAllocations] Failed to end:", err);
      setMessage(`Could not end the allocation: ${err.message}`);
    }
  };

  return (
    <div className="space-y-3">
      {canAllocate && canAdd && !adding && (
        <Button variant="secondary" size="sm" onClick={() => setAdding(true)}>
          <UserPlus className="h-4 w-4" /> Add allocation
        </Button>
      )}
      {message ? <div className="text-sm text-rose-700">{message}</div> : null}
      {adding && (
        <AllocationForm
          presetEmployeeId={employee.id}
          onCancel={() => setAdding(false)}
          onSaved={(created) => {
            setAdding(false);
            setMessage(created?.status === "PENDING_MARGIN_APPROVAL"
              ? `Saved, waiting for margin approval: ${created.margin?.message || ""}` : "");
            changed();
          }}
        />
      )}
      {loading ? (
        <div className="text-sm text-gray-500">Loading allocations...</div>
      ) : !allocations.length ? (
        <div className="text-sm text-gray-500">No active allocations.</div>
      ) : (
        allocations.map((alloc) => (
          <div key={alloc.id} className="flex items-start justify-between gap-3 rounded-xl border bg-gray-50 p-3 text-sm">
            <div className="space-y-0.5">
              <div className="font-semibold">
                {alloc.project_id ? (
                  <Link to={`/projects?project=${alloc.project_id}`} className="text-blue-700 hover:underline">
                    {alloc.project_name || "Project"}
                  </Link>
                ) : <span className="text-amber-700">No project</span>}
                {" · "}{alloc.client_name}
              </div>
              <div className="text-gray-600">{alloc.demand_job_title}</div>
              <div className="text-gray-600">
                {alloc.utilization_pct}% allocation, from {alloc.start_date}
                {alloc.end_date ? ` to ${alloc.end_date}` : " (open-ended)"}
              </div>
              <AllocationState alloc={alloc} />
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Button variant="ghost" size="sm" onClick={() => setEditing(alloc)}>
                {alloc.status !== "ACTIVE" ? "Review" : canEdit ? "Extend / Edit" : "History"}
              </Button>
              {alloc.status === "ACTIVE" && canAllocate && (
                <Button variant="ghost" size="sm" onClick={() => end(alloc)}>End</Button>
              )}
            </div>
          </div>
        ))
      )}
      {editing && <AllocationEditModal allocation={editing} onClose={() => setEditing(null)} onSaved={changed} />}
    </div>
  );
}
