// HRMS-0906 (S-225 Revenue Leakage Detection) + HRMS-0903 (Timesheet-
// to-Revenue Reconciliation) + HRMS-0909 (S-228 Client Revenue
// Realization Dashboard). Internal-only estimates, not finance figures
// -- each response is labeled as such by the backend.
import { useEffect, useState } from "react";
import { AlertOctagon, RefreshCw, GitCompareArrows, LineChart } from "lucide-react";
import { Card, Button, Input, TextArea } from "../components/ui";
import cx from "../utils/cx";
import {
  scanRevenueLeakage,
  logLeakagePartialBillingReason,
  getActiveLeakageFlags,
  scanReconciliationGaps,
  getReconciliationAlerts,
  resolveReconciliationAlert,
  getClientRevenueDashboard,
} from "../services/api/revenue";

function ScanLeakageForm({ onScanned }) {
  const [projectId, setProjectId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(undefined);

  const handleScan = async () => {
    if (!projectId.trim() || !periodStart || !periodEnd) {
      setError("Project ID and both period dates are required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const flag = await scanRevenueLeakage(projectId.trim(), periodStart, periodEnd);
      setResult(flag);
      onScanned();
    } catch (err) {
      setError(err.message || "Failed to scan for leakage.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border p-4">
      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="Project ID" value={projectId} onChange={setProjectId} placeholder="project UUID" />
        <Input label="Period start" type="date" value={periodStart} onChange={setPeriodStart} />
        <Input label="Period end" type="date" value={periodEnd} onChange={setPeriodEnd} />
      </div>
      <Button variant="primary" disabled={busy} onClick={handleScan} className="mt-3">
        {busy ? "Scanning…" : "Scan for Leakage"}
      </Button>
      {result === null ? (
        <div className="mt-2 text-xs text-emerald-700">No leakage -- fully billed, or still within the grace period.</div>
      ) : result ? (
        <div className="mt-2 text-xs text-amber-700">
          Flagged: {result.unbilled_hours}h unbilled ({result.approved_hours}h approved vs {result.invoiced_hours}h invoiced).
        </div>
      ) : null}
    </div>
  );
}

function LeakageFlagRow({ flag, onChanged }) {
  const [showReason, setShowReason] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleLogReason = async () => {
    setBusy(true);
    setError("");
    try {
      await logLeakagePartialBillingReason(flag.id, reason);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to log reason.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-lg border px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-gray-900">Project {flag.project_id}</span>
        <span className="text-amber-700">{flag.unbilled_hours}h unbilled</span>
      </div>
      <div className="text-[11px] text-gray-500">
        {flag.period_start} → {flag.period_end} · approved {flag.approved_hours}h · invoiced {flag.invoiced_hours}h
      </div>
      {error ? <div className="mt-1 text-[11px] text-rose-700">{error}</div> : null}
      {showReason ? (
        <div className="mt-2">
          <TextArea value={reason} onChange={setReason} placeholder="Reason (e.g. client-negotiated cap)" rows={2} />
          <Button variant="secondary" disabled={busy} onClick={handleLogReason} className="mt-2">
            Log Reason
          </Button>
        </div>
      ) : (
        <Button variant="ghost" onClick={() => setShowReason(true)} className="mt-1">
          Log Partial-Billing Reason
        </Button>
      )}
    </div>
  );
}

function ReconciliationAlertRow({ alert, onChanged }) {
  const [busy, setBusy] = useState(false);
  const handleResolve = async () => {
    setBusy(true);
    try {
      await resolveReconciliationAlert(alert.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex items-center justify-between rounded-lg border px-3 py-2 text-xs">
      <div>
        <div className="font-semibold text-gray-900">Timesheet {alert.timesheet_id}</div>
        <div className="text-gray-500">{alert.billable_hours}h billable, no invoice line item</div>
      </div>
      {alert.status === "UNRESOLVED" ? (
        <Button variant="secondary" disabled={busy} onClick={handleResolve}>
          Resolve
        </Button>
      ) : (
        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-emerald-800">RESOLVED</span>
      )}
    </div>
  );
}

function ClientDashboardPanel() {
  const [clientId, setClientId] = useState("");
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleLoad = async () => {
    if (!clientId.trim()) {
      setError("Client ID is required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await getClientRevenueDashboard(clientId.trim());
      setDashboard(res);
    } catch (err) {
      setError(err.message || "Failed to load dashboard.");
    } finally {
      setBusy(false);
    }
  };

  const formatUsdCents = (cents) =>
    cents == null ? "—" : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-end gap-2">
        <Input label="Client ID" value={clientId} onChange={setClientId} placeholder="client UUID" />
        <Button variant="primary" disabled={busy} onClick={handleLoad}>
          {busy ? "Loading…" : "Load Dashboard"}
        </Button>
      </div>
      {error ? <div className="mt-2 text-xs text-rose-700">{error}</div> : null}
      {dashboard ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border px-3 py-2">
            <div className="text-[11px] text-gray-500">Earned</div>
            <div className="text-lg font-semibold text-gray-900">{formatUsdCents(dashboard.earned_usd_cents)}</div>
          </div>
          <div className="rounded-lg border px-3 py-2">
            <div className="text-[11px] text-gray-500">Planned</div>
            <div className="text-lg font-semibold text-gray-900">{formatUsdCents(dashboard.planned_usd_cents)}</div>
          </div>
          <div className="rounded-lg border px-3 py-2">
            <div className="text-[11px] text-gray-500">Billable Ratio</div>
            <div className="text-lg font-semibold text-gray-900">{dashboard.billable_ratio_pct != null ? `${dashboard.billable_ratio_pct}%` : "—"}</div>
          </div>
          <div className="rounded-lg border px-3 py-2 sm:col-span-3">
            <div className="text-[11px] text-gray-500">Burn Rate (fixed-bid only)</div>
            <div className="text-lg font-semibold text-gray-900">{dashboard.burn_rate_pct != null ? `${dashboard.burn_rate_pct}%` : "N/A"}</div>
          </div>
          <div className="text-[11px] text-gray-400 sm:col-span-3">{dashboard.note}</div>
        </div>
      ) : null}
    </div>
  );
}

export default function RevenueScreen() {
  const [flags, setFlags] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [flagsRes, alertsRes] = await Promise.all([
        getActiveLeakageFlags(),
        getReconciliationAlerts("UNRESOLVED"),
      ]);
      setFlags(flagsRes?.flags || []);
      setAlerts(alertsRes?.alerts || []);
    } catch (err) {
      setError(err.message || "Failed to load revenue data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleScanReconciliation = async () => {
    try {
      await scanReconciliationGaps();
      load();
    } catch (err) {
      setError(err.message || "Failed to scan reconciliation gaps.");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Revenue Leakage Detection"
        subtitle="Compares approved billable hours against invoiced hours for a project+period. Only flags once the grace period has elapsed."
        icon={<AlertOctagon className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        <ScanLeakageForm onScanned={load} />
        <div className="mt-4 grid gap-2">
          {loading ? (
            <div className="py-4 text-center text-sm text-gray-500">Loading…</div>
          ) : flags.length === 0 ? (
            <div className="py-4 text-center text-sm text-gray-500">No active leakage flags.</div>
          ) : (
            flags.map((f) => <LeakageFlagRow key={f.id} flag={f} onChanged={load} />)
          )}
        </div>
      </Card>

      <Card
        title="Timesheet-to-Revenue Reconciliation"
        subtitle="Every approved timesheet past the grace period should have at least one invoice line item -- otherwise it's a gap."
        icon={<GitCompareArrows className="h-4 w-4" />}
        right={
          <Button variant="primary" onClick={handleScanReconciliation}>
            Scan for Gaps
          </Button>
        }
      >
        <div className="grid gap-2">
          {alerts.length === 0 ? (
            <div className="py-4 text-center text-sm text-gray-500">No unresolved reconciliation alerts.</div>
          ) : (
            alerts.map((a) => <ReconciliationAlertRow key={a.id} alert={a} onChanged={load} />)
          )}
        </div>
      </Card>

      <Card
        title="Client Revenue Realization Dashboard"
        subtitle="Internal only, estimate -- earned vs planned revenue and billable ratio for a client."
        icon={<LineChart className="h-4 w-4" />}
      >
        <ClientDashboardPanel />
      </Card>
    </div>
  );
}
