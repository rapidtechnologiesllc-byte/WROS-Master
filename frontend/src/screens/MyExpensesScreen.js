// Self-service expense logging, 2026-08-05. Avinash: "the expense is
// logged by employee so they need to login to their portal and add
// their expense." Every submission here is attributed to whoever is
// logged in -- there is no field to log an expense as someone else.
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Receipt, Plus } from "lucide-react";
import { Card, Button, Input, Select, TextArea, Table } from "../components/ui";
import { listClients, createClient } from "../services/api/clients";
import {
  addExpenseVisitReceipts, createExpense, listExpenseEmployees, createExpenseVisit, listMyExpenses, openExpenseReceipt, removeExpenseReceipt,
  updateExpense, uploadExpenseReceipts,
} from "../services/api/expenses";
import ReceiptCheck from "../components/ReceiptCheck";
import ExpenseEventPicker from "../components/ExpenseEventPicker";
import { expenseDates, expenseSubject } from "../utils/expenseAttribution";
import { hasPermission } from "../utils/permissionsRoleTemplate";

const PURPOSES = [
  { label: "Current client", value: "CLIENT_CURRENT" },
  { label: "Prospect client", value: "CLIENT_PROSPECT" },
  { label: "Conference", value: "CONFERENCE" },
  { label: "Investment", value: "INVESTMENT" },
  { label: "Other", value: "OTHER" },
];
const CATEGORIES = ["TRAVEL", "MEALS", "LODGING", "ENTERTAINMENT", "OTHER"];
const TRAVEL_TYPES = ["AIRFARE", "GROUND_TRANSPORT", "HOTEL", "MEALS", "OTHER"];

export const PURPOSE_LABELS = Object.fromEntries(PURPOSES.map((p) => [p.value, p.label]));
export { CATEGORIES, TRAVEL_TYPES };

// Where an expense is in its approvals, as words and a colour
export const expenseStatus = (e) => {
  if (e.manager_approval_status === "REJECTED" || e.payment_status === "REJECTED") {
    return { label: "Rejected", color: "bg-rose-100 text-rose-800" };
  }
  if (e.manager_approval_status === "PENDING" || !e.manager_approval_status) {
    return { label: "Pending Manager Approval", color: "bg-amber-100 text-amber-800" };
  }
  if (e.payment_status === "PENDING") return { label: "Finance Review", color: "bg-blue-100 text-blue-800" };
  if (e.payment_status === "APPROVED") return { label: "Approved", color: "bg-emerald-100 text-emerald-800" };
  if (e.payment_status === "REIMBURSED") return { label: "Reimbursed", color: "bg-emerald-100 text-emerald-800" };
  return { label: e.payment_status, color: "bg-gray-100 text-gray-700" };
};

// A visit's lines, in one word (backend expense_visit_service.visit_status)
const VISIT_STATUS = {
  NEEDS_DETAILS: { label: "Describe receipts", color: "bg-amber-100 text-amber-800" },
  SOME_REJECTED: { label: "Some rejected", color: "bg-rose-100 text-rose-800" },
  PENDING_MANAGER: { label: "Pending Manager Approval", color: "bg-amber-100 text-amber-800" },
  FINANCE_REVIEW: { label: "Finance Review", color: "bg-blue-100 text-blue-800" },
  APPROVED: { label: "Approved", color: "bg-emerald-100 text-emerald-800" },
  REIMBURSED: { label: "Reimbursed", color: "bg-emerald-100 text-emerald-800" },
  EMPTY: { label: "No lines yet", color: "bg-gray-100 text-gray-700" },
};
export const visitStatus = (status) => VISIT_STATUS[status] || { label: status, color: "bg-gray-100 text-gray-700" };

const statusOfLines = (lines) => {
  const words = lines.map((l) => expenseStatus(l).label);
  if (words.includes("Rejected")) return "SOME_REJECTED";
  if (words.every((w) => w === "Reimbursed")) return "REIMBURSED";
  if (words.includes("Pending Manager Approval")) return "PENDING_MANAGER";
  if (words.every((w) => w === "Approved" || w === "Reimbursed")) return "APPROVED";
  return "FINANCE_REVIEW";
};

export const formatUsdCents = (cents) =>
  cents == null ? "—" : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Who the spend is on (CEO 2026-10-31) -- the P&L puts it on that client (or each client's
// share of a split), its BU and its contracting company; internal spend stays with your BU
// -- every expense says it; personal/internal is a choice, never a default
const SPEND_FOR_LABELS = { INTERNAL: "Personal / internal (no client)", CLIENT: "One client", SPLIT: "Several clients" };
const spendForChoices = (purpose) => {
  if (purpose === "CLIENT_CURRENT" || purpose === "CLIENT_PROSPECT") return ["CLIENT", "SPLIT"];
  if (purpose === "INVESTMENT") return ["INTERNAL"];
  return ["INTERNAL", "CLIENT", "SPLIT"];
};
const defaultSpendFor = (purpose) => {
  if (purpose === "CLIENT_CURRENT" || purpose === "CLIENT_PROSPECT") return "CLIENT"; // still needs the client
  if (purpose === "INVESTMENT") return "INTERNAL"; // the only answer
  return ""; // the person must say
};
const emptySplitLine = () => ({ clientId: "", value: "" });

const emptyForm = {
  purpose: "CLIENT_CURRENT",
  spendFor: "CLIENT",
  clientId: "",
  splitBy: "percent",
  splits: [emptySplitLine(), emptySplitLine()],
  event: null,
  investmentLabel: "",
  expenseCategory: "TRAVEL",
  travelType: "AIRFARE",
  tripLabel: "",
  amount: "",
  expenseDate: "",
  expenseEndDate: "",
  location: "",
  description: "",
  receiptRef: "",
  receiptFiles: [],
};

// The form as it was filled in, to correct a logged expense
const formOf = (e) => ({
  ...emptyForm,
  purpose: e.purpose,
  spendFor: e.spend_for || defaultSpendFor(e.purpose),
  clientId: e.spend_for === "CLIENT" ? e.client_id || "" : "",
  splitBy: "amount",
  splits: e.spend_for === "SPLIT" && (e.client_shares || []).length
    ? e.client_shares.map((s) => ({ clientId: s.client_id, value: (s.amount_usd_cents / 100).toFixed(2) }))
    : [emptySplitLine(), emptySplitLine()],
  event: e.event_id ? { id: e.event_id, name: e.conference_name } : null,
  investmentLabel: e.investment_label || "",
  expenseCategory: e.expense_category,
  travelType: e.travel_type || "AIRFARE",
  tripLabel: e.trip_label || "",
  amount: (e.amount_usd_cents / 100).toFixed(2),
  expenseDate: e.expense_date,
  expenseEndDate: e.expense_end_date || "",
  location: e.location || "",
  description: e.description || "",
  receiptRef: e.receipt_ref || "",
});

export function LogExpenseForm({ clients, onCancel, onSaved, reloadClients, expense, onVisitCreated, employees }) {
  const [form, setForm] = useState(() => (expense ? formOf(expense) : emptyForm));
  // Accounts only (expenses:create on the role template): who the new expense is for; "" = yourself
  const [expenseFor, setExpenseFor] = useState("");
  // The record once it exists: if a receipt then fails to upload, saving again doesn't log it twice
  const [record, setRecord] = useState(expense || null);
  const [progress, setProgress] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [addingProspect, setAddingProspect] = useState(false);
  const [newProspectWebsite, setNewProspectWebsite] = useState("");

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));
  const setPurpose = (purpose) =>
    setForm((f) => ({ ...f, purpose, spendFor: defaultSpendFor(purpose), clientId: "", event: null }));
  const setSplit = (index, field) => (value) =>
    setForm((f) => ({ ...f, splits: f.splits.map((s, i) => (i === index ? { ...s, [field]: value } : s)) }));

  const amountCentsOf = (text) => Math.round(parseFloat(text || "0") * 100);
  const splitTotal = form.splits.reduce((sum, s) => sum + (parseFloat(s.value) || 0), 0);
  const splitTarget = form.splitBy === "percent" ? 100 : parseFloat(form.amount || "0");
  const splitBalanced = Math.abs(splitTotal - splitTarget) < 0.005;

  const clientSplitsPayload = () =>
    form.splits.map((s) =>
      form.splitBy === "percent"
        ? { client_id: s.clientId, percent: parseFloat(s.value) }
        : { client_id: s.clientId, amount_usd_cents: amountCentsOf(s.value) }
    );

  const handleAddProspect = async () => {
    if (!newProspectWebsite.trim()) {
      setError("Website is required to create a prospect client.");
      return;
    }
    try {
      const created = await createClient({
        company_name: newProspectWebsite.trim(),
        website: newProspectWebsite.trim(),
        line_type: "SPECIALITY",
        billing_currency: "USD",
      });
      await reloadClients();
      setForm((f) => {
        if (f.spendFor !== "SPLIT") return { ...f, clientId: created.id };
        const empty = f.splits.findIndex((s) => !s.clientId);
        const splits = empty >= 0
          ? f.splits.map((s, i) => (i === empty ? { ...s, clientId: created.id } : s))
          : [...f.splits, { clientId: created.id, value: "" }];
        return { ...f, splits };
      });
      setAddingProspect(false);
      setNewProspectWebsite("");
      setError("");
    } catch (err) {
      setError(err.message || "Failed to add prospect client.");
    }
  };

  // Several receipts for a new expense make a visit: each receipt becomes its own line, described next (CEO 2026-11-14)
  const visitMode = !expense && !record && form.receiptFiles.length > 1;

  const handleSave = async () => {
    const amountCents = Math.round(parseFloat(form.amount || "0") * 100);
    if (!visitMode && (!amountCents || amountCents <= 0)) {
      setError("Amount must be a positive number.");
      return;
    }
    if (!form.expenseDate) {
      setError("Expense date is required.");
      return;
    }
    if (form.expenseEndDate && form.expenseEndDate < form.expenseDate) {
      setError("The last date can't be before the first date.");
      return;
    }
    if (!form.receiptFiles.length && !(record?.receipts || []).length) {
      setError("Attach at least one receipt (photo or PDF).");
      return;
    }
    if (form.purpose === "CONFERENCE" && !form.event) {
      setError("Pick the conference (or add it if your team hasn't yet).");
      return;
    }
    if (!form.spendFor) {
      setError("Say who this expense is for: personal/internal, one client, or several clients.");
      return;
    }
    if (form.spendFor === "CLIENT" && !form.clientId) {
      setError("Pick the client this spend is on.");
      return;
    }
    if (form.spendFor === "SPLIT") {
      const chosen = form.splits.map((s) => s.clientId);
      if (chosen.some((c) => !c) || new Set(chosen).size !== chosen.length) {
        setError("Pick a different client on every split line.");
        return;
      }
      if (!splitBalanced) {
        setError(form.splitBy === "percent" ? "The split must total 100%." : "The split must total the amount.");
        return;
      }
    }
    if (form.purpose === "INVESTMENT" && !form.investmentLabel.trim()) {
      setError("Investment label is required.");
      return;
    }
    if (visitMode) {
      if (expenseFor) {
        setError("A visit is logged by the person themself. For an employee, upload one receipt per expense (Finance > Upload receipts).");
        return;
      }
      await saveVisit();
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = {
        purpose: form.purpose,
        spend_for: form.spendFor,
        client_id: form.spendFor === "CLIENT" ? form.clientId : null,
        client_splits: form.spendFor === "SPLIT" ? clientSplitsPayload() : null,
        event_id: form.purpose === "CONFERENCE" ? form.event.id : null,
        investment_label: form.purpose === "INVESTMENT" ? form.investmentLabel : null,
        expense_category: form.expenseCategory,
        travel_type: form.expenseCategory === "TRAVEL" ? form.travelType : null,
        trip_label: form.tripLabel || null,
        amount_usd_cents: amountCents,
        expense_date: form.expenseDate,
        expense_end_date: form.expenseEndDate || null,
        location: form.location || null,
        description: form.description || null,
        receipt_ref: form.receiptRef || form.receiptFiles[0]?.name || record?.receipt_ref,
        ...(record ? {} : { expense_for_employee_id: expenseFor || null }),
      };
      const saved = record ? await updateExpense(record.id, payload) : await createExpense(payload);
      setRecord(saved);
      // Receipts are read and checked on upload: a match approves the manager step by itself
      if (form.receiptFiles.length) {
        await uploadExpenseReceipts(saved.id, form.receiptFiles, (done, total) => setProgress(`Uploading receipt ${done} of ${total}…`));
      }
      onSaved();
    } catch (err) {
      setError(record || err.message ? err.message || "Failed to save the expense." : "Failed to save the expense.");
    } finally {
      setProgress("");
      setSaving(false);
    }
  };

  const saveVisit = async () => {
    if (form.spendFor === "SPLIT" && form.splitBy !== "percent") {
      setError("A visit splits its clients by %, so every receipt splits the same way.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const visit = await createExpenseVisit({
        name: form.tripLabel.trim() || form.description.trim() || `Visit ${form.expenseDate}`,
        purpose: form.purpose,
        spend_for: form.spendFor,
        client_id: form.spendFor === "CLIENT" ? form.clientId : null,
        client_splits: form.spendFor === "SPLIT" ? clientSplitsPayload() : null,
        event_id: form.purpose === "CONFERENCE" ? form.event.id : null,
        investment_label: form.purpose === "INVESTMENT" ? form.investmentLabel : null,
        location: form.location || null,
        start_date: form.expenseDate,
        end_date: form.expenseEndDate || null,
      });
      await addExpenseVisitReceipts(visit.id, form.receiptFiles, (done, total) => setProgress(`Uploading receipt ${done} of ${total}…`));
      onVisitCreated(visit.id);
    } catch (err) {
      setError(err.message || "Couldn't save the visit.");
    } finally {
      setProgress("");
      setSaving(false);
    }
  };

  const removeReceipt = async (receiptId) => {
    setError("");
    try {
      setRecord(await removeExpenseReceipt(record.id, receiptId));
    } catch (err) {
      setError(err.message || "Couldn't remove the receipt.");
    }
  };

  const choices = spendForChoices(form.purpose);
  const clientOptions = [
    { label: "Select client", value: "", disabled: true },
    ...clients.map((c) => ({ label: `${c.company_name}${c.status === "PROSPECT" ? " (prospect)" : ""}`, value: c.id })),
  ];
  const prospectAdder = addingProspect ? (
    <div className="mt-1 flex gap-1">
      <input
        className="w-full rounded-lg border px-2 py-1 text-xs"
        placeholder="Website (e.g. acme.com)"
        value={newProspectWebsite}
        onChange={(e) => setNewProspectWebsite(e.target.value)}
      />
      <Button variant="secondary" onClick={handleAddProspect}>Add</Button>
    </div>
  ) : (
    <button type="button" className="mt-1 text-xs font-semibold text-bx-orange" onClick={() => setAddingProspect(true)}>
      + New prospect client
    </button>
  );

  return (
    <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">{expense ? "Correct this expense" : "Log an expense"}</div>
      {expense && expense.manager_approval_status !== "PENDING" ? (
        <div className="mb-3 text-xs text-amber-700">Changing what it costs, its dates or who it is on sends it back to your manager.</div>
      ) : null}
      {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {employees && !expense ? (
          <Select
            label="Expense for"
            value={expenseFor}
            onChange={setExpenseFor}
            options={[
              { label: "Myself", value: "" },
              ...employees.map((e) => ({ label: e.email ? `${e.name} (${e.email})` : e.name, value: e.id })),
            ]}
          />
        ) : null}
        <Select label="Purpose" value={form.purpose} onChange={setPurpose} options={PURPOSES} />

        {form.purpose === "CONFERENCE" ? (
          <div className="sm:col-span-2">
            <ExpenseEventPicker value={form.event} onChange={set("event")} />
          </div>
        ) : null}
        {form.purpose === "INVESTMENT" ? (
          <Input label="Investment Label" value={form.investmentLabel} onChange={set("investmentLabel")} placeholder="New market entry" />
        ) : null}
      </div>

      {choices.length ? (
        <div className="mt-3 rounded-xl border border-gray-200 bg-white p-3">
          <div className="mb-2 text-xs font-semibold text-gray-700">Who is this expense for? *</div>
          <div className="flex flex-wrap gap-2">
            {choices.map((choice) => (
              <button
                key={choice}
                type="button"
                onClick={() => set("spendFor")(choice)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                  form.spendFor === choice ? "border-bx-orange bg-bx-orange text-white" : "border-gray-300 text-gray-700"
                }`}
              >
                {SPEND_FOR_LABELS[choice]}
              </button>
            ))}
          </div>
          {form.spendFor === "INTERNAL" ? (
            <div className="mt-2 text-xs text-gray-500">Counts as your business unit's own BD cost -- no client carries it.</div>
          ) : null}
          {form.spendFor === "CLIENT" ? (
            <div className="mt-2 max-w-md">
              <Select label="Client" value={form.clientId} onChange={set("clientId")} options={clientOptions} />
              {prospectAdder}
            </div>
          ) : null}
          {form.spendFor === "SPLIT" ? (
            <div className="mt-2 space-y-2">
              <div className="flex gap-3 text-xs">
                {[["percent", "Split by %"], ["amount", "Split by amount"]].map(([mode, label]) => (
                  <label key={mode} className="flex items-center gap-1">
                    <input type="radio" checked={form.splitBy === mode} onChange={() => set("splitBy")(mode)} /> {label}
                  </label>
                ))}
              </div>
              {form.splits.map((line, i) => (
                <div key={i} className="grid grid-cols-[1fr_8rem_auto] items-end gap-2">
                  <Select label={i === 0 ? "Client" : undefined} value={line.clientId} onChange={setSplit(i, "clientId")} options={clientOptions} />
                  <Input
                    label={i === 0 ? (form.splitBy === "percent" ? "Share %" : "Amount (USD)") : undefined}
                    value={line.value}
                    onChange={setSplit(i, "value")}
                    placeholder={form.splitBy === "percent" ? "50" : "225.00"}
                  />
                  <button
                    type="button"
                    className="pb-2 text-xs text-gray-500 disabled:opacity-30"
                    disabled={form.splits.length <= 2}
                    onClick={() => setForm((f) => ({ ...f, splits: f.splits.filter((_, j) => j !== i) }))}
                  >
                    Remove
                  </button>
                </div>
              ))}
              <div className="flex items-center gap-3 text-xs">
                <button
                  type="button"
                  className="font-semibold text-bx-orange"
                  onClick={() => setForm((f) => ({ ...f, splits: [...f.splits, emptySplitLine()] }))}
                >
                  + Add client
                </button>
                <span className={splitBalanced ? "text-emerald-700" : "text-rose-700"}>
                  {form.splitBy === "percent"
                    ? `Total ${splitTotal.toFixed(2)}% of 100%`
                    : `Total $${splitTotal.toFixed(2)} of $${(parseFloat(form.amount) || 0).toFixed(2)}`}
                </span>
              </div>
              {prospectAdder}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Select label="Category" value={form.expenseCategory} onChange={set("expenseCategory")} options={CATEGORIES} />
        {form.expenseCategory === "TRAVEL" ? (
          <Select label="Travel Type" value={form.travelType} onChange={set("travelType")} options={TRAVEL_TYPES} />
        ) : null}
        <Input
          label={visitMode ? "Visit or trip name" : "Trip Label (optional)"}
          value={form.tripLabel}
          onChange={set("tripLabel")}
          placeholder="Seattle - Goldenbear - Aug 2026"
        />
        {visitMode ? null : <Input label="Amount (USD)" value={form.amount} onChange={set("amount")} placeholder="450.00" />}
        <Input label="Date (first day)" type="date" value={form.expenseDate} onChange={set("expenseDate")} />
        <Input label="Last day (if it covers several)" type="date" value={form.expenseEndDate} onChange={set("expenseEndDate")} />
        <Input label="Location" value={form.location} onChange={set("location")} />
        <div className="block">
          <label htmlFor="expense-receipts" className="mb-1 block text-xs font-semibold text-gray-700">
            {(record?.receipts || []).length ? "Add more receipts" : "Receipts * (photos or PDFs)"}
          </label>
          <input
            id="expense-receipts"
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(e) => setForm((f) => ({ ...f, receiptFiles: Array.from(e.target.files || []) }))}
            className="block w-full text-sm"
          />
          <div className="mt-1 text-xs text-gray-500">
            {visitMode
              ? `${form.receiptFiles.length} receipts: each becomes its own line of this visit. Next you say what each was for; the amount and date are filled in from the receipt.`
              : "Select several receipts from one visit or event and each becomes its own line, grouped under the visit."}
          </div>
          {(record?.receipts || []).map((r, i) => (
            <div key={r.id} className="mt-1 flex items-center gap-2 text-xs">
              <button type="button" className="text-blue-600 hover:underline" onClick={() => openExpenseReceipt(record.id, r.id).catch((err) => setError(err.message))}>
                Receipt {i + 1}: {r.file_name || "file"}
              </button>
              {record.receipts.length > 1 ? (
                <button type="button" className="text-rose-700 hover:underline" onClick={() => removeReceipt(r.id)}>Remove</button>
              ) : null}
            </div>
          ))}
        </div>
        <Input label="Receipt Ref (optional)" value={form.receiptRef} onChange={set("receiptRef")} placeholder="Invoice ID or email ref" />
      </div>
      <div className="mt-3">
        <TextArea label="Description" value={form.description} onChange={set("description")} rows={2} />
      </div>
      <div className="mt-3 flex gap-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? progress || "Saving…" : expense ? "Save changes" : visitMode ? "Next: describe each receipt" : "Log Expense"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export default function MyExpensesScreen() {
  const navigate = useNavigate();
  const [expenses, setExpenses] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  // null = only your own expenses; a list = you may also log for these employees (expenses:create)
  const canLogForOthers = hasPermission("expenses", "create");
  const [employees, setEmployees] = useState(null);

  useEffect(() => {
    if (!canLogForOthers) return;
    listExpenseEmployees()
      .then(setEmployees)
      .catch((err) => setLoadError(`Couldn't load the employees you can log for: ${err.message}`));
  }, [canLogForOthers]);

  // the client list is the caller's own tenant and business units (server-scoped)
  const loadClients = useCallback(async () => {
    const data = await listClients();
    setClients(data?.clients || []);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [expenseData] = await Promise.all([listMyExpenses(), loadClients()]);
      setExpenses(expenseData?.expenses || []);
      setLoadError("");
    } catch (err) {
      console.error("[MyExpenses] Failed to load expenses or clients:", err);
      setLoadError(`Couldn't load your expenses: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [loadClients]);

  useEffect(() => {
    load();
  }, [load]);

  // A visit is one row that opens to its lines (CEO 2026-11-14); an expense on its own is its own row
  const visitRows = Object.values(expenses.filter((e) => e.visit_id).reduce((groups, e) => {
    (groups[e.visit_id] = groups[e.visit_id] || []).push(e);
    return groups;
  }, {})).map((lines) => {
    const first = lines[0];
    const days = lines.flatMap((l) => [l.expense_date, l.expense_end_date].filter(Boolean)).sort();
    const status = visitStatus(statusOfLines(lines));
    const rejected = lines.filter((l) => l.manager_review_note && expenseStatus(l).label === "Rejected").length;
    return {
      id: `visit-${first.visit_id}`,
      sortDate: days[days.length - 1],
      date: days[0] === days[days.length - 1] ? days[0] : `${days[0]} to ${days[days.length - 1]}`,
      purpose: first.purpose.replace("_", " "),
      subject: (
        <button type="button" className="text-left font-semibold text-blue-600 hover:underline"
          onClick={() => navigate(`/my-expenses/visits/${first.visit_id}`)}>
          {first.visit_name || "Visit"}
          <div className="text-xs font-normal text-gray-500">{expenseSubject(first)}</div>
        </button>
      ),
      category: `${lines.length} line${lines.length === 1 ? "" : "s"}`,
      amount: formatUsdCents(lines.reduce((sum, l) => sum + l.amount_usd_cents, 0)),
      status: <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${status.color}`}>{status.label}</span>,
      receipt: rejected ? <div className="text-xs text-rose-700">{rejected} rejected by your manager: open the visit</div> : null,
      actions: <Button variant="ghost" onClick={() => navigate(`/my-expenses/visits/${first.visit_id}`)}>Open</Button>,
    };
  });

  const singleRows = expenses.filter((e) => !e.visit_id).map((e) => {
    // Workflow: Employee logs → (waiting for manager approval) → Finance review → Marked paid
    const { label: statusDisplay, color: statusColor } = expenseStatus(e);

    return {
      id: e.id,
      sortDate: e.expense_end_date || e.expense_date,
      date: expenseDates(e),
      purpose: e.purpose.replace("_", " "),
      subject: expenseSubject(e),
      category: `${e.expense_category}${e.travel_type ? ` / ${e.travel_type}` : ""}`,
      amount: formatUsdCents(e.amount_usd_cents),
      status: (
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusColor}`}>
          {statusDisplay}
        </span>
      ),
      receipt: (
        <div>
          <ReceiptCheck expense={e} />
          {e.manager_review_note ? <div className="mt-1 text-xs text-rose-700">Manager: {e.manager_review_note}</div> : null}
        </div>
      ),
      // until Finance approves it (the server holds the same rule)
      actions: e.payment_status === "PENDING" ? (
        <Button variant="ghost" onClick={() => { setShowForm(false); setEditing(e); window.scrollTo({ top: 0 }); }}>Edit</Button>
      ) : null,
    };
  });
  const rows = [...visitRows, ...singleRows].sort((a, b) => (b.sortDate || "").localeCompare(a.sortDate || ""));

  return (
    <div className="space-y-4 p-6">
      <Card
        title="My Expenses"
        subtitle="Log your own travel and BD spend -- tagged to a client, prospect, conference, or investment."
        icon={<Receipt className="h-4 w-4" />}
        right={
          <Button onClick={() => { setEditing(null); setShowForm((v) => !v); }}>
            <Plus className="h-4 w-4" /> Log Expense
          </Button>
        }
      >
        {showForm || editing ? (
          <LogExpenseForm
            key={editing?.id || "new"}
            expense={editing}
            clients={clients}
            employees={canLogForOthers ? employees || [] : null}
            reloadClients={loadClients}
            onCancel={() => { setShowForm(false); setEditing(null); }}
            onSaved={() => {
              setShowForm(false);
              setEditing(null);
              load();
            }}
            onVisitCreated={(visitId) => navigate(`/my-expenses/visits/${visitId}`)}
          />
        ) : null}

        {loadError ? <div className="mb-3 text-xs text-rose-700">{loadError}</div> : null}
        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : (
          <Table
            columns={[
              { key: "date", header: "Date" },
              { key: "purpose", header: "Purpose" },
              { key: "subject", header: "Subject" },
              { key: "category", header: "Category" },
              { key: "amount", header: "Amount" },
              { key: "status", header: "Status" },
              { key: "receipt", header: "Receipt" },
              { key: "actions", header: "" },
            ]}
            rows={rows}
          />
        )}
      </Card>
    </div>
  );
}
