// Public: the client's timesheet approver opens this from the emailed link (no account, no login).
// The single-use token is sent in the request body; the page shows only that one week's hours
// and lets the approver approve, or reject with a reason.
import { useEffect, useState } from "react";
import { getApiBaseUrl, formatApiErrorMessage } from "../services/api/client";

const post = async (path, body) => {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/public/client-timesheet-approval${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch (parseError) {
    throw new Error(`Unexpected response from the server (HTTP ${response.status}).`);
  }
  if (!response.ok) throw new Error(formatApiErrorMessage(data));
  return data;
};

export default function ClientTimesheetApproval() {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  const [week, setWeek] = useState(null);
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("This link is incomplete. Open it again from the email.");
      return;
    }
    post("/view", { token }).then(setWeek).catch((err) => setError(err.message));
  }, [token]);

  const decide = async (path, body) => {
    setBusy(true);
    setError("");
    try {
      const res = await post(path, { token, ...body });
      setDone(res.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-lg rounded-2xl border bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-gray-900">Timesheet approval</h1>
        {error ? <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
        {done ? <p className="mt-4 text-sm text-gray-700">{done}</p> : null}
        {week && !done ? (
          <div className="mt-3 space-y-3">
            <p className="text-sm text-gray-700">
              {week.employee_name} worked <b>{week.total_hours} hours</b> for {week.client_name} in the week of{" "}
              {week.week_starting_date} to {week.week_ending_date}. Sent by {week.issuer_name}.
            </p>
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-gray-500">
                <tr><th className="py-1">Day</th><th>Hours</th><th>Type</th></tr>
              </thead>
              <tbody className="divide-y">
                {week.entries.map((e) => (
                  <tr key={e.entry_date}>
                    <td className="py-1">{e.entry_date}</td>
                    <td>{e.hours}</td>
                    <td className="text-gray-600">{e.entry_type.replace(/_/g, " ").toLowerCase()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rejecting ? (
              <div className="space-y-2">
                <textarea className="w-full rounded-xl border px-3 py-2 text-sm" rows={3}
                  placeholder="Why are you rejecting these hours? (required)" value={reason}
                  onChange={(e) => setReason(e.target.value)} />
                <div className="flex gap-2">
                  <button type="button" disabled={busy || !reason.trim()}
                    className="rounded-xl bg-rose-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                    onClick={() => decide("/reject", { reason: reason.trim() })}>Reject with this reason</button>
                  <button type="button" className="rounded-xl px-3 py-2 text-sm font-semibold text-gray-700"
                    onClick={() => setRejecting(false)}>Back</button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <button type="button" disabled={busy}
                  className="rounded-xl bg-gray-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  onClick={() => decide("/approve", {})}>Approve</button>
                <button type="button" disabled={busy}
                  className="rounded-xl border px-3 py-2 text-sm font-semibold text-gray-800 disabled:opacity-50"
                  onClick={() => setRejecting(true)}>Reject</button>
              </div>
            )}
            <p className="text-xs text-gray-500">This link works once and expires on {week.expires_at.slice(0, 10)}.</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
