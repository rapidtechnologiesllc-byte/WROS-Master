// The bench (CEO 2026-10-22): everyone billable with no active allocation, with how long they
// have been on the bench, what that bench time cost (loaded payroll per bench day, the figure the
// P&L books as bench cost), what they earned while allocated and the net. Every bench number on
// every dashboard links here. Sorted by bench loss.
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { Button, Card } from "../components/ui";
import cx from "../utils/cx";
import { getBench } from "../services/api/workforce";

const usd = (cents) => (cents == null ? "—" : `$${Math.round(cents / 100).toLocaleString()}`);
const Th = ({ children, right }) => <th className={cx("px-3 py-2 text-xs font-semibold text-gray-700", right && "text-right")}>{children}</th>;
const Td = ({ children, right, tone }) => <td className={cx("px-3 py-2 text-xs", right && "text-right", tone)}>{children}</td>;

export default function BenchScreen() {
  const [searchParams, setSearchParams] = useSearchParams();
  const group = searchParams.get("group") || "";
  const businessUnitId = searchParams.get("business_unit_id") || "";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getBench({ group, businessUnitId }));
    } catch (err) {
      setData(null);
      setError(err.message || "Failed to load the bench.");
    } finally {
      setLoading(false);
    }
  }, [group, businessUnitId]);

  useEffect(() => {
    load();
  }, [load]);

  const pick = (key) => {
    const next = new URLSearchParams(searchParams);
    if (key) next.set("group", key); else next.delete("group");
    setSearchParams(next);
  };
  const money = data?.financials_visible;
  const t = data?.totals;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link to="/workforce" className="flex items-center gap-1 font-semibold text-blue-700 hover:underline">
          <ArrowLeft className="h-4 w-4" /> Workforce Overview
        </Link>
        {[{ key: "", label: "Whole bench" }, ...(data?.groups || [])].map((g) => (
          <button
            key={g.key || "all"}
            type="button"
            onClick={() => pick(g.key)}
            className={cx("rounded-full border px-3 py-1 text-xs font-semibold",
              g.key === group ? "border-gray-900 bg-gray-900 text-white" : "text-gray-700 hover:border-gray-500")}
          >
            {g.label}
          </button>
        ))}
      </div>

      <Card
        title={`Bench${t ? ` (${t.people})` : ""}`}
        subtitle={money
          ? "Bench loss = loaded cost of each bench day (as the P&L books bench cost). Earned = revenue minus delivery cost while allocated. Net = earned - bench loss."
          : "Who is on the bench and for how long. Costs are shown to people who can see the P&L."}
        right={<Button variant="ghost" onClick={load} disabled={loading}><RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh</Button>}
      >
        {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
        {data && !data.cost_data_complete ? (
          <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            {data.missing_cost_employee_ids.length} people have no salary or cost rate: their cost is missing, not zero.
          </div>
        ) : null}
        {t ? (
          <div className="mb-3 grid gap-3 sm:grid-cols-5 text-sm">
            <div><div className="text-xs text-gray-500">People</div><div className="font-bold">{t.people}</div></div>
            <div><div className="text-xs text-gray-500">Bench days</div><div className="font-bold">{t.bench_days.toLocaleString()}</div></div>
            {money ? <div><div className="text-xs text-gray-500">Bench loss</div><div className="font-bold text-rose-700">{usd(t.bench_loss_usd_cents)}</div></div> : null}
            {money ? <div><div className="text-xs text-gray-500">Earned while allocated</div><div className="font-bold text-emerald-700">{usd(t.allocated_margin_usd_cents)}</div></div> : null}
            {money ? <div><div className="text-xs text-gray-500">Net</div><div className={cx("font-bold", (t.net_usd_cents || 0) < 0 ? "text-rose-700" : "text-emerald-700")}>{usd(t.net_usd_cents)}</div></div> : null}
          </div>
        ) : null}
        <div className="overflow-x-auto rounded-2xl border">
          <table className="w-full text-left">
            <thead className="bg-gray-50">
              <tr>
                <Th>Employee</Th><Th>Group</Th><Th>Business unit · location</Th><Th>On bench since</Th><Th right>Days</Th>
                {money ? <><Th right>Cost / day</Th><Th right>Bench loss</Th><Th right>Earned while allocated</Th><Th right>Net</Th></> : null}
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading || !data?.employees?.length ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-sm text-gray-500">{loading ? "Loading…" : "Nobody is on the bench."}</td></tr>
              ) : data.employees.map((r) => (
                <tr key={r.employee_id} className="hover:bg-gray-50">
                  <Td><Link className="font-semibold text-blue-700 hover:underline" to={`/employees?employee=${encodeURIComponent(r.employee_id)}`}>{r.name}</Link></Td>
                  <Td>{r.group_label}</Td>
                  <Td>{r.business_unit || "—"} · {r.location || "—"}{r.country ? ` (${r.country})` : ""}</Td>
                  <Td>{r.bench_since}</Td>
                  <Td right>{r.bench_days}</Td>
                  {money ? (
                    <>
                      <Td right>{usd(r.daily_cost_usd_cents)}</Td>
                      <Td right tone="text-rose-700">{usd(r.bench_loss_usd_cents)}</Td>
                      <Td right>{usd(r.allocated_margin_usd_cents)}</Td>
                      <Td right tone={(r.net_usd_cents || 0) < 0 ? "text-rose-700" : "text-emerald-700"}>{usd(r.net_usd_cents)}</Td>
                    </>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
