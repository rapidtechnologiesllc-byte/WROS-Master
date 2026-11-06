import React from "react";
import { openExpenseReceipt } from "../services/api/expenses";

// Result of the automatic receipt check (backend app.services.expense_receipt_service):
// MATCHED approves the manager step by itself; MISMATCH / UNREADABLE wait for the manager.
const LOOK = {
  MATCHED: { label: "Receipt verified", tone: "bg-emerald-100 text-emerald-800" },
  MISMATCH: { label: "Needs review", tone: "bg-amber-100 text-amber-800" },
  UNREADABLE: { label: "Unreadable - review", tone: "bg-amber-100 text-amber-800" },
  NOT_ATTACHED: { label: "No receipt", tone: "bg-gray-100 text-gray-700" },
};

export const checkDetails = (detail) => {
  try {
    const parsed = JSON.parse(detail || "{}");
    return { reasons: parsed.reasons || [], receipts: parsed.receipts || [] };
  } catch (err) {
    console.error("[ReceiptCheck] Unreadable receipt_check_detail:", err);
    return { reasons: ["Check details unavailable"], receipts: [] };
  }
};

export default function ReceiptCheck({ expense, onError, compact }) {
  const status = expense.receipt_check_status || "NOT_ATTACHED";
  const look = LOOK[status] || LOOK.NOT_ATTACHED;
  const { reasons } = checkDetails(expense.receipt_check_detail);
  const receipts = expense.receipts || [];
  const view = async (receiptId) => {
    try {
      await openExpenseReceipt(expense.id, receiptId);
    } catch (err) {
      console.error("[ReceiptCheck] Failed to open receipt:", err);
      if (onError) onError(`Failed to open receipt: ${err.message}`);
    }
  };
  return (
    <div className="flex flex-col gap-1">
      <span className={`w-fit rounded-full px-2 py-0.5 text-xs font-semibold ${look.tone}`} title={reasons.join("\n")}>
        {look.label}
      </span>
      {!compact && reasons.length > 0 && <span className="text-xs text-amber-700">{reasons.join("; ")}</span>}
      {!compact && receipts.length > 1
        ? receipts.map((r, i) => (
          <button key={r.id} type="button" onClick={() => view(r.id)} className="w-fit text-xs text-blue-600 hover:underline">
            View receipt {i + 1}
          </button>
        ))
        : !compact && status !== "NOT_ATTACHED" && (
          <button type="button" onClick={() => view()} className="w-fit text-xs text-blue-600 hover:underline">
            View receipt
          </button>
        )}
    </div>
  );
}
