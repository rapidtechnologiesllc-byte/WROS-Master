// S-359/HRMS-P511 -- HTD Intake Pause Engine: Conversion Rate Breach.
// A 2-consecutive-month conversion rate below 50% auto-pauses new HTD
// intake. Resuming requires 200+ char audit findings AND corrective
// actions -- no shortcut button.
import { useEffect, useState } from "react";
import { AlertOctagon, RefreshCw, Calculator, ShieldCheck, History } from "lucide-react";
import { Card, Button, Input, TextArea } from "../components/ui";
import cx from "../utils/cx";
import {
  calculateMonthlyMetric,
  checkHtdBreach,
  getHtdIntakeStatus,
  resumeHtdIntake,
  getHtdPauseLog,
} from "../services/api/htdIntake";

function ResumeForm({ onResumed }) {
  const [auditFindings, setAuditFindings] = useState("");
  const [correctiveActions, setCorrectiveActions] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async () => {
    if (auditFindings.trim().length < 200 || correctiveActions.trim().length < 200) {
      setError("Both audit findings and corrective actions must be at least 200 characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await resumeHtdIntake(auditFindings.trim(), correctiveActions.trim());
      onResumed();
    } catch (err) {
      setError(err.message || "Failed to resume intake.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 rounded-xl border border-rose-200 bg-white p-3">
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <TextArea
        label={`Audit Findings (${auditFindings.length}/200 min)`}
        value={auditFindings}
        onChange={setAuditFindings}
        placeholder="What went wrong with the HTD pipeline this period?"
        rows={4}
      />
      <div className="mt-2">
        <TextArea
          label={`Corrective Actions (${correctiveActions.length}/200 min)`}
          value={correctiveActions}
          onChange={setCorrectiveActions}
          placeholder="What has been fixed before resuming intake?"
          rows={4}
        />
      </div>
      <Button variant="danger" disabled={busy} onClick={handleSubmit} className="mt-3">
        {busy ? "Resuming…" : "Re-enable HTD Intake"}
      </Button>
    </div>
  );
}

export default function HtdIntakeScreen() {
  const [status, setStatus] = useState(null);
  const [pauseLog, setPauseLog] = useState([]);
  const [month, setMonth] = useState("");
  const [lastMetric, setLastMetric] = useState(null);
  const [showResumeForm, setShowResumeForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [statusRes, logRes] = await Promise.all([getHtdIntakeStatus(), getHtdPauseLog()]);
      setStatus(statusRes);
      setPauseLog(logRes.entries || []);
    } catch (err) {
      setError(err.message || "Failed to load HTD intake status.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCalculate = async () => {
    if (!month) {
      setError("Pick a month first.");
      return;
    }
    setError("");
    setNotice("");
    try {
      const metric = await calculateMonthlyMetric(`${month}-01`);
      setLastMetric(metric);
      setNotice(`Calculated: ${metric.cohort_size} cohort, ${metric.converted} converted${metric.conversion_rate != null ? ` (${(metric.conversion_rate * 100).toFixed(1)}%)` : " -- insufficient data"}.`);
    } catch (err) {
      setError(err.message || "Failed to calculate metric.");
    }
  };

  const handleCheckBreach = async () => {
    setError("");
    try {
      await checkHtdBreach();
      load();
    } catch (err) {
      setError(err.message || "Failed to check breach.");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="HTD Intake Pause Engine"
        subtitle="Monthly HTD-to-Core conversion rate monitor. Two consecutive months below 50% auto-pauses new intake until BU Head resumes with a documented audit."
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
        {notice ? (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</div>
        ) : null}

        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : status?.is_paused ? (
          <div className="rounded-xl border border-rose-300 bg-rose-50 p-4">
            <div className="flex items-center gap-2 font-semibold text-rose-800">
              <AlertOctagon className="h-5 w-5" /> HTD INTAKE PAUSED
            </div>
            <div className="mt-1 text-sm text-rose-700">{status.pause_reason}</div>
            <div className="mt-1 text-xs text-rose-500">
              Paused {status.paused_at ? new Date(status.paused_at).toLocaleString() : "—"}
            </div>
            <Button variant="danger" onClick={() => setShowResumeForm((v) => !v)} className="mt-3">
              <ShieldCheck className="h-4 w-4" /> {showResumeForm ? "Cancel" : "Review Audit & Re-enable"}
            </Button>
            {showResumeForm ? <ResumeForm onResumed={() => { setShowResumeForm(false); load(); }} /> : null}
          </div>
        ) : (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-800">
            HTD intake is active -- no breach detected.
          </div>
        )}

        <div className="mt-4 rounded-xl border p-3">
          <div className="mb-2 flex items-center gap-1 text-sm font-semibold text-gray-700">
            <Calculator className="h-4 w-4" /> Calculate Monthly Conversion Rate
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Input label="Month" type="month" value={month} onChange={setMonth} />
            <Button variant="secondary" onClick={handleCalculate}>
              Calculate
            </Button>
            <Button variant="primary" onClick={handleCheckBreach}>
              Check Breach (last 2 months)
            </Button>
          </div>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center gap-1 text-sm font-semibold text-gray-700">
            <History className="h-4 w-4" /> Pause/Resume Audit Log
          </div>
          {pauseLog.length === 0 ? (
            <div className="text-xs text-gray-500">No pause/resume events recorded.</div>
          ) : (
            <ul className="space-y-2">
              {pauseLog.map((e) => (
                <li key={e.id} className="rounded-lg border px-3 py-2 text-xs">
                  <span className={cx("font-semibold", e.action === "PAUSED" ? "text-rose-700" : "text-emerald-700")}>
                    {e.action}
                  </span>
                  <span className="text-gray-500"> · {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}</span>
                  {e.reason ? <div className="mt-1 text-gray-700">{e.reason}</div> : null}
                  {e.audit_findings ? <div className="mt-1 text-gray-600">Audit: {e.audit_findings}</div> : null}
                  {e.corrective_actions ? <div className="mt-1 text-gray-600">Corrective: {e.corrective_actions}</div> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}
