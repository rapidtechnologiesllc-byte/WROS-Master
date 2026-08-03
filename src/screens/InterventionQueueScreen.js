// S-062/HRMS-0462 -- Recruiter Intervention Queue standalone page.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { getInterventionQueue, resolveQueueItem, takeOverQueueItem } from "../services/api/interventionQueue";

const PRIORITY_LABELS = { 1: "CRITICAL", 2: "HIGH", 3: "MEDIUM" };
const PRIORITY_BADGE = {
  1: "bg-red-100 text-red-800 border-red-300 animate-pulse",
  2: "bg-red-50 text-red-700 border-red-200",
  3: "bg-amber-50 text-amber-700 border-amber-200",
};
const REASON_LABELS = {
  ESCALATION: "Escalation", HIGH_DROP_RISK: "High Drop Risk", CRITICAL_DROP_RISK: "Critical Drop Risk",
  SLA_BREACH: "SLA Breach", HIGH_ABANDONMENT: "High Abandonment", NO_SHOW: "No-Show",
  OFFER_COUNTER: "Offer Countered", DOCUMENT_OVERDUE: "Document Overdue",
};

function timeAgo(iso) {
  if (!iso) return "";
  const hours = Math.round((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function isOverdue(iso) {
  if (!iso) return false;
  return Date.now() - new Date(iso).getTime() > 24 * 60 * 60 * 1000;
}

export default function InterventionQueueScreen() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [resolvingId, setResolvingId] = useState(null);
  const [resolutionNote, setResolutionNote] = useState("");
  const navigate = useNavigate();

  const load = async () => {
    try {
      const data = await getInterventionQueue();
      setItems(data.items);
    } catch {
      toast.error("Unable to load intervention queue.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleTakeOver = async (item) => {
    try {
      await takeOverQueueItem(item.id);
      toast.success(`Took over ${item.candidate_name}'s conversation.`);
      load();
    } catch (err) {
      toast.error(err?.message || "Failed to take over.");
    }
  };

  const handleResolveConfirm = async (item) => {
    try {
      await resolveQueueItem(item.id, resolutionNote);
      toast.success("Marked resolved.");
      setResolvingId(null);
      setResolutionNote("");
      load();
    } catch (err) {
      toast.error(err?.message || "Failed to resolve.");
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Recruiter Intervention Queue</h1>
        <p className="text-sm text-gray-500">Candidates that need you right now, sorted by urgency.</p>
      </div>

      <div className="rounded-2xl border bg-white shadow-sm">
        {loading ? (
          <div className="p-6 text-center text-sm text-gray-500">Loading...</div>
        ) : items.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-500">Nothing needs attention right now.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold text-gray-500">
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Candidate</th>
                  <th className="px-4 py-3">Reason</th>
                  <th className="px-4 py-3">Added</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b last:border-b-0">
                    <td className="px-4 py-3">
                      <span className={`inline-block rounded-full border px-2.5 py-1 text-xs font-semibold ${PRIORITY_BADGE[item.priority]}`}>
                        {PRIORITY_LABELS[item.priority]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => navigate(`/candidates/${item.candidate_id}?tab=messages`)}
                        className="font-semibold text-gray-900 hover:underline"
                      >
                        {item.candidate_name}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {REASON_LABELS[item.queue_reason] || item.queue_reason}
                      {item.reason_detail ? `: ${item.reason_detail}` : ""}
                    </td>
                    <td className={`px-4 py-3 ${isOverdue(item.added_at) ? "text-red-600 font-semibold" : "text-gray-500"}`}>
                      {timeAgo(item.added_at)}
                    </td>
                    <td className="px-4 py-3">
                      {item.status === "RESOLVED" ? (
                        <span className="text-xs text-gray-400">Resolved</span>
                      ) : (
                        <div className="flex flex-wrap items-center gap-2">
                          {item.status === "OPEN" && (
                            <button
                              onClick={() => handleTakeOver(item)}
                              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50"
                            >
                              Take Over
                            </button>
                          )}
                          <button
                            onClick={() => setResolvingId(item.id)}
                            className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50"
                          >
                            Mark Resolved
                          </button>
                        </div>
                      )}
                      {resolvingId === item.id && (
                        <div className="mt-2 space-y-2 rounded-lg border bg-gray-50 p-2">
                          <input
                            type="text"
                            value={resolutionNote}
                            onChange={(e) => setResolutionNote(e.target.value)}
                            placeholder="Resolution note (optional)"
                            className="w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                          />
                          <div className="flex gap-2">
                            <button onClick={() => handleResolveConfirm(item)} className="rounded-md bg-bx-navy px-2 py-1 text-xs font-semibold text-white">
                              Confirm
                            </button>
                            <button onClick={() => setResolvingId(null)} className="rounded-md border px-2 py-1 text-xs">
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
