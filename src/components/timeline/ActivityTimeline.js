// S-216/HRMS-0118 -- reusable activity feed. Any entity detail screen
// drops this in with just an entityType/entityId; no per-entity
// component needed (BR-0118-01's sanctioned pattern, frontend half).
import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { getTimeline } from "../../services/api/activityTimeline";

export default function ActivityTimeline({ entityType, entityId }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 10;

  useEffect(() => {
    if (!entityType || !entityId) return;
    setLoading(true);
    getTimeline(entityType, entityId, { page, perPage })
      .then((res) => {
        setEntries(res.entries || []);
        setTotal(res.total || 0);
      })
      .finally(() => setLoading(false));
  }, [entityType, entityId, page]);

  if (loading && entries.length === 0) {
    return <div className="py-4 text-center text-xs text-gray-400">Loading activity...</div>;
  }
  if (!loading && entries.length === 0) {
    return <div className="py-4 text-center text-xs text-gray-400">No activity yet.</div>;
  }

  return (
    <div>
      <div className="space-y-3">
        {entries.map((e) => (
          <div key={e.id} className="flex gap-2.5 border-l-2 border-gray-100 pl-3">
            <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-gray-800">{e.action}</div>
              {e.description ? (
                <div className="mt-0.5 text-xs text-gray-600">{e.description}</div>
              ) : null}
              <div className="mt-0.5 text-[11px] text-gray-400">
                {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
                {e.actor_type === "SYSTEM" ? " · system" : e.actor_type === "AI_AGENT" ? " · Thunder" : ""}
              </div>
            </div>
          </div>
        ))}
      </div>
      {total > perPage ? (
        <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="disabled:opacity-40"
          >
            ← Newer
          </button>
          <span>
            Page {page} of {Math.ceil(total / perPage)}
          </span>
          <button
            type="button"
            disabled={page * perPage >= total}
            onClick={() => setPage((p) => p + 1)}
            className="disabled:opacity-40"
          >
            Older →
          </button>
        </div>
      ) : null}
    </div>
  );
}
