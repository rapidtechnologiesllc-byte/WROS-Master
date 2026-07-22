// HRMS-1105 (canonical S-320) Resource Management Agent -- the bench-scan
// recommendation queue. Avinash's explicit business rule lives here in the
// UI too: once an employee is being actively pursued for one client
// (status IN_PROGRESS), every other recommendation for that same employee
// is hard-blocked from being pursued (409 from the API) until this one
// resolves -- the error banner below surfaces that block clearly rather
// than as a generic failure.
import { useEffect, useState } from "react";
import { Users2, RefreshCw, CheckCircle2, XCircle, PlayCircle, Search } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import cx from "../utils/cx";
import {
  triggerBenchScan,
  getRecommendationQueue,
  pursueRecommendation,
  approveRecommendation,
  rejectRecommendation,
  getMatchingBenchResources,
} from "../services/api/resourceManagement";

function MatchBenchResourcesCard() {
  const [demandId, setDemandId] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!demandId.trim()) {
      setError("Demand ID is required.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await getMatchingBenchResources(demandId.trim());
      setResult(res);
    } catch (err) {
      setError(err.message || "Failed to find matching bench resources.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title="Match Bench Resources to Opportunity"
      subtitle="Top 5 current bench employees for a demand, ranked by skill match. Read-only preview -- doesn't create a recommendation."
      icon={<Search className="h-4 w-4" />}
    >
      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Input label="Demand ID" value={demandId} onChange={setDemandId} placeholder="demand UUID" />
        </div>
        <Button variant="primary" disabled={loading} onClick={handleSearch}>
          {loading ? "Searching…" : "Find Matches"}
        </Button>
      </div>

      {result ? (
        <div className="mt-4">
          <div className="mb-2 text-xs font-semibold text-gray-700">
            Candidates for: {result.demand_job_title}
          </div>
          {result.candidates.length === 0 ? (
            <div className="text-sm text-gray-500">No matching bench candidates found.</div>
          ) : (
            <ul className="space-y-2">
              {result.candidates.map((c) => (
                <li key={c.employee_id} className="flex items-center justify-between rounded-xl border px-3 py-2 text-sm">
                  <div>
                    <div className="font-semibold text-gray-900">{c.employee_name}</div>
                    <div className="text-xs text-gray-500">{c.employee_current_title || "—"}</div>
                  </div>
                  <span className="text-sm font-semibold text-gray-700">{c.score_pct}%</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </Card>
  );
}

const STATUS_STYLES = {
  PENDING_RM_REVIEW: "border-amber-200 bg-amber-50 text-amber-800",
  IN_PROGRESS: "border-blue-200 bg-blue-50 text-blue-800",
  APPROVED: "border-green-200 bg-green-50 text-green-800",
  REJECTED: "border-red-200 bg-red-50 text-red-800",
};

const STATUS_LABELS = {
  PENDING_RM_REVIEW: "Pending Review",
  IN_PROGRESS: "Pursuing",
  APPROVED: "Approved",
  REJECTED: "Rejected",
};

function RecStatusBadge({ status }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STATUS_STYLES[status] || "border-gray-200 bg-gray-50 text-gray-800",
      )}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

export default function ResourceManagementScreen() {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [actioningId, setActioningId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getRecommendationQueue();
      setRecommendations(res?.recommendations || []);
    } catch (err) {
      setError(err.message || "Failed to load the recommendation queue.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleScan = async () => {
    setScanning(true);
    setError("");
    setNotice("");
    try {
      const res = await triggerBenchScan();
      setNotice(
        `Scan complete: ${res.recommendations_created} new recommendation(s), ` +
          `${res.core_pull_events_triggered} Core-Pull event(s) triggered.`,
      );
      await load();
    } catch (err) {
      setError(err.message || "Bench scan failed.");
    } finally {
      setScanning(false);
    }
  };

  const runAction = async (id, action) => {
    setActioningId(id);
    setError("");
    setNotice("");
    try {
      await action(id);
      await load();
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setActioningId("");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Resource Management Agent"
        subtitle="Bench employees matched against open demand. Pursuing a recommendation puts that employee on hold at one client -- they can't be pursued anywhere else until it's approved or rejected."
        icon={<Users2 className="h-4 w-4" />}
        right={
          <Button variant="secondary" onClick={handleScan} disabled={scanning}>
            <RefreshCw className={cx("h-4 w-4", scanning ? "animate-spin" : "")} />
            {scanning ? "Scanning…" : "Run Bench Scan"}
          </Button>
        }
        bodyClassName="p-0"
      >
        {error ? (
          <div className="mx-5 mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mx-5 mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        <div className="px-5 py-4">
          {loading ? (
            <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
          ) : recommendations.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">
              No recommendations yet. Run a bench scan to generate matches.
            </div>
          ) : (
            <div className="overflow-visible rounded-2xl border">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Employee</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Demand / Client</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Confidence</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Rationale</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Status</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y bg-white">
                  {recommendations.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-900">
                        <div className="font-semibold">{r.employee_name}</div>
                        <div className="text-xs text-gray-500">
                          {r.employee_current_title || "—"}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-900">
                        <div>{r.demand_job_title}</div>
                        <div className="text-xs text-gray-500">{r.client_name || "—"}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-900">{r.confidence_pct}%</td>
                      <td className="max-w-xs px-4 py-3 text-xs text-gray-600">
                        {r.rationale || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <RecStatusBadge status={r.status} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          {r.status === "PENDING_RM_REVIEW" ? (
                            <Button
                              variant="secondary"
                              disabled={actioningId === r.id}
                              onClick={() => runAction(r.id, pursueRecommendation)}
                            >
                              <PlayCircle className="h-4 w-4" /> Pursue
                            </Button>
                          ) : null}
                          {r.status === "IN_PROGRESS" ? (
                            <>
                              <Button
                                variant="success"
                                disabled={actioningId === r.id}
                                onClick={() => runAction(r.id, approveRecommendation)}
                              >
                                <CheckCircle2 className="h-4 w-4" /> Approve
                              </Button>
                              <Button
                                variant="danger"
                                disabled={actioningId === r.id}
                                onClick={() => runAction(r.id, rejectRecommendation)}
                              >
                                <XCircle className="h-4 w-4" /> Reject
                              </Button>
                            </>
                          ) : null}
                          {r.status === "PENDING_RM_REVIEW" ? (
                            <Button
                              variant="ghost"
                              disabled={actioningId === r.id}
                              onClick={() => runAction(r.id, rejectRecommendation)}
                            >
                              Reject
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      <MatchBenchResourcesCard />
    </div>
  );
}
