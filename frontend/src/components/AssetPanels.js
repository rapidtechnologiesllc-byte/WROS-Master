// Shared pieces of the asset ledger: status chips, the one-action forms (issue, ship back, receive, report a
// defect...) and the item's history. Used by the Asset Ledger screen and the employee's Assets tab.
import { useState } from "react";
import { Button, Input, Select, TextArea } from "./ui";
import cx from "../utils/cx";
import {
  confirmAssetReceipt,
  confirmOwnerReceived,
  issueAsset,
  markAssetLost,
  receiveAssetReturn,
  recordReturnShipment,
  reportAssetDefect,
  requestAssetReturn,
  retireAsset,
  returnAssetToOwner,
  titleCase,
  updateAssetDefect,
} from "../services/api/assets";

// A live item is in the office or with an employee (CEO 2026-11-23); a courier or a repair shop is a flag
const STATUS_STYLE = {
  IN_STOCK: "border-emerald-200 bg-emerald-50 text-emerald-800",
  ASSIGNED: "border-blue-200 bg-blue-50 text-blue-800",
  LOST: "border-rose-200 bg-rose-50 text-rose-800",
  RETIRED: "border-gray-200 bg-gray-100 text-gray-600",
  RETURNED_TO_OWNER: "border-gray-200 bg-gray-100 text-gray-600",
};
const SEVERITY_STYLE = {
  HIGH: "border-rose-200 bg-rose-50 text-rose-800",
  MEDIUM: "border-amber-200 bg-amber-50 text-amber-800",
  LOW: "border-gray-200 bg-gray-50 text-gray-700",
};

export function Chip({ tone, children }) {
  return <span className={cx("inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold", tone)}>{children}</span>;
}

const STATUS_TEXT = {
  IN_STOCK: "In office", ASSIGNED: "With employee", LOST: "Lost", RETIRED: "Retired", RETURNED_TO_OWNER: "Returned to owner",
};
export const StatusChip = ({ status }) => <Chip tone={STATUS_STYLE[status]}>{STATUS_TEXT[status] || titleCase(status)}</Chip>;

export function PlaceChips({ asset }) {
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      <StatusChip status={asset.status} />
      {asset.in_transit ? <Chip tone="border-amber-200 bg-amber-50 text-amber-800">With courier</Chip> : null}
      {asset.in_repair ? <Chip tone="border-orange-200 bg-orange-50 text-orange-800">At repair shop</Chip> : null}
    </span>
  );
}

// Times come from the server marked as UTC: shown as the viewer's own date
export const localDay = (value) => (value ? new Date(value).toLocaleDateString() : "");
const when = (value) => localDay(value) || "—";
const METHOD_TEXT = { HAND: "In person", COURIER: "Courier", OWN_DEVICE: "Own device" };
const OUTCOME_TEXT = { RETURNED: "Checked in", LOST: "Lost", RELEASED: "Left with them" };

// The check-out / check-in register: one row per spell with an employee. showAsset: the employee's view.
export function CheckoutRegister({ rows, showAsset }) {
  if (!rows?.length) return <div className="text-sm text-gray-500">Never checked out.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b text-xs uppercase tracking-wide text-gray-500">
          <tr>
            <th className="py-2 pr-3">{showAsset ? "Item" : "Employee"}</th>
            <th className="py-2 pr-3">Checked out</th><th className="py-2 pr-3">How</th>
            <th className="py-2 pr-3">Checked in</th><th className="py-2 pr-3">Condition</th><th className="py-2">Days</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b align-top last:border-0">
              <td className="py-2 pr-3 font-medium text-gray-900">{showAsset ? row.asset_label : row.employee_name}</td>
              <td className="py-2 pr-3 text-gray-700">{when(row.checked_out_at)}
                {row.checked_out_by ? <div className="text-xs text-gray-500">by {row.checked_out_by}</div> : null}</td>
              <td className="py-2 pr-3 text-gray-700">{METHOD_TEXT[row.method] || row.method}
                {row.received_on ? <div className="text-xs text-gray-500">arrived {row.received_on}</div> : null}</td>
              <td className="py-2 pr-3 text-gray-700">
                {row.open ? <Chip tone="border-blue-200 bg-blue-50 text-blue-800">Still out</Chip> : (
                  <>{when(row.checked_in_at)} · {OUTCOME_TEXT[row.outcome] || row.outcome}
                    {row.checked_in_by ? <div className="text-xs text-gray-500">by {row.checked_in_by}</div> : null}</>
                )}
                {row.note ? <div className="text-xs text-gray-500">{row.note}</div> : null}</td>
              <td className="py-2 pr-3 text-gray-700">{titleCase(row.condition_out)}{row.condition_in ? ` → ${titleCase(row.condition_in)}` : ""}</td>
              <td className="py-2 text-gray-700">{row.days ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export const SeverityChip = ({ severity }) => <Chip tone={SEVERITY_STYLE[severity]}>{titleCase(severity)}</Chip>;

// The person's own calendar date (toISOString is UTC: in the evening it is already tomorrow)
const today = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

function ActionForm({ title, submitLabel, onSubmit, onCancel, children, danger }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await onSubmit();
    } catch (err) {
      setError(err.message || "That did not work.");
      setBusy(false);
    }
  };
  return (
    <div className="space-y-3 rounded-xl border bg-gray-50 p-4">
      <div className="text-sm font-semibold text-gray-900">{title}</div>
      {children}
      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">{error}</div> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} onClick={submit} disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
      </div>
    </div>
  );
}

function CourierFields({ value, onChange, withExpected = true }) {
  const set = (key) => (v) => onChange({ ...value, [key]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Input label="Courier" value={value.carrier} onChange={set("carrier")} placeholder="Blue Dart, FedEx, DHL…" />
      <Input label="Tracking number" value={value.tracking_number} onChange={set("tracking_number")} />
      <Input label="Shipped on" type="date" value={value.shipped_on} onChange={set("shipped_on")} />
      {withExpected ? <Input label="Expected delivery" type="date" value={value.expected_on} onChange={set("expected_on")} /> : null}
    </div>
  );
}

const courierBody = (c) => ({
  carrier: c.carrier, tracking_number: c.tracking_number, shipped_on: c.shipped_on || null, expected_on: c.expected_on || null,
});

// What can be done with this item now, for this viewer. manage: IT Admin (assets.edit); holder: it is theirs.
export function availableActions(asset, { manage, holder }) {
  const actions = [];
  const held = asset.status === "ASSIGNED";
  const ours = asset.owner_type !== "PERSONAL";
  const inbound = asset.shipment && asset.shipment.direction === "TO_EMPLOYEE";
  if (held && inbound && (manage || holder)) actions.push(["receipt", "Confirm received"]);
  if (held && ours && !asset.shipment && (manage || holder)) actions.push(["ship_back", "Send it back"]);
  if (manage) {
    if (asset.status === "IN_STOCK" && !asset.in_repair) actions.push(["issue", "Check out to employee"]);
    if (held && ours && !inbound) actions.push(["receive", "Check in"]);
    if (held && ours && !asset.return_due) actions.push(["request", "Ask it back"]);
    if (asset.status === "IN_STOCK" && (asset.owner_type === "CLIENT" || asset.owner_type === "LEASED")) actions.push(["to_owner", "Return to owner"]);
    if (asset.status === "RETURNED_TO_OWNER" && asset.shipment && asset.shipment.direction === "TO_OWNER") actions.push(["owner_received", "Owner received it"]);
  }
  if (!["LOST", "RETIRED", "RETURNED_TO_OWNER"].includes(asset.status) && (manage || holder)) actions.push(["defect", "Report a defect"]);
  if (manage && !["LOST", "RETIRED", "RETURNED_TO_OWNER"].includes(asset.status)) actions.push(["lost", "Mark lost"]);
  if (manage && ["IN_STOCK", "LOST"].includes(asset.status)) actions.push(["retire", "Retire"]);
  return actions;
}

// One action's form. onDone(updatedAsset) after a success.
export function AssetActionForm({ action, asset, options, onDone, onCancel }) {
  const [courier, setCourier] = useState({ carrier: "", tracking_number: "", shipped_on: today(), expected_on: "" });
  const [form, setForm] = useState({
    employee_id: "", method: "HAND", project_id: "", condition: "GOOD", note: "", description: "", severity: "MEDIUM",
    due_date: today(), reason: "RECALL", received_on: today(),
  });
  const set = (key) => (value) => setForm((prev) => ({ ...prev, [key]: value }));
  const employees = (options?.employees || []).map((e) => ({ value: e.id, label: e.name }));
  const projects = [{ value: "", label: "Not for a project" },
    ...(options?.projects || []).map((p) => ({ value: p.id, label: p.name }))];
  const conditions = (options?.conditions || ["NEW", "GOOD", "FAIR", "DAMAGED"]).map((c) => ({ value: c, label: titleCase(c) }));
  const run = (call) => async () => onDone(await call());

  if (action === "issue") {
    return (
      <ActionForm title={`Check out ${asset.asset_tag}`} submitLabel="Check out" onCancel={onCancel}
        onSubmit={run(() => issueAsset(asset.id, {
          employee_id: form.employee_id, method: form.method, project_id: form.project_id || null,
          ...(form.method === "COURIER" ? courierBody(courier) : {}),
        }))}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Employee" value={form.employee_id} onChange={set("employee_id")} options={employees} />
          <Select label="Project (its kit comes back when it ends)" value={form.project_id} onChange={set("project_id")} options={projects} />
          <Select label="Handover" value={form.method} onChange={set("method")}
            options={[{ value: "HAND", label: "In person" }, { value: "COURIER", label: "By courier" }]} />
        </div>
        {form.method === "COURIER" ? <CourierFields value={courier} onChange={setCourier} /> : null}
      </ActionForm>
    );
  }
  if (action === "receipt" || action === "owner_received") {
    const call = action === "receipt" ? confirmAssetReceipt : confirmOwnerReceived;
    return (
      <ActionForm title={action === "receipt" ? `Confirm ${asset.asset_tag} arrived` : "The owner confirmed receipt"}
        submitLabel="Confirm" onCancel={onCancel} onSubmit={run(() => call(asset.id, { received_on: form.received_on }))}>
        <Input label="Received on" type="date" value={form.received_on} onChange={set("received_on")} />
      </ActionForm>
    );
  }
  if (action === "ship_back") {
    return (
      <ActionForm title={`Send ${asset.asset_tag} back`} submitLabel="Save tracking" onCancel={onCancel}
        onSubmit={run(() => recordReturnShipment(asset.id, courierBody(courier)))}>
        <p className="text-xs text-gray-500">Enter the courier and tracking number. Handing it over in person? IT Admin checks it in directly.</p>
        <CourierFields value={courier} onChange={setCourier} />
      </ActionForm>
    );
  }
  if (action === "receive") {
    return (
      <ActionForm title={`Check ${asset.asset_tag} in to the office`} submitLabel="Check in" onCancel={onCancel}
        onSubmit={run(() => receiveAssetReturn(asset.id, { condition: form.condition, received_on: form.received_on, note: form.note || null }))}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Condition" value={form.condition} onChange={set("condition")} options={conditions} />
          <Input label="Received on" type="date" value={form.received_on} onChange={set("received_on")} />
        </div>
        <TextArea label="Note (damage, missing charger…)" value={form.note} onChange={set("note")} rows={2} />
      </ActionForm>
    );
  }
  if (action === "request") {
    const reasons = (options?.return_reasons || ["RECALL", "PROJECT_END"]).map((r) => ({ value: r, label: titleCase(r) }));
    return (
      <ActionForm title={`Ask ${asset.holder_name || "the holder"} to return ${asset.asset_tag}`} submitLabel="Ask it back"
        onCancel={onCancel}
        onSubmit={run(() => requestAssetReturn(asset.id, { due_date: form.due_date, reason: form.reason, note: form.note || null }))}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Due back by" type="date" value={form.due_date} onChange={set("due_date")} />
          <Select label="Reason" value={form.reason} onChange={set("reason")} options={reasons} />
        </div>
        <TextArea label="Note to them" value={form.note} onChange={set("note")} rows={2} />
      </ActionForm>
    );
  }
  if (action === "to_owner") {
    return (
      <ActionForm title={`Return ${asset.asset_tag} to ${asset.owner_label}`} submitLabel="Record return" onCancel={onCancel}
        onSubmit={run(() => returnAssetToOwner(asset.id, {
          method: form.method, note: form.note || null, ...(form.method === "COURIER" ? courierBody(courier) : {}),
        }))}>
        <Select label="Handover" value={form.method} onChange={set("method")}
          options={[{ value: "HAND", label: "In person" }, { value: "COURIER", label: "By courier" }]} />
        {form.method === "COURIER" ? <CourierFields value={courier} onChange={setCourier} withExpected={false} /> : null}
      </ActionForm>
    );
  }
  if (action === "defect") {
    const severities = (options?.severities || ["LOW", "MEDIUM", "HIGH"]).map((s) => ({ value: s, label: titleCase(s) }));
    return (
      <ActionForm title={`Report a defect on ${asset.asset_tag}`} submitLabel="Report" onCancel={onCancel}
        onSubmit={run(() => reportAssetDefect(asset.id, { description: form.description, severity: form.severity }))}>
        <TextArea label="What is wrong" value={form.description} onChange={set("description")} rows={3} />
        <Select label="Severity" value={form.severity} onChange={set("severity")} options={severities} />
      </ActionForm>
    );
  }
  if (action === "lost" || action === "retire") {
    const lost = action === "lost";
    return (
      <ActionForm title={lost ? `Mark ${asset.asset_tag} lost` : `Retire ${asset.asset_tag}`} danger
        submitLabel={lost ? "Mark lost" : "Retire"} onCancel={onCancel}
        onSubmit={run(() => (lost ? markAssetLost : retireAsset)(asset.id, form.note))}>
        <TextArea label={lost ? "What happened (police report number for a theft)" : "Why, and how it was wiped and disposed of"}
          value={form.note} onChange={set("note")} rows={3} />
      </ActionForm>
    );
  }
  return null;
}

export function DefectRow({ issue, canManage, onChanged }) {
  const [mode, setMode] = useState("");
  const [values, setValues] = useState({ repair_vendor: "", resolution: "", fix_cost: "" });
  const set = (key) => (v) => setValues((prev) => ({ ...prev, [key]: v }));
  const open = issue.status === "OPEN" || issue.status === "IN_REPAIR";
  const submit = async () => {
    const body = { action: mode, repair_vendor: values.repair_vendor || null, resolution: values.resolution || null,
      fix_cost_cents: values.fix_cost ? Math.round(Number(values.fix_cost) * 100) : null };
    onChanged(await updateAssetDefect(issue.id, body));
    setMode("");
  };
  return (
    <div className="rounded-xl border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 text-sm text-gray-900">{issue.description}</div>
        <div className="flex gap-1.5"><SeverityChip severity={issue.severity} /><Chip tone="border-gray-200 bg-white text-gray-700">{titleCase(issue.status)}</Chip></div>
      </div>
      <div className="mt-1 text-xs text-gray-500">
        Reported {localDay(issue.reported_at)}{issue.reported_by ? ` by ${issue.reported_by}` : ""}
        {issue.repair_vendor ? ` · with ${issue.repair_vendor}` : ""}
        {issue.resolution ? ` · ${issue.resolution}` : ""}
        {issue.fix_cost_cents ? ` · cost ${(issue.fix_cost_cents / 100).toLocaleString()}` : ""}
      </div>
      {open && canManage && !mode ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {issue.status === "OPEN" ? <Button variant="secondary" onClick={() => setMode("START_REPAIR")}>Send for repair</Button> : null}
          <Button variant="secondary" onClick={() => setMode("FIXED")}>Fixed</Button>
          <Button variant="secondary" onClick={() => setMode("NO_FAULT")}>No fault</Button>
          <Button variant="ghost" onClick={() => setMode("RETIRE")}>Retire the item</Button>
        </div>
      ) : null}
      {mode ? (
        <div className="mt-3">
          <ActionForm title={titleCase(mode)} submitLabel="Save" onCancel={() => setMode("")} onSubmit={submit}>
            {mode === "START_REPAIR" ? <Input label="Repaired by" value={values.repair_vendor} onChange={set("repair_vendor")} /> : null}
            {mode !== "START_REPAIR" ? <TextArea label="What was found or done" value={values.resolution} onChange={set("resolution")} rows={2} /> : null}
            {mode === "FIXED" ? <Input label="Repair cost" type="number" value={values.fix_cost} onChange={set("fix_cost")} /> : null}
          </ActionForm>
        </div>
      ) : null}
    </div>
  );
}

export function AssetHistory({ events }) {
  if (!events?.length) return <div className="text-sm text-gray-500">Nothing recorded yet.</div>;
  return (
    <ol className="space-y-2">
      {events.map((event) => (
        <li key={event.id} className="border-l-2 border-gray-200 pl-3">
          <div className="text-sm font-medium text-gray-900">
            {titleCase(event.event_type)}{event.asset_label ? ` · ${event.asset_label}` : ""}
          </div>
          <div className="text-xs text-gray-500">
            {event.at ? new Date(event.at).toLocaleString() : ""}{event.actor ? ` · ${event.actor}` : ""}
          </div>
          {event.note ? <div className="mt-0.5 break-words text-xs text-gray-700">{event.note}</div> : null}
        </li>
      ))}
    </ol>
  );
}
