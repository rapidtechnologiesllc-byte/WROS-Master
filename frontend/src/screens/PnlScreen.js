// Partner & Org P&L: income, delivery cost, bench cost and approved expenses for a month,
// for the whole org and broken down by partner, business unit and client. Clicking a partner
// shows every timesheet behind their numbers, from employee and job to invoice and payment.
import { useCallback, useEffect, useState } from "react";
import { BarChart3, RefreshCw } from "lucide-react";
import { Card, Button, Input, Table } from "../components/ui";
import { getChainLines, getChainSummary, getPnl } from "../services/api/revenueChain";

const usd = (cents) =>
  cents == null ? "—" : `$${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const pct = (value) => (value == null ? "—" : `${value}%`);

const monthBounds = (month) => {
  const [y, m] = month.split("-").map(Number);
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return [`${month}-01`, `${month}-${String(last).padStart(2, "0")}`];
};

const MONEY_COLUMNS = [
  { key: "revenue", header: "Income (earned)", cell: (r) => usd(r.revenue_usd_cents ?? r.earned_usd_cents) },
  { key: "collected", header: "Collected", cell: (r) => usd(r.collected_usd_cents) },
  { key: "unbilled", header: "Not yet billed", cell: (r) => usd(r.unbilled_usd_cents) },
  { key: "delivery", header: "Delivery cost", cell: (r) => usd(r.delivery_cost_usd_cents ?? r.cost_usd_cents) },
  { key: "bench", header: "Bench cost", cell: (r) => usd(r.bench_cost_usd_cents) },
  { key: "overhead", header: "Internal staff (overhead)", cell: (r) => usd(r.overhead_cost_usd_cents) },
  { key: "expense", header: "Expenses", cell: (r) => usd(r.expense_cost_usd_cents ?? r.expense_usd_cents) },
  { key: "margin", header: "Margin", cell: (r) => usd(r.margin_usd_cents) },
  { key: "margin_pct", header: "Margin %", cell: (r) => pct(r.margin_pct) },
];

// A project's margin is its income less the delivery cost of the hours worked on it; bench,
// internal staff and expenses are not attributed to projects (they stay in the org P&L above).
const PROJECT_COLUMNS = [
  { key: "name", header: "Project", cell: (r) => r.name || "No project (cannot invoice)" },
  { key: "hours", header: "Billable hours", cell: (r) => r.billable_hours },
  ...MONEY_COLUMNS.filter((c) => ["revenue", "collected", "unbilled", "delivery", "margin", "margin_pct"].includes(c.key)),
  { key: "complete", header: "Cost known", cell: (r) => (r.cost_data_complete ? "Yes" : "No: salary or cost rate missing") },
];

function Tile({ label, value, hint }) {
  return (
    <div className="rounded-2xl border bg-white px-4 py-3">
      <div className="text-xs font-semibold text-gray-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-gray-900">{value}</div>
      {hint ? <div className="text-xs text-gray-500">{hint}</div> : null}
    </div>
  );
}

export default function PnlScreen() {
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [country, setCountry] = useState(""); // "" = every location
  const [report, setReport] = useState(null);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [partner, setPartner] = useState(null);
  const [lines, setLines] = useState([]);

  const load = useCallback(async () => {
    const [start, end] = monthBounds(month);
    setLoading(true);
    setError("");
    try {
      const [pnl, byProject] = await Promise.all([
        getPnl(start, end, country),
        getChainSummary(start, end, "project", country),
      ]);
      setReport(pnl);
      setProjects(byProject?.rows || []);
    } catch (err) {
      setError(err.message || "Failed to load the P&L.");
    } finally {
      setLoading(false);
    }
  }, [month, country]);

  const openPartner = async (row) => {
    const [start, end] = monthBounds(month);
    setPartner(row);
    try {
      const res = await getChainLines(start, end, { partnerUserId: row.key });
      setLines(res?.lines || []);
    } catch (err) {
      setError(err.message || "Failed to load the partner's lines.");
    }
  };

  useEffect(() => {
    load();
    setPartner(null);
    setLines([]);
  }, [load]);

  return (
    <div className="space-y-4">
      <Card
        title="P&L — Organization and Partners"
        subtitle="Income is work delivered in the month (billed or approved), costs are delivery, bench (billable staff off projects), internal staff overhead and approved expenses."
        icon={<BarChart3 className="h-4 w-4" />}
        right={
          <div className="flex items-center gap-2">
            <Input type="month" value={month} onChange={setMonth} />
            <select className="rounded-xl border bg-white px-2 py-2 text-sm" value={country}
              onChange={(e) => setCountry(e.target.value)} aria-label="Location">
              <option value="">All locations</option>
              {(report?.by_location || []).filter((l) => l.key).map((l) => <option key={l.key} value={l.key}>{l.key}</option>)}
              {country && !(report?.by_location || []).some((l) => l.key === country) ? <option value={country}>{country}</option> : null}
            </select>
            <Button variant="ghost" onClick={load} disabled={loading}>
              <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} /> Refresh
            </Button>
          </div>
        }
      >
        {error ? (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>
        ) : null}
        {report ? (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Tile label="Income" value={usd(report.revenue_usd_cents)} hint={`${usd(report.collected_usd_cents)} collected`} />
              <Tile
                label="Total cost"
                value={usd(report.total_cost_usd_cents)}
                hint={`delivery ${usd(report.delivery_cost_usd_cents)} · bench ${usd(report.bench_cost_usd_cents)} · internal staff ${usd(report.overhead_cost_usd_cents)} · expenses ${usd(report.expense_cost_usd_cents)}`}
              />
              <Tile label="Margin" value={usd(report.margin_usd_cents)} hint={pct(report.margin_pct)} />
              <Tile
                label="Waiting"
                value={usd(report.pending_approval_usd_cents)}
                hint={`timesheets awaiting approval · ${usd(report.pending_expenses_usd_cents)} expenses awaiting manager`}
              />
            </div>
            {!report.cost_data_complete ? (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                Cost is incomplete: {report.missing_cost_employee_ids.length} employee(s) have no salary or their business
                unit has no cost-rate config, so margin isn't shown. Add them and this fills in.
              </div>
            ) : null}
          </>
        ) : null}
      </Card>

      {report?.by_cost_object?.length ? (
        <Card title="By cost object (business unit x location)"
          subtitle="Each day's cost is charged to the business unit and location the person sat in that day.">
          <Table columns={[{ key: "name", header: "Cost object", cell: (r) => r.name }, ...MONEY_COLUMNS]}
            rows={report.by_cost_object} />
        </Card>
      ) : null}

      {report ? (
        <Card title="By partner" subtitle="Click a partner to see every timesheet behind their numbers.">
          <Table
            columns={[
              {
                key: "name",
                header: "Partner",
                cell: (r) => (
                  <button className="font-semibold text-blue-700 hover:underline" onClick={() => openPartner(r)}>
                    {r.key === "UNASSIGNED" ? "Unassigned" : r.name || r.key}
                  </button>
                ),
              },
              ...MONEY_COLUMNS,
            ]}
            rows={report.by_partner}
          />
        </Card>
      ) : null}

      {partner ? (
        <Card title={`${partner.key === "UNASSIGNED" ? "Unassigned" : partner.name || partner.key}: candidate to cash`}>
          {lines.length === 0 ? (
            <div className="py-6 text-center text-sm text-gray-500">No timesheets this month.</div>
          ) : (
            <Table
              columns={[
                { key: "week", header: "Week", cell: (r) => r.week_starting_date },
                { key: "employee", header: "Employee", cell: (r) => r.employee_name },
                { key: "job", header: "Job", cell: (r) => r.job_title },
                { key: "project", header: "Project", cell: (r) => r.project_name || "—" },
                { key: "client", header: "Client", cell: (r) => r.client_name },
                { key: "hours", header: "Hours", cell: (r) => r.billable_hours },
                { key: "timesheet", header: "Timesheet", cell: (r) => r.timesheet_status },
                { key: "invoice", header: "Invoice", cell: (r) => r.invoice_status || "not invoiced" },
                { key: "earned", header: "Income", cell: (r) => usd(r.earned_usd_cents) },
                { key: "cost", header: "Cost", cell: (r) => usd(r.cost_usd_cents) },
                { key: "margin", header: "Margin", cell: (r) => usd(r.margin_usd_cents) },
                { key: "flags", header: "Needs attention", cell: (r) => (r.flags || []).join(", ") || "—" },
              ]}
              rows={lines}
            />
          )}
        </Card>
      ) : null}

      {report?.by_company?.length ? (
        <Card
          title="By company"
          subtitle="The parent company owns the org-wide P&L above (all companies together). Each company's own P&L: income on the clients it contracts, cost of the people it employs, and intercompany charges (which cancel out at org level)."
        >
          <Table
            columns={[
              {
                key: "name",
                header: "Company",
                cell: (r) => (
                  <span>
                    {r.name}
                    {r.company_code ? <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">{r.company_code}</span> : null}
                  </span>
                ),
              },
              { key: "ic_rev", header: "Intercompany income", cell: (r) => usd(r.intercompany_revenue_usd_cents) },
              { key: "ic_cost", header: "Intercompany cost", cell: (r) => usd(r.intercompany_cost_usd_cents) },
              ...MONEY_COLUMNS.filter((c) => !["collected", "unbilled"].includes(c.key)),
            ]}
            rows={report.by_company}
          />
        </Card>
      ) : null}

      {report ? (
        <>
          <Card title="By business unit">
            <Table
              columns={[{ key: "name", header: "Business unit", cell: (r) => r.name || "Unassigned" }, ...MONEY_COLUMNS]}
              rows={report.by_business_unit}
            />
          </Card>
          <Card
            title="By project"
            subtitle="Income and delivery cost of the work booked to each project this month (by timesheet week). Bench, internal staff and expenses stay in the org totals above."
          >
            {projects.length === 0 ? (
              <div className="py-6 text-center text-sm text-gray-500">No project work this month.</div>
            ) : (
              <Table columns={PROJECT_COLUMNS} rows={projects} />
            )}
          </Card>
          <Card title="By client">
            <Table
              columns={[{ key: "name", header: "Client", cell: (r) => r.name || r.key }, ...MONEY_COLUMNS]}
              rows={report.by_client}
            />
          </Card>
        </>
      ) : null}
    </div>
  );
}
