// FY progress: time elapsed in the fiscal year plus how far the org has
// actually progressed toward each cumulative FY target, month by month
// (billable headcount at month end; revenue and new logos accumulated
// since the FY start). The dash on each bar is the straight-line pace the
// target needs by that month. The FY start month is a tenant setting.
import { useState } from "react";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];

const METRICS = [
  { key: "headcount", label: "Billable headcount", unit: "people" },
  { key: "revenue", label: "Revenue", unit: "USD" },
  { key: "new_logos", label: "New logos", unit: "clients" },
];

const fmt = (value, unit) => {
  if (value === null || value === undefined) return "--";
  if (unit === "USD") {
    const n = Number(value);
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toLocaleString(undefined, { maximumFractionDigits: 2 })}M`;
    if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toLocaleString(undefined, { maximumFractionDigits: 0 })}K`;
    return `$${n.toLocaleString()}`;
  }
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
};

const formatDate = (iso) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", year: "numeric" }) : "";

export default function FYProgressPanel({ fyData, onChangeStartMonth }) {
  const [metricKey, setMetricKey] = useState("headcount");
  const [savingMonth, setSavingMonth] = useState(false);
  const [error, setError] = useState(null);

  if (!fyData) return null;
  const metricDef = METRICS.find((m) => m.key === metricKey);
  const metric = (fyData.metrics || []).find((m) => m.key === metricKey) || {};
  const target = metric.target ?? null;
  const months = fyData.monthly || [];
  const startMonth = fyData.fy_start ? new Date(`${fyData.fy_start}T00:00:00`).getMonth() + 1 : 1;

  // 12 slots for the whole FY; months not reached yet stay empty
  const slots = Array.from({ length: 12 }, (_, i) => months[i] || null);
  const slotLabels = Array.from({ length: 12 }, (_, i) => MONTHS[(startMonth - 1 + i) % 12].slice(0, 3));
  const scaleMax = Math.max(target || 0, ...months.map((m) => m[metricKey] || 0), 1);
  const pctOfTarget = target ? Math.round(((metric.current || 0) / target) * 100) : null;

  const changeMonth = async (value) => {
    setSavingMonth(true);
    setError(null);
    try {
      await onChangeStartMonth(Number(value));
    } catch (err) {
      setError(err.message || "Could not save the fiscal year start");
    } finally {
      setSavingMonth(false);
    }
  };

  return (
    <div className="rounded-2xl border bg-gradient-to-br from-blue-50 to-blue-100/40 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase text-blue-600">FY Progress · {fyData.fy_label}</div>
          <div className="text-xs text-blue-700/80">{formatDate(fyData.fy_start)} – {formatDate(fyData.fy_end)}</div>
        </div>
        <label className="flex items-center gap-2 text-xs text-gray-600">
          FY starts in
          <select
            value={startMonth}
            onChange={(e) => changeMonth(e.target.value)}
            disabled={savingMonth}
            className="rounded-lg border border-gray-300 bg-white px-2 py-1 text-xs"
          >
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </label>
      </div>
      {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}

      <div className="mt-3">
        <div className="flex items-baseline justify-between text-xs text-blue-800">
          <span>Time elapsed</span>
          <span className="font-semibold">{Math.round(fyData.fy_progress_pct)}% of the fiscal year</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
          <div className="h-full rounded-full bg-blue-400" style={{ width: `${Math.min(fyData.fy_progress_pct, 100)}%` }} />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex gap-1">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => setMetricKey(m.key)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                metricKey === m.key ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-blue-50"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-blue-900">
            {fmt(metric.current, metricDef.unit)}
            <span className="text-lg font-semibold text-blue-700/70"> / {target === null ? "no target" : fmt(target, metricDef.unit)}</span>
          </div>
          <div className="text-xs text-blue-700">
            {pctOfTarget === null ? "Set the target on the metric card below" : `${pctOfTarget}% of FY target`}
          </div>
        </div>
      </div>

      <div className="mt-4">
        <div className="relative flex h-36 items-end gap-1.5 border-b border-blue-200">
          {target !== null && (
            <div className="pointer-events-none absolute left-0 right-0 border-t border-dashed border-blue-400" style={{ bottom: `${(target / scaleMax) * 100}%` }}>
              <span className="absolute -top-4 right-0 text-[10px] text-blue-600">target {fmt(target, metricDef.unit)}</span>
            </div>
          )}
          {slots.map((slot, i) => {
            const value = slot ? slot[metricKey] || 0 : 0;
            const pace = slot?.pace?.[metricKey];
            const behind = pace != null && value < pace * 0.9;
            return (
              <div key={i} className="relative flex h-full flex-1 items-end justify-center"
                title={slot ? `${slotLabels[i]}: ${fmt(value, metricDef.unit)}${pace != null ? ` (pace ${fmt(pace, metricDef.unit)})` : ""}` : `${slotLabels[i]}: not reached yet`}>
                {slot ? (
                  <div
                    className={`w-full rounded-t ${slot.is_current ? "opacity-70" : ""} ${behind ? "bg-amber-400" : "bg-blue-500"}`}
                    style={{ height: `${Math.max((value / scaleMax) * 100, value ? 2 : 0)}%` }}
                  />
                ) : (
                  <div className="h-1 w-full rounded bg-blue-100" />
                )}
                {pace != null && (
                  <div className="absolute left-0 right-0 h-0.5 bg-gray-700/60" style={{ bottom: `${(pace / scaleMax) * 100}%` }} />
                )}
              </div>
            );
          })}
        </div>
        <div className="mt-1 flex gap-1.5">
          {slotLabels.map((label, i) => (
            <div key={i} className="flex-1 text-center text-[10px] text-gray-500">{label}</div>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-gray-500">
          <span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-blue-500" />on pace</span>
          <span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-amber-400" />behind pace</span>
          <span><span className="mr-1 inline-block h-0.5 w-3 bg-gray-700/60 align-middle" />pace needed to hit the target</span>
          <span>{metricKey === "headcount" ? "Billable headcount at each month end" : "Accumulated since the FY start"}</span>
        </div>
      </div>
    </div>
  );
}
