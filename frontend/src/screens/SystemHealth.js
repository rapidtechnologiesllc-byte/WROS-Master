// System Health (Admin & Settings): the backend's own health, read through the API client
// (same origin and auth as every other screen; it used to call http://localhost:8080 from the
// user's browser, which only worked on a developer machine). Both endpoints check system-health.view.
import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button, Card } from "../components/ui";
import { apiRequest } from "../services/api/client";

const REFRESH_MS = 30000;

const tone = (status) => {
  const s = String(status || "").toUpperCase();
  if (s === "HEALTHY" || s === "CLOSED") return "bg-green-100 text-green-800";
  if (s === "WARNING" || s === "DEGRADED" || s === "HALF_OPEN") return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
};

const Badge = ({ status }) => (
  <span className={`rounded px-2 py-0.5 text-xs font-semibold ${tone(status)}`}>{String(status || "UNKNOWN").toUpperCase()}</span>
);

const Row = ({ label, value }) => (
  <div className="flex justify-between border-b py-1.5 text-sm last:border-0">
    <span className="text-gray-600">{label}</span>
    <span className="font-medium text-gray-900">{value ?? "--"}</span>
  </div>
);

export default function SystemHealth() {
  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [checkedAt, setCheckedAt] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [h, s] = await Promise.all([
        apiRequest("/system/health", { method: "GET" }),
        apiRequest("/system/health/summary", { method: "GET" }),
      ]);
      setHealth(h.data);
      setSummary(s.data);
      setError(null);
      setCheckedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError(`Failed to load system health: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const pool = summary?.components?.database_pool || {};
  const circuit = summary?.components?.permission_circuit || {};
  const cache = summary?.components?.permission_cache || {};

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">System Health</h1>
          <p className="text-sm text-gray-500">{checkedAt ? `Checked ${checkedAt} · refreshes every 30 s` : "Checking..."}</p>
        </div>
        <Button variant="secondary" onClick={load} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {summary && (
        <Card title="Platform">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-sm text-gray-600">Overall</span>
            <Badge status={summary.status} />
          </div>
          {summary.issues?.length > 0 && (
            <ul className="mb-3 list-disc pl-5 text-sm text-red-700">
              {summary.issues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          )}
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <div className="mb-1 flex items-center justify-between text-sm font-semibold">Database pool <Badge status={pool.status} /></div>
              <Row label="Utilization" value={pool.utilization_percent != null ? `${Number(pool.utilization_percent).toFixed(0)}%` : null} />
              <Row label="Checked out" value={pool.checked_out_connections} />
              <Row label="Capacity" value={pool.total_capacity} />
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between text-sm font-semibold">Permission service <Badge status={circuit.state} /></div>
              <Row label="Failures" value={circuit.failure_count} />
              <Row label="Last failure" value={circuit.last_failure_time} />
            </div>
            <div>
              <div className="mb-1 text-sm font-semibold">Permission cache</div>
              {Object.entries(cache).map(([key, value]) => (
                <Row key={key} label={key.replace(/_/g, " ")} value={typeof value === "object" ? JSON.stringify(value) : String(value)} />
              ))}
            </div>
          </div>
        </Card>
      )}

      {health && (
        <Card title="Self-healing">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-sm text-gray-600">Status</span>
            <Badge status={health.status} />
            <span className="text-xs text-gray-500">cycle {health.cycle}</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {Object.entries(health.components || {}).map(([name, component]) => (
              <div key={name}>
                <div className="mb-1 text-sm font-semibold capitalize">{name}</div>
                <p className="mb-1 text-xs text-gray-500">{component.description}</p>
                {Object.entries(component)
                  .filter(([key]) => key !== "description")
                  .map(([key, value]) => <Row key={key} label={key.replace(/_/g, " ")} value={String(value)} />)}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
