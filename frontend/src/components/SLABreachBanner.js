// S-020/HRMS-0420 -- Engagement SLA Monitoring. Mounted above the
// recruiter's candidate list (same placement as ConversationSearchBar).
// Red banner when active breaches exist; click expands an inline
// breach table sorted oldest-first (most urgent first).
import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getActiveSLABreaches } from "../services/api/slaBreaches";

export default function SLABreachBanner() {
  const navigate = useNavigate();
  const [breaches, setBreaches] = useState([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getActiveSLABreaches()
      .then((res) => {
        if (!cancelled) setBreaches(res?.breaches || []);
      })
      .catch(() => {
        if (!cancelled) setBreaches([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (breaches.length === 0) return null;

  return (
    <div className="mb-4 overflow-hidden rounded-2xl border border-red-200 bg-red-50">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-red-700">
          <AlertTriangle className="h-4 w-4" />
          {breaches.length} candidate{breaches.length === 1 ? "" : "s"} need attention — View
        </span>
      </button>
      {expanded ? (
        <div className="border-t border-red-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs font-semibold uppercase text-gray-400">
                <th className="px-4 py-2">Candidate</th>
                <th className="px-4 py-2">Breach Type</th>
                <th className="px-4 py-2">Hours Since Breach</th>
                <th className="px-4 py-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {breaches.map((b) => (
                <tr key={`${b.candidate_id}-${b.conversation_id}`}>
                  <td className="px-4 py-2 font-medium text-gray-900">{b.candidate_name}</td>
                  <td className="px-4 py-2 text-gray-600">{b.sla_type.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2 text-gray-600">{b.hours_since_breach}</td>
                  <td className="px-4 py-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/candidates/${b.candidate_id}`)}
                      className="text-xs font-semibold text-bx-orange hover:underline"
                    >
                      View Conversation
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
