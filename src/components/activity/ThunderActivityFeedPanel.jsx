// S-061/HRMS-0461 -- AI Activity Feed, global recruiter dashboard view.
// A distinct icon from TopBar's existing generic notification Bell
// (S-105/HRMS-P210) -- that one surfaces recruiter notifications from
// notification_service.py; this one is specifically Thunder's own
// activity transparency feed, a different data source and purpose.
import { useEffect, useRef, useState } from "react";
import { Zap } from "lucide-react";
import { useNavigate } from "react-router-dom";
import cx from "../../utils/cx";
import { getActivityFeed, markAllActivityRead } from "../../services/api/activityFeed";

const SEVERITY_BORDER = {
  INFO: "border-l-gray-300",
  WARNING: "border-l-amber-400",
  ACTION_REQUIRED: "border-l-red-500",
};

function timeAgo(iso) {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function ThunderActivityFeedPanel() {
  const [open, setOpen] = useState(false);
  const [feed, setFeed] = useState({ activities: [], unread_count: 0 });
  const panelRef = useRef(null);
  const navigate = useNavigate();

  const load = async () => {
    try {
      const data = await getActivityFeed({ perPage: 25 });
      setFeed(data);
    } catch {
      // Bell badge just won't update this cycle -- never crash the shell.
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!open) return;
      if (panelRef.current && !panelRef.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const handleOpen = async () => {
    const opening = !open;
    setOpen(opening);
    if (opening) {
      // BR-01: only INFO/WARNING auto-clear on open -- ACTION_REQUIRED
      // items stay unread until the recruiter explicitly deals with them.
      try {
        await markAllActivityRead();
      } catch {
        // Non-fatal -- badge will just stay elevated until next load.
      }
      load();
    }
  };

  const handleItemClick = (activity) => {
    if (activity.candidate_id) navigate(`/candidates/${activity.candidate_id}?tab=messages`);
    setOpen(false);
  };

  return (
    <div className="relative" ref={panelRef}>
      <button onClick={handleOpen} className="relative" aria-label="Thunder Activity Feed">
        <Zap className="h-5 w-5 cursor-pointer text-gray-500 hover:text-black transition" />
        {feed.unread_count > 0 ? (
          <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-semibold text-white">
            {feed.unread_count > 9 ? "9+" : feed.unread_count}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-10 z-[9999] max-h-[28rem] w-96 overflow-y-auto rounded-2xl border bg-white shadow-xl">
          <div className="border-b px-4 py-2 text-xs font-semibold text-gray-500">
            THUNDER ACTIVITY {feed.unread_count > 0 ? `(${feed.unread_count} unread)` : ""}
          </div>
          {feed.activities.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-gray-500">No recent activity.</div>
          ) : (
            feed.activities.map((activity) => (
              <button
                key={activity.id}
                onClick={() => handleItemClick(activity)}
                className={cx(
                  "block w-full border-b border-l-4 px-4 py-2.5 text-left text-sm last:border-b-0 hover:bg-gray-50",
                  SEVERITY_BORDER[activity.severity] || SEVERITY_BORDER.INFO,
                  !activity.is_read && "bg-blue-50/50",
                )}
              >
                <div className="text-gray-800">
                  <span className="font-semibold">{activity.candidate_name}</span>{" "}
                  {activity.activity_summary.replace(activity.candidate_name, "").trim()}
                </div>
                <div className="mt-0.5 text-[11px] text-gray-400">{timeAgo(activity.created_at)}</div>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
