// Self-service expense logging, 2026-08-05. Avinash: "the expense is
// logged by employee so they need to login to their portal and add
// their expense." Every submission here is attributed to whoever is
// logged in -- there is no field to log an expense as someone else.
import { useEffect, useState } from "react";
import { Receipt, Plus } from "lucide-react";
import { Card, Button, Input, Select, TextArea, Table } from "../components/ui";
import { listClients, createClient } from "../services/api/clients";
import { createExpense, listMyExpenses } from "../services/api/expenses";

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

const emptyForm = {
  purpose: "CLIENT_CURRENT",
  clientId: "",
  conferenceName: "",
  investmentLabel: "",
  expenseCategory: "TRAVEL",
  travelType: "AIRFARE",
  tripLabel: "",
  amount: "",
  expenseDate: "",
  location: "",
  description: "",
  receiptRef: "",
};

function LogExpenseForm({ clients, onCancel, onSaved, reloadClients }) {
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [addingProspect, setAddingProspect] = useState(false);
  const [newProspectName, setNewProspectName] = useState("");

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const handleAddProspect = async () => {
    if (!newProspectName.trim()) return;
    try {
      const created = await createClient({
        company_name: newProspectName.trim(),
        line_type: "SPECIALITY",
        billing_currency: "USD",
      });
      await reloadClients();
      setForm((f) => ({ ...f, clientId: created.id }));
      setAddingProspect(false);
      setNewProspectName("");
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
    if ((form.purpose === "CLIENT_CURRENT" || form.purpose === "CLIENT_PROSPECT") && !form.clientId) {
      setError("Client is required for this purpose.");
      return;
    }
    if (form.purpose === "CONFERENCE" && !form.conferenceName.trim()) {
      setError("Conference name is required.");
      return;
    }
    if (form.purpose === "INVESTMENT" && !form.investmentLabel.trim()) {
      setError("Investment label is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createExpense({
        purpose: form.purpose,
        client_id: form.purpose === "CLIENT_CURRENT" || form.purpose === "CLIENT_PROSPECT" ? form.clientId : null,
        conference_name: form.purpose === "CONFERENCE" ? form.conferenceName : null,
        investment_label: form.purpose === "INVESTMENT" ? form.investmentLabel : null,
        expense_category: form.expenseCategory,
        travel_type: form.expenseCategory === "TRAVEL" ? form.travelType : null,
        trip_label: form.tripLabel || null,
        amount_usd_cents: amountCents,
        expense_date: form.expenseDate,
        location: form.location || null,
        description: form.description || null,
        receipt_ref: form.receiptRef || null,
      });
      onSaved();
    } catch (err) {
      setError(err.message || "Failed to log expense.");
    } finally {
      setSaving(false);
    }
  };

  const needsClient = form.purpose === "CLIENT_CURRENT" || form.purpose === "CLIENT_PROSPECT";

  return (
    <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">Log an expense</div>
      {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Select label="Purpose" value={form.purpose} onChange={set("purpose")} options={PURPOSES} />

        {needsClient ? (
          <div>
            <Select
              label="Client"
              value={form.clientId}
              onChange={set("clientId")}
              options={[
                { label: "Select client", value: "", disabled: true },
                ...clients.map((c) => ({ label: c.company_name, value: c.id })),
              ]}
            />
            {form.purpose === "CLIENT_PROSPECT" ? (
              addingProspect ? (
                <div className="mt-1 flex gap-1">
                  <input
                    className="w-full rounded-lg border px-2 py-1 text-xs"
                    placeholder="New prospect name"
                    value={newProspectName}
                    onChange={(e) => setNewProspectName(e.target.value)}
                  />
                  <Button variant="secondary" onClick={handleAddProspect}>Add</Button>
                </div>
              ) : (
                <button
                  type="button"
                  className="mt-1 text-xs font-semibold text-bx-orange"
                  onClick={() => setAddingProspect(true)}
                >
                  + New prospect client
                </button>
              )
            ) : null}
          </div>
        ) : null}

        {form.purpose === "CONFERENCE" ? (
          <Input label="Conference Name" value={form.conferenceName} onChange={set("conferenceName")} placeholder="NAMIC 2026" />
        ) : null}
        {form.purpose === "INVESTMENT" ? (
          <Input label="Investment Label" value={form.investmentLabel} onChange={set("investmentLabel")} placeholder="New market entry" />
        ) : null}

        <Select label="Category" value={form.expenseCategory} onChange={set("expenseCategory")} options={CATEGORIES} />
        {form.expenseCategory === "TRAVEL" ? (
          <Select label="Travel Type" value={form.travelType} onChange={set("travelType")} options={TRAVEL_TYPES} />
        ) : null}
        <Input label="Trip Label (optional)" value={form.tripLabel} onChange={set("tripLabel")} placeholder="Seattle - Goldenbear - Aug 2026" />
        <Input label="Amount (USD)" value={form.amount} onChange={set("amount")} placeholder="450.00" />
        <Input label="Expense Date" type="date" value={form.expenseDate} onChange={set("expenseDate")} />
        <Input label="Location" value={form.location} onChange={set("location")} />
        <Input label="Receipt Ref" value={form.receiptRef} onChange={set("receiptRef")} />
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
  const [showForm, setShowForm] = useState(false);

  const loadClients = async () => {
    try {
      const data = await listClients();
      setClients(data?.clients || []);
    } catch (err) {
      console.error("Failed to load clients:", err);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const [expenseData] = await Promise.all([listMyExpenses(), loadClients()]);
      setExpenses(expenseData?.expenses || []);
    } catch (err) {
      console.error("Failed to load expenses:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const rows = expenses.map((e) => ({
    date: e.expense_date,
    purpose: e.purpose.replace("_", " "),
    subject: e.conference_name || e.investment_label || (e.client_id ? "Client" : "—"),
    category: `${e.expense_category}${e.travel_type ? ` / ${e.travel_type}` : ""}`,
    amount: formatUsdCents(e.amount_usd_cents),
    status: (
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-700">
        {e.payment_status}
      </span>
    ),
  }));

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
            ]}
            rows={rows}
          />
        )}
      </Card>
    </div>
  );
}
