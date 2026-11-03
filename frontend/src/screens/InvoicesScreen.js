// HRMS-0907 (S-226 Invoicing) -- generate a DRAFT invoice for a
// project+billing period from approved timesheets, then walk it through
// Approve -> Send -> Mark Paid. Each transition is always an explicit
// human action -- no automatic sending, per invoice_service.py.
import { Fragment, useCallback, useEffect, useState } from "react";
import { Receipt, RefreshCw, CheckCircle2, Send, DollarSign } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import cx from "../utils/cx";
import VendorInvoicesTab from "../components/VendorInvoicesTab";
import {
  runAutoInvoicing,
  approveInvoice,
  sendInvoice,
  recordExternalDelivery,
  recordInvoicePayment,
  getInvoices,
  getArAging,
} from "../services/api/invoices";

const STATUS_STYLES = {
  DRAFT: "border-gray-200 bg-gray-50 text-gray-800",
  APPROVED: "border-amber-200 bg-amber-50 text-amber-800",
  SENT: "border-blue-200 bg-blue-50 text-blue-800",
  PAID: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

function formatUsdCents(cents) {
  if (cents == null) return "—";
  return `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// CEO 2026-11-02: invoicing "has to be automatic". The daily job drafts each project's invoice
// from approved timesheets (last month first); Finance approves, then it is emailed to the client.
// "Check now" runs the same job immediately -- nothing reaches a client before Finance approves.
const RUN_OUTCOMES = [
  ["awaiting", "draft(s) waiting for your review"],
  ["waiting", "project(s) waiting for timesheet approval"],
  ["held", "held -- see your Finance tasks"],
  ["unlinked", "allocation(s) with approved hours but no project"],
  ["failed", "failed (logged)"],
];

function AutoInvoicingPanel({ onRan }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const run = async () => {
    setRunning(true);
    setError("");
    try {
      const res = await runAutoInvoicing();
      setResult(res);
      onRan();
    } catch (err) {
      setError(err.message || "Could not run invoicing.");
    } finally {
      setRunning(false);
    }
  };

  const outcomes = result ? RUN_OUTCOMES.filter(([key]) => result[key]) : [];
  return (
    <div className="flex flex-1 flex-wrap items-center gap-3 rounded-2xl border bg-gray-50 px-4 py-3">
      <div className="min-w-0 flex-1 text-xs text-gray-700">
        Invoices draft themselves every day from approved timesheets, per project and month. You review and approve; the
        client is then emailed automatically.
        {result ? (
          <div className="mt-1 font-semibold text-gray-900">
            {outcomes.length
              ? outcomes.map(([key, label]) => `${result[key]} ${label}`).join(" · ")
              : `Nothing due for ${result.period}: no approved, uninvoiced timesheets.`}
          </div>
        ) : null}
        {error ? <div className="mt-1 text-rose-700">{error}</div> : null}
      </div>
      <Button variant="primary" onClick={run} disabled={running}>
        <Receipt className="h-4 w-4" /> {running ? "Checking…" : "Check for due invoices now"}
      </Button>
    </div>
  );
}

function InvoiceRow({ invoice, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [portalNote, setPortalNote] = useState("");
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState((invoice.total_usd_cents / 100).toFixed(2));
  const [reference, setReference] = useState("");
  const emailInFlight = ["QUEUED", "DRAFTED"].includes(invoice.delivery_status);

  const run = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn(invoice.id);
      onChanged();
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-gray-900">
            {invoice.invoice_number || "(no number)"} · {formatUsdCents(invoice.total_usd_cents)} {invoice.currency}
          </div>
          <div className="text-xs text-gray-500">
            {[invoice.client_name, invoice.project_name].filter(Boolean).join(" · ")}
            {invoice.issuing_company_name ? ` · issued by ${invoice.issuing_company_name}` : ""}
          </div>
          <div className="text-xs text-gray-500">
            {invoice.billing_period_start} → {invoice.billing_period_end} · {invoice.line_items.length} line item(s)
            {invoice.po_numbers ? ` · PO ${invoice.po_numbers}` : ""}
            {invoice.due_date ? ` · due ${invoice.due_date}` : ""}
          </div>
          {invoice.delivery_status ? (
            <div className="text-xs text-gray-500">
              Delivery: {invoice.delivery_channel === "EXTERNAL" ? "outside email" : `email to ${invoice.delivery_to}`} ·{" "}
              {invoice.delivery_status}
            </div>
          ) : null}
        </div>
        <span className={cx("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", STATUS_STYLES[invoice.status])}>
          {invoice.status}
        </span>
      </div>

      {error ? (
        <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        {invoice.status === "DRAFT" ? (
          <Button variant="success" disabled={busy} onClick={() => run(approveInvoice)}>
            <CheckCircle2 className="h-4 w-4" /> Approve
          </Button>
        ) : null}
        {invoice.status === "APPROVED" ? (
          <>
            <Button variant="primary" disabled={busy || emailInFlight} onClick={() => run(sendInvoice)}>
              <Send className="h-4 w-4" /> {emailInFlight ? "Email queued" : "Email to client"}
            </Button>
            <Input
              placeholder="Or: how it was delivered (e.g. client portal)"
              value={portalNote}
              onChange={setPortalNote}
            />
            <Button
              variant="ghost"
              disabled={busy || !portalNote.trim()}
              onClick={() => run((id) => recordExternalDelivery(id, portalNote.trim()))}
            >
              Mark delivered
            </Button>
          </>
        ) : null}
        {invoice.status === "SENT" ? (
          <>
            <Input type="date" value={paidOn} onChange={setPaidOn} />
            <Input type="number" value={amount} onChange={setAmount} />
            <Input placeholder="Bank / UTR reference" value={reference} onChange={setReference} />
            <Button
              variant="success"
              disabled={busy || !reference.trim() || !paidOn}
              onClick={() =>
                run((id) =>
                  recordInvoicePayment(id, {
                    paidOn,
                    amountUsdCents: Math.round(parseFloat(amount || "0") * 100),
                    reference: reference.trim(),
                  })
                )
              }
            >
              <DollarSign className="h-4 w-4" /> Record payment
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}

function ArAgingTab() {
  const [aging, setAging] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState("");

  useEffect(() => {
    getArAging().then(setAging).catch((err) => setError(err.message || "Failed to load AR aging."));
  }, []);

  if (error) {
    return <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>;
  }
  if (!aging) return <div className="py-8 text-center text-sm text-gray-500">Loading…</div>;
  const cell = "px-3 py-2 text-right";
  return (
    <div className="overflow-x-auto">
      <div className="mb-2 text-xs text-gray-500">
        Unpaid sent invoices as of {aging.as_of}, aged by due date (sent date + the client's payment terms).
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-xs text-gray-700">
          <tr>
            <th className="px-3 py-2 text-left">Client</th>
            <th className="px-3 py-2 text-right">Terms</th>
            {aging.buckets.map((b) => <th key={b} className={cell}>{b === "current" ? "Not yet due" : `${b} days`}</th>)}
            <th className={cell}>Total</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {aging.clients.length === 0 ? (
            <tr><td colSpan={aging.buckets.length + 3} className="py-6 text-center text-gray-500">Nothing outstanding.</td></tr>
          ) : null}
          {aging.clients.map((c) => (
            <Fragment key={c.client_id}>
              <tr className="cursor-pointer hover:bg-gray-50"
                onClick={() => setOpen(open === c.client_id ? "" : c.client_id)}>
                <td className="px-3 py-2 font-medium text-gray-900">{c.client_name}</td>
                <td className={cell}>{c.payment_terms_days != null ? `net ${c.payment_terms_days}` : "—"}</td>
                {aging.buckets.map((b) => <td key={b} className={cell}>{c.buckets[b] ? formatUsdCents(c.buckets[b]) : "—"}</td>)}
                <td className={cx(cell, "font-semibold")}>{formatUsdCents(c.total_usd_cents)}</td>
              </tr>
              {open === c.client_id ? c.invoices.map((i) => (
                <tr key={i.invoice_id} className="bg-gray-50 text-xs text-gray-600">
                  <td className="px-6 py-1" colSpan={2}>{i.invoice_number || i.invoice_id}</td>
                  <td className="px-3 py-1" colSpan={aging.buckets.length}>
                    due {i.due_date}{i.days_past_due ? ` · ${i.days_past_due} days past due` : ""} · {i.bucket}
                  </td>
                  <td className={cell}>{formatUsdCents(i.total_usd_cents)}</td>
                </tr>
              )) : null}
            </Fragment>
          ))}
          <tr className="bg-gray-50 font-semibold">
            <td className="px-3 py-2" colSpan={2}>Total</td>
            {aging.buckets.map((b) => <td key={b} className={cell}>{formatUsdCents(aging.totals[b])}</td>)}
            <td className={cell}>{formatUsdCents(aging.total_usd_cents)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function InvoicesScreen() {
  const [invoices, setInvoices] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  // a task link can open a tab directly (e.g. /invoices?tab=vendor from "Pay the vendor: the client has paid")
  const [tab, setTab] = useState(() => {
    const wanted = new URLSearchParams(window.location.search).get("tab");
    return ["invoices", "aging", "vendor"].includes(wanted) ? wanted : "invoices";
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getInvoices(statusFilter ? { status: statusFilter } : {});
      setInvoices(res?.invoices || []);
    } catch (err) {
      setError(err.message || "Failed to load invoices.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="grid gap-4">
      <Card
        title="Invoices"
        subtitle="Client invoices draft themselves from approved timesheets; Finance approves and the client is emailed. Sub-vendors are paid only after the client pays."
        icon={<Receipt className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        <div className="mb-4 flex gap-1">
          {[["invoices", "Client invoices"], ["aging", "AR aging"], ["vendor", "Sub-vendor invoices"]].map(([key, label]) => (
            <button key={key} type="button" onClick={() => setTab(key)}
              className={cx("rounded-lg px-3 py-1.5 text-sm font-semibold",
                tab === key ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100")}>
              {label}
            </button>
          ))}
        </div>
        {tab === "aging" ? <ArAgingTab /> : null}
        {tab === "vendor" ? <VendorInvoicesTab /> : null}

        {tab === "invoices" && error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {tab === "invoices" ? (
        <>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <AutoInvoicingPanel onRan={load} />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
          >
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="APPROVED">Approved</option>
            <option value="SENT">Sent</option>
            <option value="PAID">Paid</option>
          </select>
        </div>

        <div className="grid gap-3">
          {loading ? (
            <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
          ) : invoices.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">No invoices yet.</div>
          ) : (
            invoices.map((inv) => <InvoiceRow key={inv.id} invoice={inv} onChanged={load} />)
          )}
        </div>
        </>
        ) : null}
      </Card>
    </div>
  );
}
