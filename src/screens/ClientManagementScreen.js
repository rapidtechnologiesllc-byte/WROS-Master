// Client Management -- add/edit client details. Flagged as a real gap
// 2026-08-05 (Avinash: "we need to be able to add and edit client
// details not seeing it in UI") -- no client CRUD UI existed anywhere
// before this. BU attribution is never editable here (locked to the
// creating user's own BU server-side, see POST /clients).
//
// 2026-08-06 redesign, confirmed directly with Avinash while testing
// live: Line Type (Core/Specialty) replaces Client Type on create;
// Industry dropped; Country is a dropdown; Website is a required dedup
// key; every client needs Hiring Manager + Timesheet Approver contacts
// captured at creation.
import { useEffect, useState } from "react";
import { Building2, Plus, Pencil } from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { listClients, createClient, updateClient } from "../services/api/clients";

const LINE_TYPES = ["CORE", "SPECIALITY"];
const CLIENT_TIERS = ["PLATINUM", "GOLD", "SILVER", "STANDARD"];
const BILLING_CURRENCIES = ["USD", "INR", "GBP", "EUR", "CAD", "AUD"];
const COUNTRIES = [
  "United States", "India", "United Kingdom", "Canada", "Australia",
  "Germany", "France", "Ireland", "Singapore", "United Arab Emirates",
  "Netherlands", "Mexico", "Philippines", "Other",
];

const emptyForm = {
  company_name: "",
  company_short_name: "",
  country: "",
  line_type: "CORE",
  website: "",
  tier: "STANDARD",
  billing_currency: "USD",
  notes: "",
  hiring_manager_name: "",
  hiring_manager_email: "",
  timesheet_approver_name: "",
  timesheet_approver_email: "",
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
    if (mode === "create") {
      if (!form.website?.trim()) {
        setError("Website is required (used to detect duplicate clients).");
        return;
      }
      if (!form.hiring_manager_name?.trim() || !form.hiring_manager_email?.trim()) {
        setError("Hiring Manager contact (name + email) is required.");
        return;
      }
      if (!form.timesheet_approver_name?.trim() || !form.timesheet_approver_email?.trim()) {
        setError("Timesheet Approver contact (name + email) is required.");
        return;
      }
    }
    setSaving(true);
    setError("");
    try {
      if (mode === "edit") {
        const { company_name, company_short_name, country, line_type, website, tier, billing_currency, notes } = form;
        await updateClient(form.id, {
          company_name, company_short_name, country, line_type, website, tier, billing_currency, notes,
        });
      } else {
        await createClient({
          company_name: form.company_name,
          line_type: form.line_type,
          country: form.country || null,
          website: form.website,
          billing_currency: form.billing_currency,
          hiring_manager: {
            name: form.hiring_manager_name,
            email: form.hiring_manager_email,
          },
          timesheet_approver: {
            name: form.timesheet_approver_name,
            email: form.timesheet_approver_email,
          },
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
        <Input label="Website *" value={form.website || ""} onChange={set("website")} placeholder="e.g. builders.com" />
        <Select label="Country" value={form.country} onChange={set("country")} options={COUNTRIES} />
        <Select label="Line Type *" value={form.line_type} onChange={set("line_type")} options={LINE_TYPES} />
        <Select label="Tier" value={form.tier} onChange={set("tier")} options={CLIENT_TIERS} />
        <Select label="Billing Currency" value={form.billing_currency} onChange={set("billing_currency")} options={BILLING_CURRENCIES} />
      </div>

      {mode === "create" ? (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2 text-xs font-semibold text-gray-700">Client Contacts</div>
          <Input label="Hiring Manager Name *" value={form.hiring_manager_name || ""} onChange={set("hiring_manager_name")} />
          <Input label="Hiring Manager Email *" value={form.hiring_manager_email || ""} onChange={set("hiring_manager_email")} />
          <Input label="Timesheet Approver Name *" value={form.timesheet_approver_name || ""} onChange={set("timesheet_approver_name")} />
          <Input label="Timesheet Approver Email *" value={form.timesheet_approver_email || ""} onChange={set("timesheet_approver_email")} />
        </div>
      ) : null}

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
