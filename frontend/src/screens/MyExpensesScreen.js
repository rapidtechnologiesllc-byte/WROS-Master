// Self-service expense logging, 2026-08-05. Avinash: "the expense is
// logged by employee so they need to login to their portal and add
// their expense." Every submission here is attributed to whoever is
// logged in -- there is no field to log an expense as someone else.
import { useCallback, useEffect, useState } from "react";
import { Receipt, Plus } from "lucide-react";
import { Card, Button, Input, Select, TextArea, Table } from "../components/ui";
import { listClients, createClient } from "../services/api/clients";
import { createExpense, listMyExpenses, uploadExpenseReceipt } from "../services/api/expenses";
import ReceiptCheck from "../components/ReceiptCheck";
import ExpenseEventPicker from "../components/ExpenseEventPicker";
import { expenseSubject } from "../utils/expenseAttribution";

const PURPOSES = [
  { label: "Current client", value: "CLIENT_CURRENT" },
  { label: "Prospect client", value: "CLIENT_PROSPECT" },
  { label: "Conference", value: "CONFERENCE" },
  { label: "Investment", value: "INVESTMENT" },
  { label: "Other", value: "OTHER" },
];
const CATEGORIES = ["TRAVEL", "MEALS", "LODGING", "ENTERTAINMENT", "OTHER"];
const TRAVEL_TYPES = ["AIRFARE", "GROUND_TRANSPORT", "HOTEL", "MEALS", "OTHER"];

const formatUsdCents = (cents) =>
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
  location: "",
  description: "",
  receiptRef: "",
  receiptFile: null,
};

function LogExpenseForm({ clients, onCancel, onSaved, reloadClients }) {
  const [form, setForm] = useState(emptyForm);
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

  const handleSave = async () => {
    const amountCents = Math.round(parseFloat(form.amount || "0") * 100);
    if (!amountCents || amountCents <= 0) {
      setError("Amount must be a positive number.");
      return;
    }
    if (!form.expenseDate) {
      setError("Expense date is required.");
      return;
    }
    if (!form.receiptFile) {
      setError("Attach the receipt (photo or PDF).");
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
    setSaving(true);
    setError("");
    try {
      const created = await createExpense({
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
        location: form.location || null,
        description: form.description || null,
        receipt_ref: form.receiptRef || form.receiptFile.name,
      });
      // The receipt is read and checked on upload: a match approves the manager step by itself
      await uploadExpenseReceipt(created.id, form.receiptFile);
      onSaved();
    } catch (err) {
      setError(err.message || "Failed to log expense.");
    } finally {
      setSaving(false);
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
      <div className="mb-3 text-sm font-semibold text-gray-900">Log an expense</div>
      {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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
        <Input label="Trip Label (optional)" value={form.tripLabel} onChange={set("tripLabel")} placeholder="Seattle - Goldenbear - Aug 2026" />
        <Input label="Amount (USD)" value={form.amount} onChange={set("amount")} placeholder="450.00" />
        <Input label="Expense Date" type="date" value={form.expenseDate} onChange={set("expenseDate")} />
        <Input label="Location" value={form.location} onChange={set("location")} />
        <label className="block">
          <div className="mb-1 text-xs font-semibold text-gray-700">Receipt * (photo or PDF)</div>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(e) => setForm((f) => ({ ...f, receiptFile: e.target.files?.[0] || null }))}
            className="block w-full text-sm"
          />
          <div className="mt-1 text-xs text-gray-500">Checked automatically against the amount and date.</div>
        </label>
        <Input label="Receipt Ref (optional)" value={form.receiptRef} onChange={set("receiptRef")} placeholder="Invoice ID or email ref" />
      </div>
      <div className="mt-3">
        <TextArea label="Description" value={form.description} onChange={set("description")} rows={2} />
      </div>
      <div className="mt-3 flex gap-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Log Expense"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export default function MyExpensesScreen() {
  const [expenses, setExpenses] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [showForm, setShowForm] = useState(false);

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

  const rows = expenses.map((e) => {
    // Workflow: Employee logs → (waiting for manager approval) → Finance review → Marked paid
    let statusDisplay = e.payment_status;
    let statusColor = "bg-gray-100 text-gray-700";

    if (e.manager_approval_status === "REJECTED") {
      statusDisplay = "Rejected";
      statusColor = "bg-rose-100 text-rose-800";
    } else if (e.manager_approval_status === "PENDING" || !e.manager_approval_status) {
      statusDisplay = "Pending Manager Approval";
      statusColor = "bg-amber-100 text-amber-800";
    } else if (e.manager_approval_status === "APPROVED" && e.payment_status === "PENDING") {
      statusDisplay = "Finance Review";
      statusColor = "bg-blue-100 text-blue-800";
    } else if (e.payment_status === "APPROVED") {
      statusDisplay = "Approved";
      statusColor = "bg-emerald-100 text-emerald-800";
    } else if (e.payment_status === "REIMBURSED") {
      statusDisplay = "Reimbursed";
      statusColor = "bg-emerald-100 text-emerald-800";
    } else if (e.payment_status === "REJECTED") {
      statusDisplay = "Rejected";
      statusColor = "bg-rose-100 text-rose-800";
    }

    return {
      date: e.expense_date,
      purpose: e.purpose.replace("_", " "),
      subject: expenseSubject(e),
      category: `${e.expense_category}${e.travel_type ? ` / ${e.travel_type}` : ""}`,
      amount: formatUsdCents(e.amount_usd_cents),
      status: (
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusColor}`}>
          {statusDisplay}
        </span>
      ),
      receipt: <ReceiptCheck expense={e} />,
    };
  });

  return (
    <div className="space-y-4 p-6">
      <Card
        title="My Expenses"
        subtitle="Log your own travel and BD spend -- tagged to a client, prospect, conference, or investment."
        icon={<Receipt className="h-4 w-4" />}
        right={
          <Button onClick={() => setShowForm((v) => !v)}>
            <Plus className="h-4 w-4" /> Log Expense
          </Button>
        }
      >
        {showForm ? (
          <LogExpenseForm
            clients={clients}
            reloadClients={loadClients}
            onCancel={() => setShowForm(false)}
            onSaved={() => {
              setShowForm(false);
              load();
            }}
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
            ]}
            rows={rows}
          />
        )}
      </Card>
    </div>
  );
}
