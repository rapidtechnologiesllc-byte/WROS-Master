// When Thunder last emailed this candidate, their last reply, the next planned email and the
// profile details Thunder is still asking for (GET /candidates/{id}/thunder-status).
import { useEffect, useState } from "react";
import { Bot } from "lucide-react";
import { getCandidateThunderStatus } from "../../services/api/candidates";

function formatDateTime(value) {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function Item({ label, value, hint }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm font-medium text-gray-900">{value}</p>
      {hint && <p className="text-xs text-gray-500 truncate" title={hint}>{hint}</p>}
    </div>
  );
}

export default function ThunderContactCard({ candidateId }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!candidateId) return undefined;
    let active = true;
    getCandidateThunderStatus(candidateId)
      .then((data) => { if (active) { setStatus(data); setError(null); } })
      .catch((err) => {
        console.error("[ThunderContactCard] Failed to load Thunder status", err);
        if (active) setError(`Could not load Thunder status: ${err.message}`);
      });
    return () => { active = false; };
  }, [candidateId]);

  if (error) {
    return <div className="bg-white border border-red-200 rounded-xl p-4 text-sm text-red-700">{error}</div>;
  }
  if (!status) return null;

  const next = status.next_action_at
    ? `${status.next_step_label} · ${formatDateTime(status.next_action_at)}`
    : status.stop_reason ? `Stopped (${status.stop_reason})` : "Nothing planned";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-indigo-600" />
          <h3 className="text-sm font-semibold text-gray-900">Thunder</h3>
          <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 text-xs">{status.stage_label}</span>
          {!status.thunder_enabled && (
            <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs">Off for this candidate</span>
          )}
        </div>
        <span className="text-xs text-gray-500">{status.emails_sent} email{status.emails_sent === 1 ? "" : "s"} sent</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Item label="Last email from Thunder" value={formatDateTime(status.last_email_at)} hint={status.last_email_subject} />
        <Item label="Last reply from candidate" value={formatDateTime(status.last_reply_at)}
              hint={status.last_reply_intent ? `Read as ${status.last_reply_intent.toLowerCase().replace(/_/g, " ")}` : null} />
        <Item label="Next from Thunder" value={next} />
      </div>
      {status.missing_fields.length > 0 && (
        <p className="mt-3 text-xs text-gray-600">
          <span className="font-medium text-gray-700">Still asking for: </span>
          {status.missing_fields.map((label) => label.split("(")[0].trim()).join(", ")}
        </p>
      )}
    </div>
  );
}
