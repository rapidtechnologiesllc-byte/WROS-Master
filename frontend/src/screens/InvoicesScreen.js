// HRMS-0907 (S-226 Invoicing) -- generate a DRAFT invoice for a
// project+billing period from approved timesheets, then walk it through
// Approve -> Send -> Mark Paid. Each transition is always an explicit
// human action -- no automatic sending, per invoice_service.py.
import { useEffect, useState } from "react";
import { Receipt, RefreshCw, CheckCircle2, Send, DollarSign } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import cx from "../utils/cx";
import {
  generateInvoice,
  approveInvoice,
  sendInvoice,
  markInvoicePaid,
  getInvoices,
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

function GenerateInvoiceForm({ onGenerated }) {
  const [open, setOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!projectId.trim() || !periodStart || !periodEnd) {
      setError("Project ID and both period dates are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await generateInvoice(projectId.trim(), periodStart, periodEnd);
      setProjectId("");
      setPeriodStart("");
      setPeriodEnd("");
      setOpen(false);
      onGenerated();
    } catch (err) {
      setError(err.message || "Failed to generate invoice.");
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <Button variant="primary" onClick={() => setOpen(true)}>
        <Receipt className="h-4 w-4" /> Generate Invoice
      </Button>
    );
  }

  return (
    <div className="rounded-2xl border p-4">
      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="Project ID" value={projectId} onChange={setProjectId} placeholder="project UUID" />
        <Input label="Period start" type="date" value={periodStart} onChange={setPeriodStart} />
        <Input label="Period end" type="date" value={periodEnd} onChange={setPeriodEnd} />
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={saving} onClick={handleSubmit}>
          {saving ? "Generating…" : "Generate"}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function InvoiceRow({ invoice, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
          <div className="font-semibold text-gray-900">{formatUsdCents(invoice.total_usd_cents)} {invoice.currency}</div>
          <div className="text-xs text-gray-500">
            {invoice.billing_period_start} → {invoice.billing_period_end} · {invoice.line_items.length} line item(s)
          </div>
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
          <Button variant="primary" disabled={busy} onClick={() => run(sendInvoice)}>
            <Send className="h-4 w-4" /> Send
          </Button>
        ) : null}
        {invoice.status === "SENT" ? (
          <Button variant="success" disabled={busy} onClick={() => run(markInvoicePaid)}>
            <DollarSign className="h-4 w-4" /> Mark Paid
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export default function InvoicesScreen() {
  const [invoices, setInvoices] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
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
  };

  useEffect(() => {
    load();
  }, [statusFilter]);

  return (
    <div className="grid gap-4">
      <Card
        title="Invoices"
        subtitle="Generated from approved, undisputed timesheets for a project+billing period. Draft → Approve → Send → Mark Paid, always explicit human actions."
        icon={<Receipt className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <GenerateInvoiceForm onGenerated={load} />
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
      </Card>
    </div>
  );
}
