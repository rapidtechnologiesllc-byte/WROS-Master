// FY goal tree on one screen: Organization -> Company (BX-US, BX-IN) ->
// Partner -> Business Unit. Every node shows actual vs target; targets are
// edited in place. The Organization row is what the CEO Dashboard tracks.
// Structure comes from the Companies tab and each BU's Companies / Partner
// fields; a BU that runs in two companies appears under both.
import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Pencil, Target } from "lucide-react";
import { Button, Input, Select } from "./ui";
import { apiRequest } from "../services/api/client";

const formatValue = (value, unit) => {
  if (value === null || value === undefined) return "--";
  if (unit === "USD") {
    const n = Number(value);
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toLocaleString(undefined, { maximumFractionDigits: 2 })}M`;
    return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  if (unit === "%") return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
};

function TargetCell({ node, metric, onSave }) {
  const cell = node.metrics[metric.key] || {};
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(cell.target ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async (target) => {
    setSaving(true);
    setError(null);
    try {
      await onSave(node, metric.key, target);
      setEditing(false);
    } catch (err) {
      setError(err.message || "Could not save");
    } finally {
      setSaving(false);
    }
  };

  const overAllocated = cell.allocated != null && cell.target != null && cell.allocated > cell.target;
  const pct = cell.progress_pct;

  if (editing) {
    return (
      <div className="flex flex-col gap-1">
        <Input type="number" value={value} onChange={setValue} disabled={saving} />
        <div className="flex gap-1">
          <Button onClick={() => (Number(value) > 0 ? save(Number(value)) : setError("Enter a positive number"))} disabled={saving}>
            {saving ? "..." : "Save"}
          </Button>
          {cell.target != null && (
            <Button variant="secondary" onClick={() => save(null)} disabled={saving}>Clear</Button>
          )}
          <Button variant="ghost" onClick={() => { setEditing(false); setValue(cell.target ?? ""); setError(null); }} disabled={saving}>
            Cancel
          </Button>
        </div>
        {error && <span className="text-[11px] text-rose-600">{error}</span>}
      </div>
    );
  }

  return (
    <div className="text-sm">
      <div className="flex items-center gap-1">
        <span className="font-semibold text-gray-900">{formatValue(cell.actual, metric.unit)}</span>
        <span className="text-gray-400">/</span>
        <span className={cell.target == null ? "text-gray-400" : "text-gray-700"}>
          {cell.target == null ? "no target" : formatValue(cell.target, metric.unit)}
        </span>
        {node.editable && (
          <button className="ml-1 text-gray-400 hover:text-bx-orange" onClick={() => setEditing(true)} title="Set target">
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      {pct != null && (
        <div className="mt-1 h-1.5 w-full max-w-[140px] overflow-hidden rounded-full bg-gray-200">
          <div className={`h-full rounded-full ${pct >= 90 ? "bg-green-500" : pct >= 60 ? "bg-blue-500" : "bg-amber-500"}`} style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
      )}
      {cell.allocated != null && (
        <div className={`mt-0.5 text-[11px] ${overAllocated ? "text-rose-600" : "text-gray-500"}`}>
          allocated below: {formatValue(cell.allocated, metric.unit)}
          {overAllocated && " (exceeds target)"}
        </div>
      )}
    </div>
  );
}

function TreeRows({ node, depth, metrics, onSave, expanded, toggle }) {
  const hasChildren = (node.children || []).length > 0;
  const key = `${node.level}:${node.entity_id}`;
  const open = expanded[key] !== false;
  const LEVEL_LABEL = { LOCATION: "Company", PARTNER: "Partner", BU: "Business unit" };
  return (
    <Fragment>
      <tr className="border-b border-bx-border align-top">
        <td className="py-2 pr-3">
          <div className="flex items-start gap-1" style={{ paddingLeft: depth * 18 }}>
            {hasChildren ? (
              <button onClick={() => toggle(key)} className="mt-0.5 text-gray-500">
                {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
            ) : (
              <span className="inline-block w-4" />
            )}
            <div>
              <div className={`text-sm ${node.editable ? "font-semibold text-gray-900" : "italic text-gray-500"}`}>{node.name}</div>
              <div className="text-[11px] uppercase tracking-wide text-gray-400">{LEVEL_LABEL[node.level]}</div>
            </div>
          </div>
        </td>
        {metrics.map((m) => (
          <td key={m.key} className="py-2 pr-3">
            <TargetCell node={node} metric={m} onSave={onSave} />
          </td>
        ))}
      </tr>
      {open && (node.children || []).map((child) => (
        <TreeRows key={`${child.level}:${child.entity_id}`} node={child} depth={depth + 1} metrics={metrics}
          onSave={onSave} expanded={expanded} toggle={toggle} />
      ))}
    </Fragment>
  );
}

export default function GoalTree() {
  const [year, setYear] = useState(null); // null = current fiscal year (server decides)
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: tree } = await apiRequest(`/goals/tree${year ? `?year=${year}` : ""}`);
      setData(tree);
      setError(null);
    } catch (err) {
      setError(`Could not load goals: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => {
    load();
  }, [load]);

  const saveTarget = async (node, metric, target) => {
    await apiRequest("/goals/targets", {
      method: "PUT",
      body: JSON.stringify({ level: node.level, entity_id: node.entity_id, metric, target, year: data?.year }),
    });
    await load();
  };

  const toggle = (key) => setExpanded((e) => ({ ...e, [key]: e[key] === false }));

  const rollupMetrics = (data?.metrics || []).filter((m) => m.rolls_up);
  const orgOnlyMetrics = (data?.metrics || []).filter((m) => !m.rolls_up);
  const setup = data?.setup;

  return (
    <div className="mt-6 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <Target className="h-4 w-4" /> FY Goals -- Organization, Company, Partner, Business Unit
          </div>
          <p className="text-xs text-gray-500">
            Actual / target for each level. Click the pencil to set a target. The Organization row feeds the CEO Dashboard.
            {data ? ` ${Math.round(data.fy_progress_pct)}% of ${data.fy_label} elapsed.` : ""}
          </p>
        </div>
        <div className="w-32">
          <Select
            label="Fiscal year"
            value={String(data?.year ?? "")}
            onChange={(v) => setYear(Number(v))}
            options={data ? [data.current_fy - 1, data.current_fy, data.current_fy + 1].map((y) => ({
              value: String(y),
              label: data.fy_start_month === 1 ? `FY ${y}` : `FY ${y}-${String(y + 1).slice(-2)}`,
            })) : []}
          />
        </div>
      </div>

      {error && <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

      {setup && (setup.companies === 0 || setup.business_units === 0 || setup.partners === 0 || setup.bus_without_company > 0 || setup.bus_without_partner > 0) && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 space-y-0.5">
          <div className="font-semibold">To build the full tree:</div>
          {setup.companies === 0 && <div>• Add your companies (BX-US, BX-IN) in Users &amp; Access Control → Companies.</div>}
          {setup.business_units === 0 && <div>• Create business units in Users &amp; Access Control → Business Units.</div>}
          {setup.partners === 0 && <div>• Give partners the Partner role (Users tab), then set each business unit's Partner.</div>}
          {setup.bus_without_company > 0 && <div>• {setup.bus_without_company} business unit(s) have no company -- tick its companies on the BU's edit form.</div>}
          {setup.bus_without_partner > 0 && <div>• {setup.bus_without_partner} business unit(s) have no partner -- set it on the BU's edit form.</div>}
        </div>
      )}
      {setup?.intercompany_revenue > 0 && (
        <div className="mb-3 text-xs text-gray-600">
          Company revenue includes {formatValue(setup.intercompany_revenue, "USD")} of intercompany billing (e.g. BX-IN to BX-US).
          The Organization total counts external client revenue only, so it is not added twice.
        </div>
      )}

      {loading && !data ? (
        <div className="py-6 text-center text-sm text-gray-500">Loading goals...</div>
      ) : data ? (
        <>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="w-full min-w-[720px] text-left">
              <thead className="bg-bx-light text-xs uppercase text-gray-500">
                <tr>
                  <th className="py-2 px-3">Level</th>
                  {rollupMetrics.map((m) => <th key={m.key} className="py-2 pr-3">{m.label}</th>)}
                </tr>
              </thead>
              <tbody className="[&_td:first-child]:px-3">
                <TreeRows node={data.tree} depth={0} metrics={rollupMetrics} onSave={saveTarget} expanded={expanded} toggle={toggle} />
              </tbody>
            </table>
          </div>

          {orgOnlyMetrics.length > 0 && (
            <div className="mt-4">
              <div className="mb-2 text-xs font-semibold uppercase text-gray-500">Organization rates (not split by company/partner/BU)</div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {orgOnlyMetrics.map((m) => (
                  <div key={m.key} className="rounded-xl border bg-white p-3">
                    <div className="mb-1 text-xs text-gray-500">{m.label}</div>
                    <TargetCell node={data.tree} metric={m} onSave={saveTarget} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
