// A job's history (CEO 2026-11-05): read from the records the work leaves behind, so nobody logs anything.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJobHistory } from "../services/api/jobs";

export default function JobHistory({ jobId }) {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    getJobHistory(jobId)
      .then((res) => { if (live) setEvents(res?.events || []); })
      .catch((err) => { if (live) setError(`Could not load the history: ${err.message}`); });
    return () => { live = false; };
  }, [jobId]);

  if (error) return <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>;
  if (!events) return <div className="rounded-2xl border bg-white p-6 text-sm text-slate-500">Loading…</div>;
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="mb-3 text-sm font-bold text-slate-900">History</div>
      <ol className="space-y-3">
        {events.map((event, index) => (
          <li key={`${event.at}-${index}`} className="border-l-2 border-slate-200 pl-3">
            <div className="text-xs text-slate-500">
              {new Date(event.at).toLocaleString()}{event.actor ? ` · ${event.actor}` : ""}
            </div>
            <div className="text-sm font-semibold text-slate-900">
              {event.link ? <Link className="hover:underline" to={event.link}>{event.title}</Link> : event.title}
            </div>
            {event.detail ? <div className="text-xs text-slate-600">{event.detail}</div> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
