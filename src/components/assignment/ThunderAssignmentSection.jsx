// S-001/S-006/S-007 -- AI Agent Assignment history + deactivate action.
// Mounted in MessagesTab alongside the other /ai-agent/* sections
// (ThunderMemorySection, ThunderActivitySection, EngagementMetricsSection)
// since that's where this codebase already surfaces all Thunder-related UI.
import { useCallback, useEffect, useState } from "react";
import { Bot, Power } from "lucide-react";
import { toast } from "react-toastify";
import { getAssignments, deactivateAgent } from "../../services/api/aiAgent";

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ThunderAssignmentSection({ candidateId, onChanged }) {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const load = useCallback(async () => {
    if (!candidateId) return;
    try {
      setLoading(true);
      const res = await getAssignments(candidateId);
      setAssignments(Array.isArray(res) ? res : []);
    } catch (err) {
      console.error("Failed to fetch AI agent assignments", err);
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    load();
  }, [load]);

  const activeAssignment = assignments.find((a) => a.is_active);
  const pastAssignments = assignments.filter((a) => !a.is_active);

  const handleDeactivate = async () => {
    if (!candidateId || !activeAssignment) return;
    const confirmed = window.confirm(
      `Deactivate Thunder for this candidate? ${
        activeAssignment.ai_agent_name || "The AI recruiter"
      } will stop messaging them and any open conversation will be closed. This cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      setDeactivating(true);
      await deactivateAgent(candidateId);
      toast.success("AI agent deactivated for this candidate");
      await load();
      await onChanged?.();
    } catch (err) {
      console.error("Failed to deactivate AI agent", err);
      toast.error(err?.message || "Failed to deactivate AI agent");
    } finally {
      setDeactivating(false);
    }
  };

  if (!loading && !assignments.length) return null;

  return (
    <div className="rounded-2xl border bg-white">
      <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-indigo-600" />
          <h3 className="text-sm font-semibold text-gray-900">Thunder Assignment</h3>
        </div>
        {activeAssignment ? (
          <span className="rounded-full border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-semibold text-green-700">
            Active — {activeAssignment.ai_agent_name}
          </span>
        ) : (
          <span className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-semibold text-gray-500">
            No active assignment
          </span>
        )}
      </div>

      <div className="space-y-3 px-4 py-3">
        {activeAssignment && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-gray-100 bg-gray-50 px-3 py-2">
            <div className="text-xs text-gray-600">
              Assigned {formatDateTime(activeAssignment.assigned_at)}
              {activeAssignment.assigned_by
                ? ` by ${activeAssignment.assigned_by}`
                : ""}
              {activeAssignment.ai_agent_persona
                ? ` — ${activeAssignment.ai_agent_persona} persona`
                : ""}
            </div>
            <button
              type="button"
              onClick={handleDeactivate}
              disabled={deactivating}
              className="inline-flex items-center gap-1.5 rounded-xl border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 transition hover:bg-red-100 disabled:opacity-60"
            >
              <Power className="h-3.5 w-3.5" />
              {deactivating ? "Deactivating..." : "Deactivate"}
            </button>
          </div>
        )}

        {pastAssignments.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-xs font-semibold text-blue-600 hover:underline"
            >
              {expanded ? "Hide" : "Show"} assignment history (
              {pastAssignments.length})
            </button>
            {expanded && (
              <div className="mt-2 divide-y divide-gray-50 rounded-xl border border-gray-100">
                {pastAssignments.map((a) => (
                  <div
                    key={a.id}
                    className="flex items-center justify-between px-3 py-2 text-xs text-gray-500"
                  >
                    <span>
                      {a.ai_agent_name}
                      {a.ai_agent_persona ? ` (${a.ai_agent_persona})` : ""}
                    </span>
                    <span>{formatDateTime(a.assigned_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
