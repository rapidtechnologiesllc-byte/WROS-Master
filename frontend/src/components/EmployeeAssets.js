// The Assets tab of an employee's page (CEO 2026-11-10): what they hold, what is due back, the project kit
// they still need, and, for someone leaving, whether full and final settlement is on hold until IT Admin
// signs off their asset clearance. The employee sees their own and can confirm receipt, send an item back
// with its tracking number and report a defect; IT Admin can do everything.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button, TextArea } from "./ui";
import {
  AssetActionForm, AssetHistory, CheckoutRegister, Chip, PlaceChips, availableActions, localDay,
} from "./AssetPanels";
import { getAssetOptions, getEmployeeAssets, signOffClearance, titleCase } from "../services/api/assets";

function Section({ title, subtitle, children }) {
  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      {subtitle ? <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function HeldItem({ asset, data, options, onChanged }) {
  const [action, setAction] = useState("");
  const actions = availableActions(asset, { manage: data.can_manage, holder: data.is_self })
    .filter(([key]) => data.can_manage || ["receipt", "ship_back", "defect"].includes(key));
  return (
    <div className="space-y-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-medium text-gray-900">
            {data.can_manage ? <Link className="hover:underline" to={`/admin/assets?asset=${asset.id}`}>{asset.label}</Link> : asset.label}
          </div>
          <div className="text-xs text-gray-500">
            {asset.owner_label}
            {asset.shipment ? ` · ${asset.shipment.carrier} ${asset.shipment.tracking_number}` : ""}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <PlaceChips asset={asset} />
          {asset.return_due ? <Chip tone="border-amber-200 bg-amber-50 text-amber-800">Due back {asset.return_due}</Chip> : null}
          {asset.open_issues ? <Chip tone="border-rose-200 bg-rose-50 text-rose-800">{asset.open_issues} defect(s)</Chip> : null}
        </div>
      </div>
      {actions.length && !action ? (
        <div className="flex flex-wrap gap-2">
          {actions.map(([key, text]) => (
            <Button key={key} variant={["lost", "retire"].includes(key) ? "ghost" : "secondary"} onClick={() => setAction(key)}>{text}</Button>
          ))}
        </div>
      ) : null}
      {action ? (
        <AssetActionForm action={action} asset={asset} options={options}
          onDone={() => { setAction(""); onChanged(); }} onCancel={() => setAction("")} />
      ) : null}
    </div>
  );
}

function Clearance({ data, onChanged }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const leaving = ["NOTICE_PERIOD", "EXITED"].includes(data.employee_status);
  if (!leaving && !data.clearance) return null;
  const cleared = data.clearance?.status === "CLEARED";
  const sign = async () => {
    setBusy(true);
    setError("");
    try {
      await signOffClearance(data.employee_id, note || null);
      onChanged();
    } catch (err) {
      setError(err.message || "Could not sign off.");
    }
    setBusy(false);
  };
  return (
    <Section title="Asset clearance" subtitle="Full and final settlement is paid only after IT Admin signs this off.">
      {cleared ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          Signed off{data.clearance.signed_off_by ? ` by ${data.clearance.signed_off_by}` : ""}
          {data.clearance.signed_off_at ? ` on ${localDay(data.clearance.signed_off_at)}` : ""}.
          {data.clearance.note ? ` ${data.clearance.note}` : ""} Settlement is not held for assets.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            Settlement on hold: {data.settlement_hold}
            {data.clearance?.due_date ? ` Last working day ${data.clearance.due_date}.` : ""}
          </div>
          {data.lost.length ? (
            <div className="text-sm text-gray-700">Lost while with them: {data.lost.join(", ")}. Say how it was settled when signing off.</div>
          ) : null}
          {data.can_manage && !data.clearance_blockers.length ? (
            <>
              <TextArea label="Note (required if anything was lost)" value={note} onChange={setNote} rows={2} />
              {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">{error}</div> : null}
              <div className="flex justify-end"><Button onClick={sign} disabled={busy}>{busy ? "Signing…" : "Sign off clearance"}</Button></div>
            </>
          ) : null}
        </div>
      )}
    </Section>
  );
}

export default function EmployeeAssets({ employeeId }) {
  const [data, setData] = useState(null);
  const [options, setOptions] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const loaded = await getEmployeeAssets(employeeId);
      setData(loaded);
      if (loaded.can_manage) setOptions(await getAssetOptions());
    } catch (err) {
      console.error("[EmployeeAssets] load failed", err);
      setError(err.message || "Could not load assets.");
    }
  }, [employeeId]);
  useEffect(() => { load(); }, [load]);

  if (error) return <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>;
  if (!data) return <div className="py-6 text-center text-sm text-gray-500">Loading assets…</div>;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Clearance data={data} onChanged={load} />
        {data.kit_gaps.length ? (
          <Section title="Project kit still needed" subtitle="IT Admin has a task to issue it.">
            <ul className="space-y-1 text-sm text-gray-800">
              {data.kit_gaps.map((gap) => (
                <li key={`${gap.project_id}-${gap.category}-${gap.provided_by}`}>
                  {gap.needed - gap.held} × {titleCase(gap.category).toLowerCase()} for {gap.project_name}
                  {gap.provided_by === "CLIENT" ? " (the client provides it)" : ""}{gap.note ? `: ${gap.note}` : ""}
                </li>
              ))}
            </ul>
          </Section>
        ) : null}
        <Section title={`Holding (${data.held.length})`}
          subtitle={data.is_self ? "Confirm what arrives, and enter the courier and tracking number when you send something back." : null}>
          {data.held.length ? (
            <div className="space-y-3">
              {data.held.map((asset) => (
                <HeldItem key={asset.id} asset={asset} data={data} options={options} onChanged={load} />
              ))}
            </div>
          ) : <div className="text-sm text-gray-500">No assets on the ledger for {data.employee_name}.</div>}
        </Section>
        <Section title="Check-out / check-in register" subtitle="Every item they have held, from check-out to check-in.">
          <CheckoutRegister rows={data.checkouts} showAsset />
        </Section>
      </div>
      <Section title="History">
        <AssetHistory events={data.history} />
      </Section>
    </div>
  );
}
