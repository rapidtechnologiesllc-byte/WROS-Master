// Asset Ledger (Admin, CEO 2026-11-10): every device we hold or are responsible for, owned by the IT Admin
// function. What needs someone comes first (alerts), then the ledger; an item opens with its whole history,
// courier movements and defects. Task links open an item with ?asset=<id>. Every rule is the server's.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, Laptop, Plus, RefreshCw, Search, X } from "lucide-react";
import { Button, Input, Select, TextArea } from "../components/ui";
import {
  AssetActionForm, AssetHistory, CheckoutRegister, Chip, DefectRow, PlaceChips, availableActions, localDay,
} from "../components/AssetPanels";
import {
  getAsset, getAssetAlerts, getAssetOptions, listAssets, registerAsset, titleCase,
} from "../services/api/assets";

const SEVERITY_TONE = {
  HIGH: "border-rose-200 bg-rose-50 text-rose-800",
  MEDIUM: "border-amber-200 bg-amber-50 text-amber-800",
  LOW: "border-gray-200 bg-gray-50 text-gray-700",
};

function Alerts({ alerts, onOpen }) {
  if (!alerts.length) {
    return <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">Nothing needs attention: every item is where the ledger says.</div>;
  }
  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-gray-900">
        <AlertTriangle className="h-4 w-4 text-rose-600" /> Needs attention ({alerts.length})
      </h2>
      <ul className="space-y-2">
        {alerts.map((alert, index) => (
          <li key={`${alert.kind}-${alert.asset_id || alert.employee_id}-${index}`}
            className="flex flex-wrap items-start justify-between gap-2 rounded-xl border p-3">
            <div className="min-w-0 flex-1">
              <Chip tone={SEVERITY_TONE[alert.severity]}>{titleCase(alert.kind)}</Chip>
              <div className="mt-1 break-words text-sm text-gray-900">{alert.message}</div>
            </div>
            <div className="flex gap-2">
              {alert.asset_id ? <Button variant="secondary" onClick={() => onOpen(alert.asset_id)}>Open item</Button> : null}
              {alert.employee_id ? (
                <Link to={`/employees/${alert.employee_id}?tab=assets`}
                  className="rounded-xl bg-gray-100 px-3.5 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-200">Employee</Link>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

const EMPTY_ITEM = {
  category: "LAPTOP", owner_type: "COMPANY", owner_company_id: "", owner_client_id: "", owner_name: "", employee_id: "",
  make: "", model: "", serial_number: "", asset_tag: "", condition: "NEW", purchase_date: "", purchase_cost: "",
  currency: "", warranty_until: "", notes: "", supplier: "", invoice_number: "",
};

function RegisterForm({ options, onSaved, onCancel }) {
  const [item, setItem] = useState(EMPTY_ITEM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key) => (value) => setItem((prev) => ({ ...prev, [key]: value }));
  const label = (values) => values.map((v) => ({ value: v, label: titleCase(v) }));
  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const body = { ...item, purchase_cost_cents: item.purchase_cost ? Math.round(Number(item.purchase_cost) * 100) : null };
      delete body.purchase_cost;
      Object.keys(body).forEach((key) => { if (body[key] === "") body[key] = null; });
      onSaved(await registerAsset(body));
    } catch (err) {
      setError(err.message || "Could not register the item.");
      setBusy(false);
    }
  };
  return (
    <section className="space-y-4 rounded-2xl border bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-base font-semibold text-gray-900">Procure an item</h2>
        <p className="mt-0.5 text-xs text-gray-500">It starts in the office; check it out to someone from its record.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Select label="Category" value={item.category} onChange={set("category")} options={label(options.categories)} />
        <Select label="Owned by" value={item.owner_type} onChange={set("owner_type")}
          options={[{ value: "COMPANY", label: "One of our companies" }, { value: "CLIENT", label: "A client" },
            { value: "LEASED", label: "A leasing company" }, { value: "PERSONAL", label: "The employee (own device)" }]} />
        {item.owner_type === "COMPANY" ? (
          <Select label="Company" value={item.owner_company_id} onChange={set("owner_company_id")}
            options={options.companies.map((c) => ({ value: c.id, label: c.name }))} />
        ) : null}
        {item.owner_type === "CLIENT" ? (
          <Select label="Client" value={item.owner_client_id} onChange={set("owner_client_id")}
            options={options.clients.map((c) => ({ value: c.id, label: c.name }))} />
        ) : null}
        {item.owner_type === "LEASED" ? <Input label="Leasing company" value={item.owner_name} onChange={set("owner_name")} /> : null}
        {item.owner_type === "PERSONAL" ? (
          <Select label="Employee" value={item.employee_id} onChange={set("employee_id")}
            options={options.employees.map((e) => ({ value: e.id, label: e.name }))} />
        ) : null}
        <Input label="Make" value={item.make} onChange={set("make")} />
        <Input label="Model" value={item.model} onChange={set("model")} />
        <Input label="Serial number" value={item.serial_number} onChange={set("serial_number")} />
        <Input label="Asset tag (blank: next AST number)" value={item.asset_tag} onChange={set("asset_tag")} />
        <Select label="Condition" value={item.condition} onChange={set("condition")} options={label(options.conditions)} />
        {item.owner_type !== "PERSONAL" ? (
          <>
            <Input label="Procured on" type="date" value={item.purchase_date} onChange={set("purchase_date")} />
            <Input label="Supplier" value={item.supplier} onChange={set("supplier")} />
            <Input label="Invoice number" value={item.invoice_number} onChange={set("invoice_number")} />
            <Input label="Cost" type="number" value={item.purchase_cost} onChange={set("purchase_cost")} />
            <Input label="Currency (USD, INR…)" value={item.currency} onChange={set("currency")} />
            <Input label="Warranty until" type="date" value={item.warranty_until} onChange={set("warranty_until")} />
          </>
        ) : null}
      </div>
      <TextArea label="Notes" value={item.notes} onChange={set("notes")} rows={2} />
      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">{error}</div> : null}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
        <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Add to ledger"}</Button>
      </div>
    </section>
  );
}

function Fact({ label, children }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-0.5 break-words text-sm text-gray-900">{children || "—"}</div>
    </div>
  );
}

function Lifecycle({ life }) {
  if (!life) return null;
  const money = (cents) => (cents == null ? null : `${(cents / 100).toLocaleString()} ${life.currency || ""}`.trim());
  const cells = [
    ["Procured", [life.procured_on, life.supplier].filter(Boolean).join(" · ") || null],
    ["Cost", money(life.cost_cents)],
    ["Check-outs", String(life.check_outs)],
    ["Days with employees", String(life.days_with_employees)],
    ["Days in office", String(life.days_in_office)],
    ["Defects / repair cost", `${life.defects}${life.repair_cost_cents ? ` · ${money(life.repair_cost_cents)}` : ""}`],
    ["Left the ledger", life.ended ? `${life.ended}${life.ended_at ? ` ${localDay(life.ended_at)}` : ""}` : "Still in use"],
  ];
  return (
    <div className="rounded-xl border bg-gray-50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">Life of this item</h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cells.map(([label, value]) => <Fact key={label} label={label}>{value}</Fact>)}
      </div>
      {life.ended_note ? <div className="mt-2 text-xs text-gray-600">{life.ended_note}</div> : null}
    </div>
  );
}

function AssetDetail({ assetId, options, onClose, onChanged }) {
  const [asset, setAsset] = useState(null);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");

  const load = useCallback(async () => {
    try {
      setAsset(await getAsset(assetId));
    } catch (err) {
      setError(err.message || "Could not load this item.");
    }
  }, [assetId]);
  useEffect(() => { load(); }, [load]);

  const done = (updated) => {
    setAsset(updated);
    setAction("");
    onChanged();
  };
  if (error) return <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>;
  if (!asset) return <div className="rounded-2xl border bg-white p-5 text-sm text-gray-500">Loading item…</div>;
  const actions = availableActions(asset, { manage: options.can_edit, holder: false });
  const cost = asset.purchase_cost_cents != null
    ? `${(asset.purchase_cost_cents / 100).toLocaleString()} ${asset.currency || ""}`.trim() : null;
  return (
    <section className="space-y-5 rounded-2xl border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">{asset.label}</h2>
            <PlaceChips asset={asset} />
          </div>
          <div className="mt-0.5 text-sm text-gray-500">{asset.owner_label} · {asset.where}</div>
        </div>
        <Button variant="ghost" onClick={onClose}><X className="h-4 w-4" /> Close</Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Where">
          {asset.holder_employee_id ? (
            <Link className="text-blue-700 hover:underline" to={`/employees/${asset.holder_employee_id}?tab=assets`}>{asset.holder_name}</Link>
          ) : asset.status_label}
        </Fact>
        <Fact label="Condition">{titleCase(asset.condition)}</Fact>
        <Fact label="Due back">{asset.return_due ? `${asset.return_due} (${titleCase(asset.return_reason)})` : null}</Fact>
        <Fact label="Courier">
          {asset.shipment ? `${asset.shipment.carrier} ${asset.shipment.tracking_number}, shipped ${asset.shipment.shipped_on}` : null}
        </Fact>
        <Fact label="Procured">{[asset.purchase_date, asset.supplier, asset.invoice_number && `invoice ${asset.invoice_number}`, cost]
          .filter(Boolean).join(" · ")}</Fact>
        <Fact label="Warranty until">{asset.warranty_until}</Fact>
        <Fact label="Serial">{asset.serial_number}</Fact>
        <Fact label="Notes">{asset.notes}</Fact>
      </div>
      {actions.length && !action ? (
        <div className="flex flex-wrap gap-2">
          {actions.map(([key, text]) => (
            <Button key={key} variant={["lost", "retire"].includes(key) ? "ghost" : "secondary"} onClick={() => setAction(key)}>{text}</Button>
          ))}
        </div>
      ) : null}
      {action ? <AssetActionForm action={action} asset={asset} options={options} onDone={done} onCancel={() => setAction("")} /> : null}
      <Lifecycle life={asset.lifecycle} />
      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-900">Check-out / check-in register ({asset.checkouts.length})</h3>
        <CheckoutRegister rows={asset.checkouts} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-900">Defects ({asset.issues.length})</h3>
          <div className="space-y-2">
            {asset.issues.length ? asset.issues.map((issue) => (
              <DefectRow key={issue.id} issue={issue} canManage={options.can_edit} onChanged={done} />
            )) : <div className="text-sm text-gray-500">None reported.</div>}
          </div>
          <h3 className="mb-2 mt-5 text-sm font-semibold text-gray-900">Courier movements ({asset.shipments.length})</h3>
          <div className="space-y-2">
            {asset.shipments.length ? asset.shipments.map((s) => (
              <div key={s.id} className="rounded-xl border p-3 text-sm">
                <div className="font-medium text-gray-900">{titleCase(s.direction)} · {s.carrier} {s.tracking_number}</div>
                <div className="text-xs text-gray-500">
                  Shipped {s.shipped_on}{s.expected_on ? `, expected ${s.expected_on}` : ""}
                  {s.received_on ? `, received ${s.received_on}` : ""} · {titleCase(s.status)}
                </div>
              </div>
            )) : <div className="text-sm text-gray-500">None.</div>}
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-900">Full ledger, from procurement</h3>
          <AssetHistory events={asset.events} />
        </div>
      </div>
    </section>
  );
}

export default function AssetLedgerScreen() {
  const [params, setParams] = useSearchParams();
  const openId = params.get("asset");
  const [options, setOptions] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [filters, setFilters] = useState({ status: "", owner_type: "", category: "", search: "" });
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [loadedLedger, loadedAlerts] = await Promise.all([listAssets(filters), getAssetAlerts()]);
      setLedger(loadedLedger);
      setAlerts(loadedAlerts);
    } catch (err) {
      console.error("[AssetLedger] load failed", err);
      setError(err.message || "Could not load the ledger.");
    }
  }, [filters]);

  useEffect(() => {
    getAssetOptions().then(setOptions).catch((err) => setError(err.message || "Could not load the form lists."));
  }, []);
  useEffect(() => {
    const handle = setTimeout(load, filters.search ? 300 : 0);
    return () => clearTimeout(handle);
  }, [load, filters.search]);

  const open = (assetId) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    next.set("asset", assetId);
    return next;
  });
  const close = () => setParams((prev) => {
    const next = new URLSearchParams(prev);
    next.delete("asset");
    return next;
  });
  const setFilter = (key) => (value) => setFilters((prev) => ({ ...prev, [key]: value }));
  const any = (values, word, labels) => [{ value: "", label: `Any ${word}` },
    ...(values || []).map((v) => ({ value: v, label: (labels && labels[v]) || titleCase(v) }))];
  const summary = ledger?.summary;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-gray-900"><Laptop className="h-5 w-5" /> Asset Ledger</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Every device we own or are responsible for, owned by {options?.owner_function || "IT Admin"}. Returns, couriers,
            defects and leavers' clearance raise their own tasks.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={load}><RefreshCw className="h-4 w-4" /> Refresh</Button>
          {options?.can_create && !registering ? <Button onClick={() => setRegistering(true)}><Plus className="h-4 w-4" /> Procure item</Button> : null}
        </div>
      </div>
      {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div> : null}
      {registering && options ? (
        <RegisterForm options={options} onCancel={() => setRegistering(false)}
          onSaved={(asset) => { setRegistering(false); load(); open(asset.id); }} />
      ) : null}
      {openId && options ? <AssetDetail key={openId} assetId={openId} options={options} onClose={close} onChanged={load} /> : null}
      {summary ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[["In office", summary.by_status.IN_STOCK || 0], ["With employees", summary.by_status.ASSIGNED || 0],
            ["Returns open", summary.open_returns], ["Defects open", summary.open_issues]].map(([label, value]) => (
            <div key={label} className="rounded-2xl border bg-white p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</div>
              <div className="mt-1 text-2xl font-semibold text-gray-900">{value}</div>
            </div>
          ))}
        </div>
      ) : null}
      <Alerts alerts={alerts} onOpen={open} />
      <section className="rounded-2xl border bg-white p-5 shadow-sm">
        <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Search</div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input value={filters.search} onChange={(e) => setFilter("search")(e.target.value)}
                placeholder="Tag, serial, model or holder"
                className="w-full rounded-xl border bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-gray-900" />
            </div>
          </label>
          <Select label="Where" value={filters.status} onChange={setFilter("status")} options={any(options?.statuses, "place", options?.status_labels)} />
          <Select label="Owner" value={filters.owner_type} onChange={setFilter("owner_type")} options={any(options?.owner_types, "owner")} />
          <Select label="Category" value={filters.category} onChange={setFilter("category")} options={any(options?.categories, "category")} />
        </div>
        {!ledger ? <div className="py-6 text-center text-sm text-gray-500">Loading the ledger…</div> : null}
        {ledger && !ledger.assets.length ? <div className="py-6 text-center text-sm text-gray-500">No items match.</div> : null}
        {ledger?.assets.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b text-xs uppercase tracking-wide text-gray-500">
                <tr><th className="py-2 pr-3">Item</th><th className="py-2 pr-3">Owner</th><th className="py-2 pr-3">Where</th>
                  <th className="py-2 pr-3">Holder</th><th className="py-2 pr-3">Due back</th><th className="py-2">Defects</th></tr>
              </thead>
              <tbody>
                {ledger.assets.map((asset) => (
                  <tr key={asset.id} onClick={() => open(asset.id)}
                    className={`cursor-pointer border-b last:border-0 hover:bg-gray-50 ${asset.id === openId ? "bg-orange-50" : ""}`}>
                    <td className="py-2 pr-3"><div className="font-medium text-gray-900">{asset.asset_tag}</div>
                      <div className="text-xs text-gray-500">{asset.label.replace(`${asset.asset_tag} `, "")}</div></td>
                    <td className="py-2 pr-3 text-gray-700">{asset.owner_label}</td>
                    <td className="py-2 pr-3"><PlaceChips asset={asset} /></td>
                    <td className="py-2 pr-3 text-gray-700">{asset.holder_name || "—"}</td>
                    <td className="py-2 pr-3 text-gray-700">{asset.return_due || "—"}</td>
                    <td className="py-2 text-gray-700">{asset.open_issues || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}
