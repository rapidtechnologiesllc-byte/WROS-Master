// A manager's review of one expense, opened from My Tasks: the expense, its receipts on screen, and the
// system's check of one against the other. Only a decision here closes the task.
import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "./ui";
import ReceiptCheck, { checkDetails } from "./ReceiptCheck";
import { fetchExpenseReceiptBlob, getExpense, managerApproveExpense, managerRejectExpense } from "../services/api/expenses";
import { expenseDates, expenseSubject } from "../utils/expenseAttribution";

const money = (cents) => `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const VERDICT = {
  MATCHED: { text: "The receipts match this expense.", tone: "border-emerald-200 bg-emerald-50 text-emerald-900" },
  MISMATCH: { text: "The receipts don't match this expense. Look at the notes below.", tone: "border-amber-200 bg-amber-50 text-amber-900" },
  UNREADABLE: { text: "The system could not read a receipt, so nothing has been checked. Compare it yourself.", tone: "border-amber-200 bg-amber-50 text-amber-900" },
  NOT_ATTACHED: { text: "No receipt is attached.", tone: "border-rose-200 bg-rose-50 text-rose-900" },
};

function Fact({ label, children }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase text-gray-500">{label}</div>
      <div className="text-sm text-gray-900">{children || "—"}</div>
    </div>
  );
}

function SystemCheck({ expense }) {
  const { reasons, receipts } = checkDetails(expense.receipt_check_detail);
  const verdict = VERDICT[expense.receipt_check_status] || VERDICT.NOT_ATTACHED;
  return (
    <div className={`rounded-lg border p-3 ${verdict.tone}`}>
      <div className="text-xs font-semibold uppercase">System check</div>
      <div className="mt-1 text-sm font-semibold">{verdict.text}</div>
      {reasons.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-sm">
          {reasons.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      )}
      {receipts.length > 0 && (
        <table className="mt-3 w-full text-left text-xs">
          <thead>
            <tr><th className="pr-2 py-1">Receipt</th><th className="pr-2 py-1">Merchant</th><th className="pr-2 py-1">Total read</th><th className="py-1">Date read</th></tr>
          </thead>
          <tbody>
            {receipts.map((r) => (
              <tr key={r.id} className="border-t border-black/10">
                <td className="pr-2 py-1 break-all">{r.file_name || "Receipt"}</td>
                <td className="pr-2 py-1">{r.merchant || "—"}</td>
                <td className="pr-2 py-1">{r.total != null ? `${r.currency || ""} ${Number(r.total).toFixed(2)}`.trim() : "not found"}</td>
                <td className="py-1">{r.date || "not found"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ReceiptViewer({ expense }) {
  const receipts = expense.receipts || [];
  const [selected, setSelected] = useState(receipts[0]?.id || null);
  const [view, setView] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selected) return undefined;
    let url = null;
    let cancelled = false;
    setView(null);
    setError("");
    fetchExpenseReceiptBlob(expense.id, selected)
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setView({ url, isPdf: blob.type === "application/pdf" });
      })
      .catch((err) => {
        console.error("[ExpenseReview] Failed to load receipt:", err);
        if (!cancelled) setError(`Couldn't load this receipt: ${err.message}`);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [expense.id, selected]);

  if (!receipts.length) return <div className="rounded-lg border p-4 text-sm text-gray-500">No receipt is attached.</div>;
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {receipts.map((r, i) => (
          <button
            key={r.id}
            type="button"
            onClick={() => setSelected(r.id)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${selected === r.id ? "border-bx-orange bg-bx-orange text-white" : "border-gray-300 text-gray-700"}`}
          >
            Receipt {i + 1}
          </button>
        ))}
        {view && (
          <a href={view.url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">Open in a new tab</a>
        )}
      </div>
      {error && <div className="text-sm text-rose-700">{error}</div>}
      {!view && !error && <div className="rounded-lg border p-4 text-sm text-gray-500">Loading receipt…</div>}
      {view && (view.isPdf
        ? <iframe title="Receipt" src={view.url} className="h-[32rem] w-full rounded-lg border" />
        : <img alt="Receipt" src={view.url} className="max-h-[32rem] w-full rounded-lg border object-contain" />)}
    </div>
  );
}

export default function ExpenseReviewModal({ expenseId, onClose, onDone }) {
  const [expense, setExpense] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    try {
      setExpense(await getExpense(expenseId));
    } catch (err) {
      console.error("[ExpenseReview] Failed to load expense:", err);
      setError(`Couldn't load this expense: ${err.message}`);
    }
  }, [expenseId]);

  useEffect(() => { load(); }, [load]);

  const decide = async (action, message) => {
    setBusy(true);
    setError("");
    try {
      await action();
      onDone(message);
    } catch (err) {
      console.error("[ExpenseReview] Decision failed:", err);
      setError(err.message || "Couldn't save your decision.");
      setBusy(false);
    }
  };

  const pending = expense?.manager_approval_status === "PENDING";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4">
      <div className="w-full max-w-5xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Review expense</h2>
            {expense && <p className="text-sm text-gray-500">Logged by {expense.logged_by_name || expense.logged_by_user_id}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="text-gray-500 hover:text-gray-800"><X className="h-5 w-5" /></button>
        </div>
        {error && <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
        {!expense && !error && <div className="py-8 text-center text-sm text-gray-500">Loading…</div>}
        {expense && (
          <div className="grid gap-5 lg:grid-cols-2">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Fact label="Amount">{money(expense.amount_usd_cents)}</Fact>
                <Fact label="Dates">{expenseDates(expense)}</Fact>
                <Fact label="Purpose">{expense.purpose.replace(/_/g, " ")}</Fact>
                <Fact label="For">{expenseSubject(expense)}</Fact>
                <Fact label="Category">{`${expense.expense_category}${expense.travel_type ? ` / ${expense.travel_type}` : ""}`}</Fact>
                <Fact label="Location">{expense.location}</Fact>
                <Fact label="Trip">{expense.trip_label}</Fact>
                <Fact label="Receipt ref">{expense.receipt_ref}</Fact>
              </div>
              <Fact label="Description">{expense.description}</Fact>
              <SystemCheck expense={expense} />
              {(expense.edits || []).length > 0 && (
                <div className="rounded-lg border p-3">
                  <div className="text-xs font-semibold uppercase text-gray-500">Changes since it was logged</div>
                  <ul className="mt-1 space-y-1 text-sm text-gray-700">
                    {expense.edits.map((edit, i) => (
                      <li key={`${edit.created_at}-${i}`}>
                        {edit.summary}
                        <span className="text-xs text-gray-500"> · {edit.changed_by_name || "System"}{edit.created_at ? `, ${new Date(edit.created_at).toLocaleString()}` : ""}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {pending ? (
                rejecting ? (
                  <div>
                    <label className="block">
                      <div className="mb-1 text-xs font-semibold text-gray-700">Why are you rejecting it? They will see this. *</div>
                      <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} className="w-full rounded-lg border px-3 py-2 text-sm" />
                    </label>
                    <div className="mt-2 flex gap-2">
                      <Button
                        disabled={busy || !reason.trim()}
                        onClick={() => decide(() => managerRejectExpense(expense.id, reason.trim()), "Expense rejected. It won't count in the P&L.")}
                      >
                        Reject expense
                      </Button>
                      <Button variant="ghost" disabled={busy} onClick={() => setRejecting(false)}>Back</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button disabled={busy} onClick={() => decide(() => managerApproveExpense(expense.id), "Expense approved. It now counts in the P&L and moves to Finance.")}>
                      {busy ? "Saving…" : "Approve"}
                    </Button>
                    <Button variant="ghost" disabled={busy} onClick={() => setRejecting(true)}>Reject</Button>
                  </div>
                )
              ) : (
                <div className="text-sm text-gray-600">This expense has already been decided: <ReceiptCheck expense={expense} compact /></div>
              )}
            </div>
            <ReceiptViewer expense={expense} />
          </div>
        )}
      </div>
    </div>
  );
}
