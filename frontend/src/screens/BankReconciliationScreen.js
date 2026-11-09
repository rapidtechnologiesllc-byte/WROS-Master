// Bank reconciliation (a tab of P&L): money that reached the bank is matched to the invoice it pays.
// Finance uploads the statement (or types one credit); each credit is shown with the sent invoices for
// exactly that amount and the one the system suggests; Finance confirms, which pays the invoice on the
// date of the credit. Paid invoices that no bank credit confirms are listed so cash and the P&L agree.
import { useCallback, useEffect, useRef, useState } from "react";
import { Landmark, RefreshCw, Upload, CheckCircle2 } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import {
  getBankReconciliation,
  importBankStatement,
  matchBankCredit,
  recordBankCredit,
} from "../services/api/financeOperations";

function formatUsdCents(cents) {
  if (cents == null) return "—";
  return `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function invoiceLabel(invoice) {
  return [invoice.invoice_number || "(no number)", invoice.client_name, invoice.due_date ? `due ${invoice.due_date}` : null]
    .filter(Boolean)
    .join(" · ");
}

function importSummary(result) {
  const parts = [`${result.recorded} credit(s) recorded`];
  if (result.duplicates) parts.push(`${result.duplicates} already recorded`);
  if (result.debits_left_out) parts.push(`${result.debits_left_out} debit(s) left out`);
  if (result.unread.length) parts.push(`${result.unread.length} line(s) could not be read`);
  return parts.join(" · ");
}

function CreditRow({ credit, canConfirm, onMatched }) {
  const [invoiceId, setInvoiceId] = useState(credit.suggested_invoice_id || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      await matchBankCredit(credit.id, invoiceId);
      onMatched();
    } catch (err) {
      setError(err.message || "Could not match this credit.");
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="font-semibold text-gray-900 dark:text-gray-100">
            {formatUsdCents(credit.amount_usd_cents)} · {credit.transaction_date}
          </div>
          <div className="break-words text-xs text-gray-500 dark:text-gray-400">{credit.description}</div>
        </div>
        {credit.candidates.length === 0 ? (
          <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
            No sent invoice for this amount
          </span>
        ) : null}
      </div>
      {credit.candidates.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            aria-label="Invoice this credit pays"
            value={invoiceId}
            onChange={(e) => setInvoiceId(e.target.value)}
            disabled={busy}
            className="min-w-0 flex-1 rounded-lg border border-gray-400 bg-white px-3 py-2 text-sm text-gray-900 dark:bg-gray-800 dark:text-gray-100"
          >
            {credit.suggested_invoice_id ? null : <option value="">Choose the invoice this pays</option>}
            {credit.candidates.map((invoice) => (
              <option key={invoice.invoice_id} value={invoice.invoice_id}>
                {invoiceLabel(invoice)}
                {invoice.invoice_id === credit.suggested_invoice_id ? " (suggested)" : ""}
              </option>
            ))}
          </select>
          {canConfirm ? (
            <Button variant="success" disabled={busy || !invoiceId} onClick={confirm}>
              <CheckCircle2 className="h-4 w-4" /> {busy ? "Matching…" : "Confirm: this pays the invoice"}
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="mt-2 text-xs text-gray-600 dark:text-gray-300">
          A partial or combined payment, or money that is not for an invoice. It stays here until a sent invoice has
          exactly this total.
        </div>
      )}
      {error ? (
        <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>
      ) : null}
    </div>
  );
}

export default function BankReconciliationScreen() {
  const canRecord = hasPermission("finance-operations", "create");
  const fileInput = useRef(null);
  const [view, setView] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [imported, setImported] = useState(null);
  const [creditDate, setCreditDate] = useState(new Date().toISOString().slice(0, 10));
  const [creditAmount, setCreditAmount] = useState("");
  const [creditNote, setCreditNote] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setView(await getBankReconciliation());
    } catch (err) {
      setError(err.message || "Could not load the bank reconciliation.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    setError("");
    setImported(null);
    try {
      setImported(await importBankStatement(file));
      await load();
    } catch (err) {
      setError(err.message || "Could not read the statement.");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const cents = Math.round(Number(creditAmount) * 100);
  const creditReady = creditDate && creditNote.trim() && Number.isFinite(cents) && cents > 0;

  const saveCredit = async () => {
    setSaving(true);
    setError("");
    try {
      await recordBankCredit({ transactionDate: creditDate, amountUsdCents: cents, description: creditNote.trim() });
      setCreditAmount("");
      setCreditNote("");
      await load();
    } catch (err) {
      setError(err.message || "Could not record the credit.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      ) : null}

      {canRecord ? (
        <Card
          title="Money that reached the bank"
          subtitle="Upload the statement as CSV (columns: Date, Description, Amount or Credit). Only credits are recorded, each one once."
          icon={<Landmark className="h-4 w-4" />}
        >
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={fileInput}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              aria-label="Bank statement file"
              onChange={(e) => upload(e.target.files && e.target.files[0])}
            />
            <Button variant="primary" disabled={uploading} onClick={() => fileInput.current && fileInput.current.click()}>
              <Upload className="h-4 w-4" /> {uploading ? "Reading…" : "Upload statement"}
            </Button>
            {imported ? (
              <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{importSummary(imported)}</span>
            ) : null}
          </div>
          {imported && imported.unread.length ? (
            <ul className="mt-3 space-y-1 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {imported.unread.map((line) => (
                <li key={line.line}>
                  Line {line.line}: {line.reason}
                </li>
              ))}
            </ul>
          ) : null}
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <Input label="Or one credit: date" type="date" value={creditDate} onChange={setCreditDate} />
            <Input label="Amount (USD)" type="number" value={creditAmount} onChange={setCreditAmount} placeholder="0.00" />
            <div className="md:col-span-2">
              <Input
                label="Bank description / reference"
                value={creditNote}
                onChange={setCreditNote}
                placeholder="e.g. WIRE ACME BX-US-0042"
              />
            </div>
          </div>
          <div className="mt-3">
            <Button variant="secondary" disabled={saving || !creditReady} onClick={saveCredit}>
              {saving ? "Recording…" : "Record this credit"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card
        title="Credits waiting to be matched"
        subtitle={
          view
            ? `${view.transactions.length} unmatched credit(s) · ${view.awaiting_payment_count} sent invoice(s) awaiting payment`
            : "Each credit with the sent invoices for exactly that amount"
        }
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        }
      >
        {loading && !view ? <div className="text-sm text-gray-500">Loading…</div> : null}
        {view && view.transactions.length === 0 ? (
          <div className="text-sm text-gray-600 dark:text-gray-300">Every recorded credit is matched to its invoice.</div>
        ) : null}
        <div className="space-y-3">
          {(view ? view.transactions : []).map((credit) => (
            <CreditRow key={credit.id} credit={credit} canConfirm={canRecord} onMatched={load} />
          ))}
        </div>
      </Card>

      {view && view.unmatched_paid_invoices.length ? (
        <Card
          title="Paid invoices with no bank credit"
          subtitle="Marked paid, but no bank transaction confirms the money arrived. Check the statement for each."
        >
          <ul className="divide-y text-sm">
            {view.unmatched_paid_invoices.map((invoice) => (
              <li key={invoice.invoice_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="text-gray-900 dark:text-gray-100">{invoiceLabel(invoice)}</span>
                <span className="font-semibold text-gray-900 dark:text-gray-100">{formatUsdCents(invoice.total_usd_cents)}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}
