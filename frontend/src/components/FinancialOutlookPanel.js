// Projected vs actual revenue and anticipated vs actual expense (CEO 2026-10-11).
// A hire is expense from day one (bench or deployed); deployment is projected revenue;
// approved time is earned, an approved invoice is billed, and only money paid into the
// account is actual revenue. Figures and scope come from GET /finance/outlook.
import { useEffect, useState } from "react";
import { getFinancialOutlook } from "../services/api/financialOutlook";

const PERIODS = [
  { key: "month", label: "This month" },
  { key: "quarter", label: "This quarter" },
  { key: "year", label: "This fiscal year" },
];

const money = (cents, currency, fx) => {
  if (cents === null || cents === undefined) return "--";
  const value = (Number(cents) / 100) * (currency === "INR" ? fx : 1);
  const symbol = currency === "INR" ? "₹" : "$";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (currency === "INR" && abs >= 1e7) return `${sign}${symbol}${(abs / 1e7).toFixed(2)}Cr`;
  if (currency === "INR" && abs >= 1e5) return `${sign}${symbol}${(abs / 1e5).toFixed(2)}L`;
  if (abs >= 1e6) return `${sign}${symbol}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${symbol}${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${symbol}${abs.toFixed(0)}`;
};

function Bar({ label, value, max, tone, note, format }) {
  const width = max > 0 ? Math.max(2, Math.round((Math.abs(value) / max) * 100)) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-slate-600">{label}</span>
        <span className="font-semibold text-slate-900">{format(value)}</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-slate-100">
        <div className={`h-2 rounded-full ${tone}`} style={{ width: `${width}%` }} />
      </div>
      {note ? <div className="mt-0.5 text-[11px] text-slate-500">{note}</div> : null}
    </div>
  );
}

export default function FinancialOutlookPanel({ title = "Revenue & expense: plan vs actual", groupBy = "business_unit", businessUnitId }) {
  const [period, setPeriod] = useState("month");
  const [currency, setCurrency] = useState("USD");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getFinancialOutlook({ period, businessUnitId })
      .then((res) => active && setData(res))
      .catch((err) => active && setError(err.message || "Could not load the financial outlook."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [period, businessUnitId]);

  const fx = Number(data?.fx_inr_per_usd || 85);
  const format = (cents) => money(cents, currency, fx);
  const revenueMax = data ? Math.max(data.projected_revenue, data.earned_revenue, data.billed_revenue, data.actual_revenue, 1) : 1;
  const expenseMax = data ? Math.max(data.anticipated_expense, data.actual_expense, 1) : 1;
  const rows = (groupBy === "partner" ? data?.by_partner : data?.by_business_unit) || [];
  const gaps = data?.gaps || {};

  return (
    <div className="rounded-2xl border bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {data ? `${data.start} to ${data.end} · as of ${data.as_of}` : "Loading…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setPeriod(p.key)}
              className={`rounded-full px-3 py-1 text-xs ${period === p.key ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`}
            >
              {p.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setCurrency(currency === "USD" ? "INR" : "USD")}
            className="rounded-full border px-3 py-1 text-xs text-slate-700"
            title={`$1 = ₹${fx}`}
          >
            {currency === "USD" ? "Show ₹" : "Show $"}
          </button>
        </div>
      </div>

      <div className="px-5 py-4">
        {error ? <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
        {loading && !data ? <div className="text-sm text-slate-500">Loading…</div> : null}
        {data ? (
          <>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <div className="space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Revenue</div>
                <Bar label="Projected (deployed people x rate)" value={data.projected_revenue} max={revenueMax} tone="bg-sky-300" format={format} />
                <Bar label="Earned (approved time)" value={data.earned_revenue} max={revenueMax} tone="bg-sky-500" format={format}
                  note={data.unbilled ? `${format(data.unbilled)} worked, not yet invoiced` : null} />
                <Bar label="Billed (approved invoices)" value={data.billed_revenue} max={revenueMax} tone="bg-indigo-500" format={format}
                  note={data.receivable ? `${format(data.receivable)} billed, not yet paid` : null} />
                <Bar label="Actual (paid into our account)" value={data.actual_revenue} max={revenueMax} tone="bg-emerald-600" format={format}
                  note={`${data.revenue_variance >= 0 ? "+" : ""}${format(data.revenue_variance)} vs projected`} />
              </div>
              <div className="space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Expense</div>
                <Bar label="Anticipated" value={data.anticipated_expense} max={expenseMax} tone="bg-amber-300" format={format}
                  note={`Bench ${format(data.anticipated_bench_cost)} · deployed ${format(data.anticipated_deployed_cost)} · internal staff ${format(data.anticipated_overhead_cost)} · other ${format(data.anticipated_other_expense)}`} />
                <Bar label="Actual" value={data.actual_expense} max={expenseMax} tone="bg-orange-600" format={format}
                  note={`Payroll incurred ${format(data.actual_payroll)} · expenses reimbursed ${format(data.actual_other_expense)}`} />
              </div>
              <div className="space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Net</div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Projected (revenue − anticipated expense)</div>
                  <div className={`text-lg font-semibold ${data.projected_net < 0 ? "text-red-700" : "text-slate-900"}`}>{format(data.projected_net)}</div>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Actual (cash received − actual expense)</div>
                  <div className={`text-lg font-semibold ${data.actual_net < 0 ? "text-red-700" : "text-slate-900"}`}>{format(data.actual_net)}</div>
                </div>
              </div>
            </div>

            {!data.data_complete ? (
              <div className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                Incomplete inputs, left out rather than counted as zero:
                {gaps.allocations_without_bill_rate?.length ? ` ${gaps.allocations_without_bill_rate.length} allocation(s) without a bill rate.` : ""}
                {gaps.employees_without_cost?.length ? ` ${gaps.employees_without_cost.length} employee(s) without a salary or cost-rate config.` : ""}
              </div>
            ) : null}

            {rows.length > 0 ? (
              <div className="mt-5 overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-500">
                      <th className="py-2 pr-4">{groupBy === "partner" ? "Partner" : "Business unit"}</th>
                      <th className="py-2 pr-4 text-right">Projected rev.</th>
                      <th className="py-2 pr-4 text-right">Actual rev. (cash)</th>
                      <th className="py-2 pr-4 text-right">Anticipated exp.</th>
                      <th className="py-2 pr-4 text-right">Actual exp.</th>
                      <th className="py-2 pr-4 text-right">Bench cost</th>
                      <th className="py-2 text-right">Actual net</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={String(r.key)} className="border-t">
                        <td className="py-2 pr-4 text-slate-800">{r.name}</td>
                        <td className="py-2 pr-4 text-right">{format(r.projected_revenue)}</td>
                        <td className="py-2 pr-4 text-right">{format(r.actual_revenue)}</td>
                        <td className="py-2 pr-4 text-right">{format(r.anticipated_expense)}</td>
                        <td className="py-2 pr-4 text-right">{format(r.actual_expense)}</td>
                        <td className="py-2 pr-4 text-right">{format(r.anticipated_bench_cost)}</td>
                        <td className={`py-2 text-right font-medium ${r.actual_net < 0 ? "text-red-700" : ""}`}>{format(r.actual_net)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
