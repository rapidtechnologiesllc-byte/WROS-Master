// Extend / edit an allocation (CEO 2026-10-23): new end date (extend or shorten), bill rate (from a
// Monday: billed weeks keep their rate), utilization, billable -- always with a reason, kept in
// the allocation's history. The live margin line shows the rate card's verdict; below the floor
// the change waits for a BU Head / Partner and the current terms continue meanwhile. A pending
// placement or change can be approved or rejected here by whoever the server allows.
import { useEffect, useState } from "react";
import { Button, Input, Select, TextArea } from "./ui";
import { MarginLine, marginLabel, useMarginPreview } from "./AllocationMargin";
import { decideMarginChange, getAllocationHistory, updateAllocation } from "../services/api/allocations";

const dollars = (cents) => (cents == null ? "" : String(cents / 100));
const FIELD_LABELS = {
  end_date: "End date", billing_rate_usd_cents: "Bill rate", utilization_pct: "Utilization %", billable: "Billable",
  renewal_status: "Renewal status", renewal_owner_user_id: "Renewal owner", renewal_note: "Renewal note",
};

const show = (key, value) => {
  if (value == null || value === "") return "—";
  if (key === "billing_rate_usd_cents") return `$${(value / 100).toFixed(2)}/h`;
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
};

function History({ allocationId, refreshKey }) {
  const [changes, setChanges] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getAllocationHistory(allocationId)
      .then(setChanges)
      .catch((err) => setError(`Could not load the history: ${err.message}`));
  }, [allocationId, refreshKey]);
  if (error) return <div className="text-xs text-rose-700">{error}</div>;
  if (!changes) return <div className="text-xs text-gray-500">Loading history…</div>;
  return (
    <ul className="max-h-48 space-y-1 overflow-y-auto text-xs">
      {changes.map((c) => (
        <li key={c.id} className="rounded border bg-white px-2 py-1">
          <div className="font-semibold text-gray-800">
            {c.change_type} · {c.status.replace(/_/g, " ").toLowerCase()} · {c.changed_by_name || "system"} ·{" "}
            {c.changed_at ? new Date(c.changed_at).toLocaleString() : ""}
          </div>
          {Object.keys(c.new_values || {}).filter((k) => FIELD_LABELS[k]).map((k) => (
            <div key={k} className="text-gray-600">
              {FIELD_LABELS[k]}: {show(k, c.old_values?.[k])} → {show(k, c.new_values[k])}
              {k === "billing_rate_usd_cents" && c.effective_from ? ` from ${c.effective_from}` : ""}
            </div>
          ))}
          <div className="text-gray-500">Why: {c.reason}</div>
          {c.margin_check && <div className="text-gray-500">Margin {marginLabel(c.margin_pct)} ({c.margin_check})</div>}
          {c.decision_reason && <div className="text-gray-500">Decision: {c.decision_reason}</div>}
        </li>
      ))}
    </ul>
  );
}

function PendingDecision({ change, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const decide = async (approve) => {
    setBusy(true);
    setError("");
    try {
      await decideMarginChange(change.id, approve, reason);
      onDone();
    } catch (err) {
      setError(err.message || "Decision failed.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
      <div className="font-semibold">
        Waiting for margin approval ({change.approval_level === "PARTNER" ? "Partner" : "BU Head"}
        {change.approver_name ? `: ${change.approver_name}` : ""}) -- margin {marginLabel(change.margin_pct)}
      </div>
      <div>Requested by {change.changed_by_name || "—"}: {change.reason}</div>
      {error && <div className="mt-1 text-rose-700">{error}</div>}
      <div className="mt-2">
        <TextArea label="Decision reason" value={reason} onChange={setReason} rows={2} />
      </div>
      <div className="mt-2 flex gap-2">
        <Button variant="primary" size="sm" disabled={busy} onClick={() => decide(true)}>Approve</Button>
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => decide(false)}>Reject</Button>
      </div>
    </div>
  );
}

export default function AllocationEditModal({ allocation, mode = "edit", onClose, onSaved }) {
  const [endDate, setEndDate] = useState(allocation.end_date || "");
  const [billRate, setBillRate] = useState(dollars(allocation.billing_rate_usd_cents));
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [utilization, setUtilization] = useState(allocation.utilization_pct != null ? String(allocation.utilization_pct) : "");
  const [billable, setBillable] = useState(allocation.billable === false ? "no" : "yes");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const rateCents = billRate ? Math.round(parseFloat(billRate) * 100) : null;
  const active = allocation.status === "ACTIVE";
  const { margin, error: marginError } = useMarginPreview({
    allocationId: allocation.id,
    billingRateUsdCents: rateCents || undefined,
    billable: billable === "yes",
    startDate: effectiveFrom || undefined,
  }, active);

  const changes = () => {
    const out = {};
    if ((endDate || null) !== (allocation.end_date || null)) out.end_date = endDate || null;
    if (rateCents && rateCents !== allocation.billing_rate_usd_cents) out.billing_rate_usd_cents = rateCents;
    if (utilization && Number(utilization) !== Number(allocation.utilization_pct ?? NaN)) {
      out.utilization_pct = Number(utilization);
    }
    if ((billable === "yes") !== (allocation.billable !== false)) out.billable = billable === "yes";
    return out;
  };

  const save = async () => {
    const fields = changes();
    if (!Object.keys(fields).length) {
      setError("Change at least one value.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await updateAllocation(allocation.id, { ...fields, reason, effectiveFrom: effectiveFrom || undefined });
      setRefreshKey((k) => k + 1);
      if (result.change.status === "PENDING_APPROVAL") {
        setNotice("Below the margin floor: the change is waiting for approval; the current terms continue meanwhile.");
      }
      onSaved(result.allocation);
      if (result.change.status !== "PENDING_APPROVAL") onClose();
    } catch (err) {
      setError(err.message || "The change was blocked.");
    } finally {
      setSaving(false);
    }
  };

  const decided = () => {
    setRefreshKey((k) => k + 1);
    onSaved();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
        <div className="mb-1 text-lg font-semibold text-gray-900">
          {mode === "extend" ? "Extend" : "Edit"} allocation: {allocation.employee_name}
        </div>
        <div className="mb-3 text-xs text-gray-500">
          {allocation.client_name} · {allocation.demand_job_title || allocation.job_title} · from {allocation.start_date}
          {" "}· status {allocation.status.replace(/_/g, " ").toLowerCase()}
        </div>
        {error && <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
        {notice && <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{notice}</div>}
        {allocation.pending_change && (
          <div className="mb-3"><PendingDecision change={allocation.pending_change} onDone={decided} /></div>
        )}
        {active && !allocation.pending_change && (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="End date (empty = open-ended)" type="date" value={endDate} onChange={setEndDate} />
              <Input label="Bill rate (USD / hour)" type="number" value={billRate} onChange={setBillRate} />
              <Input label="New rate applies from (a Monday; default: first unbilled week)" type="date"
                value={effectiveFrom} onChange={setEffectiveFrom} />
              {mode !== "extend" && (
                <Input label="Utilization %" type="number" value={utilization} onChange={setUtilization} />
              )}
              {mode !== "extend" && (
                <Select label="Billable time?" value={billable} onChange={setBillable}
                  options={[{ value: "yes", label: "Billable" }, { value: "no", label: "Non-billable (never invoiced)" }]} />
              )}
            </div>
            <MarginLine margin={margin} error={marginError} />
            <div className="mt-3">
              <TextArea label="Reason (kept in the history)" value={reason} onChange={setReason} rows={2}
                placeholder="e.g. Client extended the SOW by six months at the same rate" />
            </div>
            <div className="mt-4 flex gap-2">
              <Button variant="primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save change"}</Button>
              <Button variant="ghost" onClick={onClose} disabled={saving}>Cancel</Button>
            </div>
          </>
        )}
        {(!active || allocation.pending_change) && (
          <div className="mt-2"><Button variant="ghost" onClick={onClose}>Close</Button></div>
        )}
        <div className="mt-4 border-t pt-3">
          <div className="mb-2 text-sm font-semibold text-gray-800">History</div>
          <History allocationId={allocation.id} refreshKey={refreshKey} />
        </div>
      </div>
    </div>
  );
}
