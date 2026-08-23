// S-353 (HRMS-0514) Core-Pull Engine + S-373 (HRMS-0529) Specialty Pool
// Minimum 40 Guard -- pending Core-Pull conflicts, execute/override, and
// the replacement-plan form that unblocks an execute the guard is
// holding back.
import { useEffect, useState } from "react";
import { ShieldAlert, RefreshCw, Zap, ShieldOff } from "lucide-react";
import { Card, Button, TextArea, Input } from "../components/ui";
import cx from "../utils/cx";
import {
  getSpecialtyPoolStatus,
  getPendingCorePullEvents,
  executeCorePullEvent,
  overrideCorePullEvent,
  submitReplacementPlan,
} from "../services/api/corePull";

function PoolStatusBanner({ status }) {
  if (!status) return null;
  const tone = status.below_minimum
    ? "border-rose-200 bg-rose-50 text-rose-700"
    : status.at_edge
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-emerald-200 bg-emerald-50 text-emerald-700";
  const label = status.below_minimum
    ? `Below the minimum of 40 -- gap of ${status.gap}.`
    : status.at_edge
      ? "One more move away from breaching the 40-minimum."
      : "Healthy -- above the 40-minimum floor.";
  return (
    <div className={cx("mx-5 mt-4 rounded-lg border px-3 py-2 text-sm", tone)}>
      <span className="font-semibold">Specialty pool: {status.pool_size} Core-Certified.</span>{" "}
      {label}
    </div>
  );
}

function ReplacementPlanForm({ employeeId, onSubmitted, onCancel }) {
  const [strategy, setStrategy] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (strategy.trim().length < 100) {
      setError("Replacement strategy must be at least 100 characters.");
      return;
    }
    if (!expectedDate) {
      setError("Expected replacement date is required.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await submitReplacementPlan({
        employeeId,
        replacementStrategy: strategy,
        expectedReplacementDate: expectedDate,
      });
      onSubmitted();
    } catch (err) {
      setError(err.message || "Failed to submit replacement plan.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
      <div className="mb-2 text-xs font-semibold text-amber-800">
        Log a replacement plan to unblock this move ({strategy.trim().length}/100 characters minimum)
      </div>
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <TextArea
        value={strategy}
        onChange={setStrategy}
        placeholder="Describe the replacement sourcing strategy..."
        rows={3}
      />
      <div className="mt-2 flex items-center gap-2">
        <Input
          type="date"
          value={expectedDate}
          onChange={setExpectedDate}
        />
        <Button variant="secondary" disabled={submitting} onClick={handleSubmit}>
          {submitting ? "Submitting…" : "Submit plan"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function OverrideForm({ onSubmit, onCancel, submitting }) {
  const [justification, setJustification] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = () => {
    if (justification.trim().length < 100) {
      setError("Justification must be at least 100 characters.");
      return;
    }
    setError("");
    onSubmit(justification);
  };

  return (
    <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
      <div className="mb-2 text-xs font-semibold text-gray-700">
        BU Head override justification ({justification.trim().length}/100 characters minimum)
      </div>
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <TextArea
        value={justification}
        onChange={setJustification}
        placeholder="Why should this Core-Pull be overridden?"
        rows={3}
      />
      <div className="mt-2 flex items-center gap-2">
        <Button variant="danger" disabled={submitting} onClick={handleSubmit}>
          {submitting ? "Submitting…" : "Confirm override"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export default function CorePullScreen() {
  const [poolStatus, setPoolStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [actioningId, setActioningId] = useState("");
  const [planFormForId, setPlanFormForId] = useState("");
  const [overrideFormForId, setOverrideFormForId] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [status, queue] = await Promise.all([
        getSpecialtyPoolStatus(),
        getPendingCorePullEvents(),
      ]);
      setPoolStatus(status);
      setEvents(queue?.events || []);
    } catch (err) {
      setError(err.message || "Failed to load Core-Pull data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleExecute = async (eventId) => {
    setActioningId(eventId);
    setError("");
    setNotice("");
    try {
      await executeCorePullEvent(eventId);
      setNotice("Core-Pull executed.");
      setPlanFormForId("");
      await load();
    } catch (err) {
      if (err.status === 409 && /minimum/i.test(err.message || "")) {
        setPlanFormForId(eventId);
      } else {
        setError(err.message || "Execute failed.");
      }
    } finally {
      setActioningId("");
    }
  };

  const handleOverride = async (eventId, justification) => {
    setActioningId(eventId);
    setError("");
    setNotice("");
    try {
      await overrideCorePullEvent(eventId, justification);
      setNotice("Core-Pull event overridden.");
      setOverrideFormForId("");
      await load();
    } catch (err) {
      setError(err.message || "Override failed.");
    } finally {
      setActioningId("");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Core-Pull Engine & Specialty Pool Guard"
        subtitle="Core-Certified employees deployed in Specialty who match an open Core demand. Executing pulls them onto Core the same day; the guard blocks a move that would drop the Specialty pool below 40 unless a replacement plan is logged."
        icon={<ShieldAlert className="h-4 w-4" />}
        right={
          <Button variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
        bodyClassName="p-0"
      >
        <PoolStatusBanner status={poolStatus} />

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
          ) : events.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">
              No pending Core-Pull conflicts.
            </div>
          ) : (
            <div className="grid gap-3">
              {events.map((e) => (
                <div key={e.id} className="rounded-2xl border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="font-semibold text-gray-900">{e.employee_name}</div>
                      <div className="text-xs text-gray-500">
                        → {e.core_demand_job_title}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="primary"
                        disabled={actioningId === e.id}
                        onClick={() => handleExecute(e.id)}
                      >
                        <Zap className="h-4 w-4" /> Execute
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={actioningId === e.id}
                        onClick={() =>
                          setOverrideFormForId(overrideFormForId === e.id ? "" : e.id)
                        }
                      >
                        <ShieldOff className="h-4 w-4" /> Override
                      </Button>
                    </div>
                  </div>

                  {planFormForId === e.id ? (
                    <ReplacementPlanForm
                      employeeId={e.employee_id}
                      onSubmitted={() => {
                        setPlanFormForId("");
                        setNotice("Replacement plan logged -- click Execute again to proceed.");
                        load();
                      }}
                      onCancel={() => setPlanFormForId("")}
                    />
                  ) : null}

                  {overrideFormForId === e.id ? (
                    <OverrideForm
                      submitting={actioningId === e.id}
                      onSubmit={(justification) => handleOverride(e.id, justification)}
                      onCancel={() => setOverrideFormForId("")}
                    />
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
