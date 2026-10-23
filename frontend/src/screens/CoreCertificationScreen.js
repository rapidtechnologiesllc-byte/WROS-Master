// Core certification approvals (CEO 2026-10-14). The daily job raises a request when an employee
// has graduated Buddy and has 90 approved billable Staff Aug days with no escalation; the BU Head
// (or another leader of that business unit) decides in Flash: Approve / Reject open the Flash
// bubble on the request (?flash=core_cert:<id>), where a rejection is a short discussion that
// becomes follow-up tasks. Who may decide and whether someone still qualifies come from the API.
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Award, MessageCircleQuestion, RefreshCw } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { closeCoreCertification, getCoreCertificationRequests } from "../services/api/coreCertification";
import { FLASH_WORKFLOW_DONE_EVENT } from "../services/api/flash";

function PendingRow({ request, onChanged }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // the decision (and a rejection discussion) happens in the Flash bubble, on any screen
  const decideInFlash = () => navigate(`?flash=core_cert:${encodeURIComponent(request.id)}`);

  const act = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn(request.id);
      onChanged();
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          {request.candidate_id ? (
            <Link to={`/candidates/${encodeURIComponent(request.candidate_id)}`} className="font-semibold text-blue-700 hover:underline">
              {request.employee_name}
            </Link>
          ) : (
            <span className="font-semibold">{request.employee_name}</span>
          )}
          <div className="text-xs text-gray-500">
            {request.billable_days} approved billable Staff Aug days
            {request.counted_from ? ` since ${request.counted_from}` : ""} · raised{" "}
            {request.created_at ? new Date(request.created_at).toLocaleDateString() : "—"}
          </div>
          {!request.still_eligible ? (
            <div className="mt-1 text-xs text-amber-800">No longer eligible: {request.eligibility_reasons.join(" ")}</div>
          ) : null}
        </div>
        {request.can_decide ? (
          <div className="flex gap-2">
            {request.chat_in_progress ? (
              <Button size="sm" disabled={busy} onClick={decideInFlash}>
                <MessageCircleQuestion className="h-4 w-4" /> Continue in Flash
              </Button>
            ) : request.still_eligible ? (
              <>
                <Button size="sm" variant="success" disabled={busy} onClick={decideInFlash}>
                  Approve
                </Button>
                <Button size="sm" variant="danger" disabled={busy} onClick={decideInFlash}>
                  Reject
                </Button>
              </>
            ) : (
              <Button size="sm" disabled={busy} onClick={() => act(closeCoreCertification)}>
                Close request
              </Button>
            )}
          </div>
        ) : (
          <span className="text-xs text-gray-500">Waiting on the BU Head</span>
        )}
      </div>
      {error ? <div className="mt-2 text-xs text-rose-700">{error}</div> : null}
    </div>
  );
}

export default function CoreCertificationScreen() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getCoreCertificationRequests();
      setRequests(data?.requests || []);
    } catch (err) {
      setError(err.message || "Failed to load Core certification requests.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // a decision taken in the Flash bubble changes this list
  useEffect(() => {
    const onDone = (event) => {
      if (event.detail?.kind === "core_cert") load();
    };
    window.addEventListener(FLASH_WORKFLOW_DONE_EVENT, onDone);
    return () => window.removeEventListener(FLASH_WORKFLOW_DONE_EVENT, onDone);
  }, [load]);

  const pending = requests.filter((r) => r.status === "PENDING");
  const decided = requests.filter((r) => r.status !== "PENDING");

  return (
    <div className="grid gap-4">
      <Link to="/workforce" className="flex items-center gap-1 text-sm font-semibold text-blue-700 hover:underline">
        <ArrowLeft className="h-4 w-4" /> Workforce Overview
      </Link>
      <Card
        title={`Core certification: awaiting decision (${pending.length})`}
        subtitle="Buddy graduated, 90 approved billable Staff Aug days, no escalation in them. The BU Head decides in Flash: approve, or tell Flash why not."
        icon={<Award className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        <div className="space-y-3">
          {loading ? <div className="text-sm text-gray-500">Loading…</div> : null}
          {!loading && pending.length === 0 ? <div className="text-sm text-gray-500">Nothing awaiting a decision.</div> : null}
          {pending.map((r) => (
            <PendingRow key={r.id} request={r} onChanged={load} />
          ))}
        </div>
      </Card>

      <Card title={`Decided (${decided.length})`}>
        <div className="overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["Employee", "Decision", "Decided", "Reason / follow-ups"].map((h) => (
                  <th key={h} className="px-4 py-3 text-xs font-semibold text-gray-700">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {decided.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-500">No decisions yet.</td>
                </tr>
              ) : (
                decided.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-3 font-semibold">{r.employee_name}</td>
                    <td className="px-4 py-3 text-xs">{r.status}</td>
                    <td className="px-4 py-3 text-xs">{r.decided_at ? new Date(r.decided_at).toLocaleDateString() : "—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {r.rejection_reason || "—"}
                      {(r.follow_up_plan || []).map((f) => (
                        <div key={f.task_id}>• {f.criterion}: {f.days} days</div>
                      ))}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
