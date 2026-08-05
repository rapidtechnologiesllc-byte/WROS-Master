// Client Management -- add/edit client details. Flagged as a real gap
// 2026-08-05 (Avinash: "we need to be able to add and edit client
// details not seeing it in UI") -- no client CRUD UI existed anywhere
// before this. BU attribution is never editable here (locked to the
// creating user's own BU server-side, see POST /clients).
import { useEffect, useState } from "react";
import { Building2, Plus, Pencil } from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { listClients, createClient, updateClient } from "../services/api/clients";

const CLIENT_TYPES = ["DIRECT", "MSP", "VMS"];
const CLIENT_TIERS = ["PLATINUM", "GOLD", "SILVER", "STANDARD"];
const BILLING_CURRENCIES = ["USD", "INR", "GBP", "EUR", "CAD", "AUD"];

const emptyForm = {
  company_name: "",
  company_short_name: "",
  industry: "",
  country: "",
  client_type: "DIRECT",
  tier: "STANDARD",
  billing_currency: "USD",
  notes: "",
};

function ClientForm({ mode, initial, onCancel, onSaved }) {
  const [form, setForm] = useState(initial || emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const handleSave = async () => {
    if (!form.company_name?.trim()) {
      setError("Company name is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (mode === "edit") {
        const { company_name, company_short_name, industry, country, client_type, tier, billing_currency, notes } = form;
        await updateClient(form.id, {
          company_name, company_short_name, industry, country, client_type, tier, billing_currency, notes,
        });
      } else {
        await createClient({
          company_name: form.company_name,
          client_type: form.client_type,
          industry: form.industry || null,
          country: form.country || null,
          billing_currency: form.billing_currency,
        });
      }
      onSaved();
    } catch (err) {
      setError(err.message || "Failed to save client.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">
        {mode === "edit" ? "Edit client" : "Add client"}
      </div>
      {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Input label="Company Name *" value={form.company_name} onChange={set("company_name")} />
        <Input label="Short Name" value={form.company_short_name || ""} onChange={set("company_short_name")} />
        <Input label="Industry" value={form.industry || ""} onChange={set("industry")} />
        <Input label="Country" value={form.country || ""} onChange={set("country")} />
        <Select label="Client Type" value={form.client_type} onChange={set("client_type")} options={CLIENT_TYPES} />
        <Select label="Tier" value={form.tier} onChange={set("tier")} options={CLIENT_TIERS} />
        <Select label="Billing Currency" value={form.billing_currency} onChange={set("billing_currency")} options={BILLING_CURRENCIES} />
      </div>
      <div className="mt-3 flex gap-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export default function ClientManagementScreen() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [editingClient, setEditingClient] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await listClients({ activeOnly: false });
      setClients(data?.clients || []);
    } catch (err) {
      console.error("Failed to load clients:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSaved = () => {
    setShowAdd(false);
    setEditingClient(null);
    load();
  };

  const rows = clients.map((c) => ({
    company_name: c.company_name,
    status: (
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-700">
        {c.status}
      </span>
    ),
    actions: (
      <Button
        variant="ghost"
        onClick={() => {
          setShowAdd(false);
          setEditingClient({ id: c.id, ...emptyForm, company_name: c.company_name });
        }}
      >
        <Pencil className="h-4 w-4" /> Edit
      </Button>
    ),
  }));

  return (
    <div className="space-y-4 p-6">
      <Card
        title="Client Management"
        subtitle="Add and edit client accounts. Business Unit ownership is locked to whoever sources the client and is not editable here."
        icon={<Building2 className="h-4 w-4" />}
        right={
          <Button
            onClick={() => {
              setEditingClient(null);
              setShowAdd((v) => !v);
            }}
          >
            <Plus className="h-4 w-4" /> Add Client
          </Button>
        }
      >
        {showAdd ? (
          <ClientForm mode="create" onCancel={() => setShowAdd(false)} onSaved={handleSaved} />
        ) : null}
        {editingClient ? (
          <ClientForm
            mode="edit"
            initial={editingClient}
            onCancel={() => setEditingClient(null)}
            onSaved={handleSaved}
          />
        ) : null}

        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading clients…</div>
        ) : (
          <Table
            columns={[
              { key: "company_name", header: "Company" },
              { key: "status", header: "Status" },
              { key: "actions", header: "" },
            ]}
            rows={rows}
          />
        )}
      </Card>
    </div>
  );
}
