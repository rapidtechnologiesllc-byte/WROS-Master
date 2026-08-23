// S-061/HRMS-0461 -- per-candidate Thunder Activity section, mounted
// in MessagesTab (this real screen is single-column, no sidebar --
// same adaptation ThunderMemorySection already made). Last 10
// activities for this candidate, auto-refreshes every 30s per spec.
import { useEffect, useState } from "react";
import { Zap } from "lucide-react";
import { getActivityFeed } from "../../services/api/activityFeed";

const SEVERITY_DOT = { INFO: "bg-gray-400", WARNING: "bg-amber-500", ACTION_REQUIRED: "bg-red-500" };

function timeAgo(iso) {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function ThunderActivitySection({ candidateId }) {
  const [activities, setActivities] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!candidateId) return undefined;
    let cancelled = false;
    const load = async () => {
      try {
        const data = await getActivityFeed({ candidateId, perPage: 10 });
        if (!cancelled) {
          setActivities(data.activities);
          setError("");
        }
      } catch {
        if (!cancelled) setError("Activity feed unavailable");
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [candidateId]);

  if (error) {
    return <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  }
  if (!activities.length) return null;

  return (
    <div className="rounded-2xl border bg-white">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <Zap className="h-4 w-4 text-blue-600" />
        <h3 className="text-sm font-semibold text-gray-900">Thunder Activity</h3>
      </div>
      <div className="divide-y">
        {activities.map((activity) => (
          <div key={activity.id} className="flex items-start gap-2 px-4 py-2.5 text-sm">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${SEVERITY_DOT[activity.severity] || SEVERITY_DOT.INFO}`} />
            <div>
              <div className="text-gray-700">{activity.activity_summary}</div>
              <div className="mt-0.5 text-[11px] text-gray-400">{timeAgo(activity.created_at)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
