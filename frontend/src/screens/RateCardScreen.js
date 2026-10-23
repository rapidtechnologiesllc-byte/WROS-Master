// Rate card (CEO 2026-10-23): the margin floor a placement is checked against, by delivery engine
// (Staff Aug / Core) and optionally delivery country and role. Below the minimum a BU Head
// approves the placement; below the hard floor a Partner does. No row = no floor (the placement
// is allowed and flagged). Finance sets the numbers; nothing is pre-filled.
import { useCallback, useEffect, useState } from "react";
import { Percent, RefreshCw } from "lucide-react";
import { Button, Card, Input, Select } from "../components/ui";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { confirmDialog } from "../utils/dialogs";
import {
  createMarginPolicy, deleteMarginPolicy, getMarginPolicies, updateMarginPolicy,
} from "../services/api/marginPolicies";

const EMPTY = { delivery_engine: "", country: "", role: "", min_margin_pct: "", hard_floor_pct: "", active: true };

export default function RateCardScreen() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const canCreate = hasPermission("finance-operations", "create");
  const canEdit = hasPermission("finance-operations", "edit");
  const canDelete = hasPermission("finance-operations", "delete");

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await getMarginPolicies());
    } catch (err) {
      setError(err.message || "Failed to load the rate card.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));
  const engines = data?.engines || [];
  const countries = data?.countries || [];
  const engineName = (code) => engines.find((e) => e.code === code)?.name || code;
  const countryName = (code) => (code ? countries.find((c) => c.code === code)?.name || code : "Any country");

  const save = async () => {
    if (!form.delivery_engine || form.min_margin_pct === "" || form.hard_floor_pct === "") {
      setError("Pick the delivery engine and set both percentages.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (editingId) await updateMarginPolicy(editingId, form);
      else await createMarginPolicy(form);
      setForm(EMPTY);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message || "Could not save the row.");
    } finally {
      setSaving(false);
    }
  };

  const edit = (row) => {
    setEditingId(row.id);
    setForm({ ...row, country: row.country || "", role: row.role || "",
      min_margin_pct: String(row.min_margin_pct), hard_floor_pct: String(row.hard_floor_pct) });
  };

  const remove = async (row) => {
    if (!(await confirmDialog("Remove this margin floor?", { danger: true }))) return;
    try {
      await deleteMarginPolicy(row.id);
      await load();
    } catch (err) {
      setError(err.message || "Could not remove the row.");
    }
  };

  const toggle = async (row) => {
    try {
      await updateMarginPolicy(row.id, { ...row, active: !row.active });
      await load();
    } catch (err) {
      setError(err.message || "Could not change the row.");
    }
  };

  return (
    <Card
      title="Rate Card"
      subtitle="Margin floor per placement: margin % = (bill rate - loaded hourly cost) / bill rate. Below the minimum a BU Head approves; below the hard floor a Partner approves. No matching row = no floor (allowed, flagged)."
      icon={<Percent className="h-4 w-4" />}
      right={<Button variant="ghost" onClick={load}><RefreshCw className="h-4 w-4" /></Button>}
    >
      {error && <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
      {data && data.policies.length === 0 && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          No margin floor is configured: every placement is accepted at any bill rate and flagged.
        </div>
      )}
      {data && data.policies.length > 0 && (
        <div className="mb-4 overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left">
              <tr>
                <th className="px-3 py-2 font-semibold">Delivery engine</th>
                <th className="px-3 py-2 font-semibold">Country</th>
                <th className="px-3 py-2 font-semibold">Role</th>
                <th className="px-3 py-2 font-semibold">Minimum margin</th>
                <th className="px-3 py-2 font-semibold">Hard floor</th>
                <th className="px-3 py-2 font-semibold">Active</th>
                <th className="px-3 py-2 font-semibold" />
              </tr>
            </thead>
            <tbody>
              {data.policies.map((row) => (
                <tr key={row.id} className="border-b">
                  <td className="px-3 py-2">{engineName(row.delivery_engine)}</td>
                  <td className="px-3 py-2">{countryName(row.country)}</td>
                  <td className="px-3 py-2">{row.role || "Any role"}</td>
                  <td className="px-3 py-2">{row.min_margin_pct}%</td>
                  <td className="px-3 py-2">{row.hard_floor_pct}%</td>
                  <td className="px-3 py-2">
                    {canEdit ? (
                      <input type="checkbox" checked={row.active} onChange={() => toggle(row)} />
                    ) : (row.active ? "yes" : "no")}
                  </td>
                  <td className="space-x-1 px-3 py-2">
                    {canEdit && <Button variant="ghost" size="sm" onClick={() => edit(row)}>Edit</Button>}
                    {canDelete && <Button variant="ghost" size="sm" onClick={() => remove(row)}>Remove</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(editingId ? canEdit : canCreate) && data && (
        <div className="rounded-2xl border bg-gray-50 p-4">
          <div className="mb-3 text-sm font-semibold text-gray-900">{editingId ? "Edit floor" : "Add a floor"}</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Select label="Delivery engine" value={form.delivery_engine} onChange={set("delivery_engine")}
              options={[{ value: "", label: "Select" }, ...engines.map((e) => ({ value: e.code, label: e.name }))]} />
            <Select label="Country (where the consultant delivers from)" value={form.country} onChange={set("country")}
              options={[{ value: "", label: "Any country" }, ...countries.map((c) => ({ value: c.code, label: c.name }))]} />
            <Input label="Role (optional, matches the allocation's role)" value={form.role} onChange={set("role")} />
            <Input label="Minimum margin % (below: BU Head approves)" type="number" value={form.min_margin_pct}
              onChange={set("min_margin_pct")} />
            <Input label="Hard floor % (below: Partner approves)" type="number" value={form.hard_floor_pct}
              onChange={set("hard_floor_pct")} />
          </div>
          <div className="mt-3 flex gap-2">
            <Button variant="primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
            {editingId && (
              <Button variant="ghost" onClick={() => { setEditingId(null); setForm(EMPTY); }}>Cancel</Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
