// One visit or event and its expense lines (CEO 2026-11-14): "everything related to that visit should be grouped and
// individual itemized rows should be created for each receipt ... click on it and add, remove, edit and see all the
// individual expense rows". Each receipt waits here until its person says what it was for; then it is its own line,
// approved and paid like any expense.
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Receipt } from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import ReceiptCheck from "../components/ReceiptCheck";
import { listClients } from "../services/api/clients";
import {
  addExpenseVisitReceipts, getExpenseVisit, openExpenseVisitDraft, removeExpense, removeExpenseVisitDraft,
  submitExpenseVisitDraft, updateExpenseVisit,
} from "../services/api/expenses";
import { expenseDates } from "../utils/expenseAttribution";
import {
  CATEGORIES, LogExpenseForm, PURPOSE_LABELS, TRAVEL_TYPES, expenseStatus, formatUsdCents, visitStatus,
} from "./MyExpensesScreen";

const centsText = (cents) => (cents == null ? "" : (cents / 100).toFixed(2));

const draftForm = (draft, visit) => ({
  description: draft.merchant || "",
  expenseCategory: "TRAVEL",
  travelType: "OTHER",
  amount: centsText(draft.amount_usd_cents),
  expenseDate: draft.expense_date || visit.start_date || "",
});

function DraftRow({ visit, draft, onDone, onError }) {
  const [form, setForm] = useState(() => draftForm(draft, visit));
  const [saving, setSaving] = useState(false);
  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const save = async () => {
    const cents = Math.round(parseFloat(form.amount || "0") * 100);
    if (!form.description.trim()) return onError(`${draft.file_name}: say what this receipt was for.`);
    if (!cents || cents <= 0) return onError(`${draft.file_name}: enter the amount (USD).`);
    if (!form.expenseDate) return onError(`${draft.file_name}: enter the date.`);
    setSaving(true);
    try {
      await submitExpenseVisitDraft(visit.id, draft.id, {
        description: form.description.trim(),
        expense_category: form.expenseCategory,
        travel_type: form.expenseCategory === "TRAVEL" ? form.travelType : null,
        amount_usd_cents: cents,
        expense_date: form.expenseDate,
      });
      onDone();
    } catch (err) {
      onError(`${draft.file_name}: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const discard = async () => {
    setSaving(true);
    try {
      await removeExpenseVisitDraft(visit.id, draft.id);
      onDone();
    } catch (err) {
      onError(`${draft.file_name}: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3" data-draft={draft.id}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <button type="button" className="font-semibold text-blue-600 hover:underline"
          onClick={() => openExpenseVisitDraft(visit.id, draft.id).catch((err) => onError(err.message))}>
          {draft.file_name || "Receipt"}
        </button>
        {draft.read_error ? (
          <span className="text-amber-800">Couldn't be read automatically: enter the amount and date.</span>
        ) : draft.currency && draft.currency.toUpperCase() !== "USD" ? (
          <span className="text-amber-800">The receipt is in {draft.currency}: enter the amount in USD.</span>
        ) : (
          <span className="text-gray-600">Amount and date filled in from the receipt: check them.</span>
        )}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-6">
        <div className="sm:col-span-2">
          <Input label="What was it for? *" value={form.description} onChange={set("description")}
            placeholder="Taxi from airport to client" />
        </div>
        <Select label="Category" value={form.expenseCategory} onChange={set("expenseCategory")} options={CATEGORIES} />
        {form.expenseCategory === "TRAVEL" ? (
          <Select label="Travel type" value={form.travelType} onChange={set("travelType")} options={TRAVEL_TYPES} />
        ) : <div />}
        <Input label="Amount (USD) *" value={form.amount} onChange={set("amount")} placeholder="45.00" />
        <Input label="Date *" type="date" value={form.expenseDate} onChange={set("expenseDate")} />
      </div>
      <div className="mt-2 flex gap-2">
        <Button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save line"}</Button>
        <Button variant="ghost" onClick={discard} disabled={saving}>Remove receipt</Button>
      </div>
    </div>
  );
}

export default function ExpenseVisitScreen() {
  const { visitId } = useParams();
  const navigate = useNavigate();
  const [visit, setVisit] = useState(null);
  const [clients, setClients] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [progress, setProgress] = useState("");
  const [editing, setEditing] = useState(null);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");

  const loadClients = useCallback(async () => {
    const data = await listClients();
    setClients(data?.clients || []);
  }, []);

  const load = useCallback(async () => {
    try {
      setVisit(await getExpenseVisit(visitId));
    } catch (err) {
      console.error("[ExpenseVisit] Failed to load the visit:", err);
      setError(`Couldn't load this visit: ${err.message}`);
    }
  }, [visitId]);

  useEffect(() => {
    load();
    loadClients().catch((err) => setError(`Couldn't load your clients: ${err.message}`));
  }, [load, loadClients]);

  const addReceipts = async (files) => {
    if (!files.length) return;
    setError("");
    try {
      await addExpenseVisitReceipts(visitId, files, (done, total) => setProgress(`Uploading receipt ${done} of ${total}…`));
    } catch (err) {
      setError(err.message);
    } finally {
      setProgress("");
      load();
    }
  };

  const removeLine = async (line) => {
    if (!window.confirm(`Remove "${line.description || line.expense_category}" (${formatUsdCents(line.amount_usd_cents)}) from this visit?`)) return;
    setError("");
    try {
      await removeExpense(line.id);
      setNotice("Line removed.");
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const saveName = async () => {
    try {
      setVisit(await updateExpenseVisit(visitId, { name }));
      setRenaming(false);
    } catch (err) {
      setError(err.message);
    }
  };

  if (!visit) {
    return (
      <div className="p-6">
        {error ? <div className="text-sm text-rose-700">{error}</div> : <div className="text-sm text-gray-500">Loading…</div>}
      </div>
    );
  }

  const status = visitStatus(visit.status);
  const who = visit.spend_for === "INTERNAL"
    ? "Personal / internal"
    : visit.spend_for === "CLIENT"
      ? visit.client_name
      : (visit.client_splits || []).map((s) => {
        const client = clients.find((c) => c.id === s.client_id);
        return `${client?.company_name || "Client"} ${s.percent}%`;
      }).join(", ");
  const dates = visit.start_date
    ? (visit.end_date && visit.end_date !== visit.start_date ? `${visit.start_date} to ${visit.end_date}` : visit.start_date)
    : "";

  const rows = visit.lines.map((line) => {
    const lineStatus = expenseStatus(line);
    return {
      id: line.id,
      date: expenseDates(line),
      description: line.description || "—",
      category: `${line.expense_category}${line.travel_type ? ` / ${line.travel_type}` : ""}`,
      amount: formatUsdCents(line.amount_usd_cents),
      status: (
        <div>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${lineStatus.color}`}>{lineStatus.label}</span>
          {line.manager_review_note ? <div className="mt-1 text-xs text-rose-700">Manager: {line.manager_review_note}</div> : null}
        </div>
      ),
      receipt: <ReceiptCheck expense={line} />,
      actions: line.payment_status === "PENDING" ? (
        <div className="flex gap-1">
          <Button variant="ghost" onClick={() => { setEditing(line); window.scrollTo({ top: 0 }); }}>Edit</Button>
          <Button variant="ghost" onClick={() => removeLine(line)}>Remove</Button>
        </div>
      ) : null,
    };
  });

  return (
    <div className="space-y-4 p-6">
      <button type="button" className="flex items-center gap-1 text-sm text-gray-600 hover:underline" onClick={() => navigate("/my-expenses")}>
        <ArrowLeft className="h-4 w-4" /> My Expenses
      </button>
      <Card
        title={visit.name}
        subtitle={[PURPOSE_LABELS[visit.purpose], visit.conference_name, who, dates, visit.location].filter(Boolean).join(" · ")}
        icon={<Receipt className="h-4 w-4" />}
        right={
          <div className="flex items-center gap-3">
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${status.color}`}>{status.label}</span>
            <span className="text-sm font-semibold text-gray-900">{formatUsdCents(visit.total_usd_cents)}</span>
          </div>
        }
      >
        {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
        {notice ? <div className="mb-3 text-xs text-emerald-700">{notice}</div> : null}

        <div className="mb-4 flex flex-wrap items-end gap-3">
          {renaming ? (
            <>
              <Input label="Visit name" value={name} onChange={setName} />
              <Button onClick={saveName}>Save name</Button>
              <Button variant="ghost" onClick={() => setRenaming(false)}>Cancel</Button>
            </>
          ) : (
            <Button variant="ghost" onClick={() => { setName(visit.name); setRenaming(true); }}>Rename visit</Button>
          )}
          <div>
            <label htmlFor="visit-receipts" className="mb-1 block text-xs font-semibold text-gray-700">
              {progress || "Add receipts to this visit"}
            </label>
            <input
              id="visit-receipts"
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp,application/pdf"
              onChange={(e) => { addReceipts(Array.from(e.target.files || [])); e.target.value = ""; }}
              className="block text-sm"
            />
          </div>
        </div>

        {visit.drafts.length ? (
          <div className="mb-4 space-y-2">
            <div className="text-sm font-semibold text-gray-900">
              {visit.drafts.length} receipt{visit.drafts.length === 1 ? "" : "s"} to describe
            </div>
            <div className="text-xs text-gray-600">
              Each becomes its own line of this visit and goes to your manager once you save it.
            </div>
            {visit.drafts.map((draft) => (
              <DraftRow key={draft.id} visit={visit} draft={draft} onError={setError}
                onDone={() => { setError(""); load(); }} />
            ))}
          </div>
        ) : null}

        {editing ? (
          <LogExpenseForm
            key={editing.id}
            expense={editing}
            clients={clients}
            reloadClients={loadClients}
            onCancel={() => setEditing(null)}
            onSaved={() => { setEditing(null); load(); }}
          />
        ) : null}

        <Table
          columns={[
            { key: "date", header: "Date" },
            { key: "description", header: "What it was for" },
            { key: "category", header: "Category" },
            { key: "amount", header: "Amount" },
            { key: "status", header: "Status" },
            { key: "receipt", header: "Receipt" },
            { key: "actions", header: "" },
          ]}
          rows={rows}
        />
        {!visit.lines.length && !visit.drafts.length ? (
          <div className="py-4 text-center text-sm text-gray-500">No lines yet: add the visit's receipts above.</div>
        ) : null}
      </Card>
    </div>
  );
}
