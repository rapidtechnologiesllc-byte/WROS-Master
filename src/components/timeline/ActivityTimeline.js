// S-216/HRMS-0118 -- reusable activity feed. Any entity detail screen
// drops this in with just an entityType/entityId; no per-entity
// component needed (BR-0118-01's sanctioned pattern, frontend half).
import { useEffect, useState } from "react";
import { Clock, Plus } from "lucide-react";
import { getTimeline, postTimelineEntry } from "../../services/api/activityTimeline";

export default function ActivityTimeline({ entityType, entityId }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 10;

  const [showForm, setShowForm] = useState(false);
  const [action, setAction] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const load = () => {
    if (!entityType || !entityId) return;
    setLoading(true);
    getTimeline(entityType, entityId, { page, perPage })
      .then((res) => {
        setEntries(res.entries || []);
        setTotal(res.total || 0);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [entityType, entityId, page]);

  const handleAddNote = async (e) => {
    e.preventDefault();
    const trimmedAction = action.trim();
    if (!trimmedAction) {
      setFormError("A short note title is required.");
      return;
    }
    setSubmitting(true);
    setFormError("");
    try {
      const res = await postTimelineEntry(entityType, entityId, trimmedAction, description.trim() || undefined);
      setEntries(res.entries || []);
      setTotal(res.total || 0);
      setPage(1);
      setAction("");
      setDescription("");
      setShowForm(false);
    } catch (err) {
      setFormError(err?.message || "Failed to add note.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && entries.length === 0) {
    return <div className="py-4 text-center text-xs text-gray-400">Loading activity...</div>;
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Activity Timeline</span>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1 rounded-lg border border-gray-200 px-2 py-1 text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
        >
          <Plus className="h-3 w-3" />
          Add note
        </button>
      </div>

      {showForm ? (
        <form onSubmit={handleAddNote} className="mb-4 space-y-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
          {formError ? <div className="text-xs font-medium text-red-600">{formError}</div> : null}
          <input
            type="text"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="Note title (e.g. Called candidate)"
            maxLength={120}
            className="w-full rounded-lg border px-2.5 py-1.5 text-xs outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            autoFocus
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Details (optional)"
            rows={2}
            className="w-full resize-none rounded-lg border px-2.5 py-1.5 text-xs outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setFormError("");
              }}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-black disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Save note"}
            </button>
          </div>
        </form>
      ) : null}

      {entries.length === 0 ? (
        <div className="py-4 text-center text-xs text-gray-400">No activity yet.</div>
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}
