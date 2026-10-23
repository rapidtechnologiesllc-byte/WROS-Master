// Client > Billing setup and Client > Work Orders (CEO 2026-10-23, gaps 3 and 12).
// Billing setup: does the client approve its own timesheets (emailed link / VMS evidence) before
// they are invoiced, its payment terms (every invoice's due date), and per placement the client's
// timesheet approver and the PO it bills against. Work Orders: the client's POs -- the PO number
// is printed on the invoice and hours after a PO's end date are not invoiced.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Input, Select } from "./ui";
import { updateClient } from "../services/api/clients";
import { getAllocationDropdowns, getAllocations, setPlacementBilling } from "../services/api/allocations";
import { changeWorkOrderStatus, createWorkOrder, listWorkOrders, updateWorkOrder } from "../services/api/workOrders";

const money = (cents) => (cents == null ? "—" : `$${(cents / 100).toFixed(2)}`);

function ErrorLine({ text }) {
  return text ? <div className="mb-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{text}</div> : null;
}

function PlacementRow({ placement, approverOptions, poOptions, onSaved }) {
  const [approver, setApprover] = useState(placement.timesheet_approver_email || "");
  const [po, setPo] = useState(placement.work_order_id || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = approver !== (placement.timesheet_approver_email || "") || po !== (placement.work_order_id || "");

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await setPlacementBilling(placement.id, { timesheetApproverEmail: approver, workOrderId: po });
      onSaved();
    } catch (err) {
      setError(err.message || "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
      <div className="mb-2 text-sm font-medium text-gray-900">
        {placement.employee_name} · {placement.demand_job_title}
        <span className="ml-2 text-xs text-gray-500">{placement.status}</span>
      </div>
      <ErrorLine text={error} />
      <div className="grid gap-2 sm:grid-cols-2">
        {approverOptions.length ? (
          <Select label="Client timesheet approver" value={approver} onChange={setApprover}
            options={[{ value: "", label: "None" }, ...approverOptions]} />
        ) : (
          <Input label="Client timesheet approver email" value={approver} onChange={setApprover}
            placeholder="add TIMESHEET_APPROVER contacts to pick one" />
        )}
        <Select label="Client PO (work order)" value={po} onChange={setPo}
          options={[{ value: "", label: "None" }, ...poOptions]} />
      </div>
      {dirty ? (
        <Button className="mt-2" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
      ) : null}
    </div>
  );
}

export function BillingSetupPanel({ client, contacts, onClientChanged }) {
  const [requires, setRequires] = useState(Boolean(client.requires_client_timesheet_approval));
  const [terms, setTerms] = useState(String(client.payment_terms_days ?? ""));
  const [placements, setPlacements] = useState(null);
  const [workOrders, setWorkOrders] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      setPlacements(await getAllocations({ clientId: client.id }));
    } catch (err) {
      setPlacements([]);
      setError(err.message || "Could not load placements.");
    }
    try {
      setWorkOrders(await listWorkOrders({ clientId: client.id }));
    } catch (err) {
      setError(`Could not load work orders: ${err.message}`);
    }
  }, [client.id]);

  useEffect(() => {
    load();
  }, [load]);

  const saveClient = async () => {
    const days = Number(terms);
    if (!Number.isInteger(days) || days < 0) {
      setError("Payment terms must be a whole number of days.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await updateClient(client.id, { requires_client_timesheet_approval: requires, payment_terms_days: days });
      onClientChanged();
    } catch (err) {
      setError(err.message || "Could not save.");
    } finally {
      setSaving(false);
    }
  };

  const approverOptions = useMemo(() => (contacts || [])
    .filter((c) => c.role_type === "TIMESHEET_APPROVER")
    .map((c) => ({ value: c.email.toLowerCase(), label: `${c.name} (${c.email})` })), [contacts]);
  const poOptions = useMemo(() => workOrders
    .filter((w) => w.status !== "ENDED")
    .map((w) => ({ value: w.id, label: `${w.po_number}${w.end_date ? ` (ends ${w.end_date})` : ""}` })), [workOrders]);

  return (
    <div className="space-y-4">
      <ErrorLine text={error} />
      <div className="rounded-xl border border-gray-200 p-4">
        <label className="flex items-center gap-2 text-sm text-gray-800">
          <input type="checkbox" checked={requires} onChange={(e) => setRequires(e.target.checked)} />
          The client approves its own timesheets before they are invoiced
        </label>
        <div className="mt-1 text-xs text-gray-500">
          After the internal approval the client's approver is emailed a link to approve or reject the week,
          or you upload the client's approved timesheet (VMS export). Invoices wait for it.
        </div>
        <div className="mt-3 max-w-xs">
          <Input label="Payment terms (days)" type="number" value={terms} onChange={setTerms} />
        </div>
        <Button className="mt-3" onClick={saveClient} disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Placements</div>
        {placements === null ? (
          <div className="text-sm text-gray-400">Loading placements…</div>
        ) : placements.length === 0 ? (
          <div className="text-sm text-gray-400">No placements at this client yet.</div>
        ) : (
          <div className="space-y-2">
            {placements.map((p) => (
              <PlacementRow key={`${p.id}-${p.timesheet_approver_email}-${p.work_order_id}`} placement={p}
                approverOptions={approverOptions} poOptions={poOptions} onSaved={load} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function WorkOrderRow({ workOrder, onChanged }) {
  const [endDate, setEndDate] = useState(workOrder.end_date || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-medium text-gray-900">PO {workOrder.po_number}</div>
        <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-semibold text-gray-700">{workOrder.status}</span>
      </div>
      <div className="mt-1 text-xs text-gray-500">
        {workOrder.start_date} → {workOrder.end_date || "open-ended"} · bill rate {money(workOrder.billing_rate_usd_cents)}/h ·{" "}
        {workOrder.placement_count} placement(s)
      </div>
      <ErrorLine text={error} />
      {workOrder.status !== "ENDED" ? (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <Input label="End date" type="date" value={endDate} onChange={setEndDate} />
          <Button variant="ghost" disabled={busy || !endDate || endDate === workOrder.end_date}
            onClick={() => run(() => updateWorkOrder(workOrder.id, { end_date: endDate }))}>Save end date</Button>
          {workOrder.status === "ACTIVE" ? (
            <Button variant="ghost" disabled={busy} onClick={() => run(() => changeWorkOrderStatus(workOrder.id, "pause"))}>Pause</Button>
          ) : (
            <Button variant="ghost" disabled={busy} onClick={() => run(() => changeWorkOrderStatus(workOrder.id, "resume"))}>Resume</Button>
          )}
          <Button variant="ghost" disabled={busy} onClick={() => run(() => changeWorkOrderStatus(workOrder.id, "end", endDate))}>End</Button>
        </div>
      ) : null}
    </div>
  );
}

const emptyWorkOrder = { po_number: "", demand_id: "", bill_rate: "", start_date: "", end_date: "", sow_reference: "" };

export function WorkOrdersPanel({ client }) {
  const [workOrders, setWorkOrders] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [form, setForm] = useState(emptyWorkOrder);
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setWorkOrders(await listWorkOrders({ clientId: client.id }));
    } catch (err) {
      setWorkOrders([]);
      setError(err.message || "Could not load work orders.");
    }
  }, [client.id]);

  useEffect(() => {
    load();
    getAllocationDropdowns()
      .then((data) => setJobs((data?.demands || []).filter((j) => j.client_id === client.id)))
      .catch((err) => setError(`Could not load the client's jobs: ${err.message}`));
  }, [load, client.id]);

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));
  const pickJob = (id) => {
    const job = jobs.find((j) => j.id === id);
    setForm((f) => ({
      ...f, demand_id: id,
      bill_rate: f.bill_rate || (job?.billing_rate_usd_cents ? String(job.billing_rate_usd_cents / 100) : ""),
    }));
  };

  const save = async () => {
    if (!form.po_number.trim() || !form.demand_id || !form.bill_rate || !form.start_date) {
      setError("PO number, job, bill rate and start date are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const job = jobs.find((j) => j.id === form.demand_id);
      await createWorkOrder({
        po_number: form.po_number.trim(), demand_id: form.demand_id, client_id: client.id,
        project_id: job?.project_id || undefined,
        billing_rate_usd_cents: Math.round(parseFloat(form.bill_rate) * 100), start_date: form.start_date,
        end_date: form.end_date || undefined, sow_reference: form.sow_reference || undefined,
      });
      setForm(emptyWorkOrder);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.message || "Could not create the work order.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <ErrorLine text={error} />
      <div className="flex justify-end">
        <Button variant="ghost" onClick={() => setShowAdd((v) => !v)}>{showAdd ? "Cancel" : "Add work order"}</Button>
      </div>
      {showAdd ? (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <Input label="PO number *" value={form.po_number} onChange={set("po_number")} />
            <Select label="Job *" value={form.demand_id} onChange={pickJob}
              options={[{ value: "", label: jobs.length ? "Select job" : "No open jobs for this client" },
                ...jobs.map((j) => ({ value: j.id, label: j.name }))]} />
            <Input label="Bill rate (USD / hour) *" type="number" value={form.bill_rate} onChange={set("bill_rate")} />
            <Input label="SOW reference" value={form.sow_reference} onChange={set("sow_reference")} />
            <Input label="Start date *" type="date" value={form.start_date} onChange={set("start_date")} />
            <Input label="End date" type="date" value={form.end_date} onChange={set("end_date")} />
          </div>
          <Button className="mt-2" onClick={save} disabled={saving}>{saving ? "Saving…" : "Create"}</Button>
        </div>
      ) : null}
      {workOrders === null ? (
        <div className="text-sm text-gray-400">Loading work orders…</div>
      ) : workOrders.length === 0 ? (
        <div className="text-sm text-gray-400">No work orders yet.</div>
      ) : (
        <div className="space-y-2">
          {workOrders.map((w) => <WorkOrderRow key={`${w.id}-${w.status}-${w.end_date}`} workOrder={w} onChanged={load} />)}
        </div>
      )}
    </div>
  );
}
