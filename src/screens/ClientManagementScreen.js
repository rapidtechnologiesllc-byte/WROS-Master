// Client Management -- add/edit client details. Flagged as a real gap
// 2026-08-05 (Avinash: "we need to be able to add and edit client
// details not seeing it in UI") -- no client CRUD UI existed anywhere
// before this. BU attribution is never editable here (locked to the
// creating user's own BU server-side, see POST /clients).
//
// 2026-08-06 redesign, confirmed directly with Avinash while testing
// live: Line Type (Core/Specialty) replaces Client Type on create;
// Industry dropped; Country is a dropdown; Website is a required dedup
// key.
//
// 2026-08-07: Hiring Manager / Timesheet Approver contacts moved OFF
// the create form per Avinash's live-testing feedback (real JobDiva
// client record shown as reference: contacts are their own tab, not a
// field that blocks creating the company). Contacts are now captured
// after creation, in the client detail view -- see ClientContactsPanel
// below. A client still can't go status=ACTIVE without at least one
// contact (enforced server-side, unchanged).
import { useEffect, useState } from "react";
import { Building2, Plus, Pencil, TrendingUp, Users, X } from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import {
  listClients, createClient, updateClient, getClient,
  getClientContacts, addClientContact,
} from "../services/api/clients";
import { getClientInvestmentPosition } from "../services/api/expenses";
import { getMyBUAccess } from "../services/api/buContext";

const CONTACT_ROLE_TYPES = [
  "HIRING_MANAGER", "TIMESHEET_APPROVER", "TECHNICAL_PANEL", "PROCUREMENT", "ACCOUNTS", "PRIMARY",
];

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const LINE_TYPES = ["CORE", "SPECIALITY"];
const CLIENT_TIERS = ["PLATINUM", "GOLD", "SILVER", "STANDARD"];
// Shared with Opportunity.stage - single source of truth
// Must match backend PIPELINE_STATUSES in app/models/opportunity.py and app/models/client.py
const PIPELINE_STATUSES = ["QUALIFICATION", "PROSPECT", "PROPOSAL", "NEGOTIATION", "CONTRACT", "ACTIVE", "LOST"];
const CLIENT_STATUSES = PIPELINE_STATUSES;  // Client.status uses same values as Opportunity.stage
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
  business_unit_id: "",
  notes: "",
};

function ClientForm({ mode, initial, onCancel, onSaved, businessUnits = [] }) {
  const [form, setForm] = useState(initial || emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (mode === "create" && !form.business_unit_id && businessUnits?.length) {
      const def = businessUnits.find((a) => a.is_default) || businessUnits[0];
      setForm((f) => ({ ...f, business_unit_id: String(def.business_unit_id) }));
    }
  }, [mode, businessUnits]);

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const handleSave = async () => {
    if (!form.company_name?.trim()) {
      setError("Company name is required.");
      return;
    }
    if (!form.business_unit_id) {
      setError("Business Unit is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (mode === "edit") {
        const { company_name, company_short_name, country, line_type, website, tier, billing_currency, business_unit_id, notes } = form;
        await updateClient(form.id, {
          company_name, company_short_name, country, line_type, website, tier, billing_currency, business_unit_id, notes,
        });
      } else {
        await createClient({
          company_name: form.company_name,
          line_type: form.line_type,
          country: form.country || null,
          website: form.website,
          billing_currency: form.billing_currency,
          business_unit_id: form.business_unit_id,
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
        <Input label="Website" value={form.website || ""} onChange={set("website")} placeholder="e.g. builders.com (optional)" />
        <Select label="Country" value={form.country} onChange={set("country")} options={COUNTRIES} />
        <Select label="Line Type *" value={form.line_type} onChange={set("line_type")} options={LINE_TYPES} />
        <Select label="Business Unit *" value={form.business_unit_id} onChange={set("business_unit_id")} options={[
          { label: "Select Business Unit", value: "", disabled: true },
          ...businessUnits.map(bu => ({ label: bu.name, value: String(bu.business_unit_id) }))
        ]} />
        <Select label="Tier" value={form.tier} onChange={set("tier")} options={CLIENT_TIERS} />
        <Select label="Billing Currency" value={form.billing_currency} onChange={set("billing_currency")} options={BILLING_CURRENCIES} />
        {mode === "edit" && (
          <Select label="Status" value={form.status || "PROSPECT"} onChange={set("status")} options={CLIENT_STATUSES} />
        )}
      </div>

      {mode === "create" ? (
        <div className="mt-3 text-xs text-gray-500">
          Contacts (Hiring Manager, Timesheet Approver, etc.) and website can be added/updated after creation.
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
  const [editLoadingId, setEditLoadingId] = useState(null);
  const [detailClient, setDetailClient] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [investmentPosition, setInvestmentPosition] = useState(null);
  const [investmentPositionError, setInvestmentPositionError] = useState("");
  const [contacts, setContacts] = useState([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [contactsError, setContactsError] = useState("");
  const [businessUnits, setBusinessUnits] = useState([]);

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
    // Fetch business units for dropdown
    getMyBUAccess()
      .then((res) => {
        setBusinessUnits(res.access || []);
      })
      .catch((err) => console.error("Failed to load business units:", err));
  }, []);

  const handleSaved = () => {
    setShowAdd(false);
    setEditingClient(null);
    load();
  };

  const handleEditClick = async (c) => {
    setShowAdd(false);
    setDetailClient(null);
    setEditLoadingId(c.id);
    try {
      // The list endpoint only returns company_name/status/BU/line_type --
      // fetching the real record here so Save doesn't blank out every
      // other field (website, tier, notes, etc.) back to form defaults.
      const full = await getClient(c.id);
      setEditingClient({
        id: full.id,
        company_name: full.company_name || "",
        company_short_name: full.company_short_name || "",
        country: full.country || "",
        line_type: full.line_type || "CORE",
        website: full.website || "",
        tier: full.tier || "STANDARD",
        billing_currency: full.billing_currency || "USD",
        business_unit_id: full.business_unit_id ? String(full.business_unit_id) : "",
        notes: full.notes || "",
      });
    } catch (err) {
      console.error("Failed to load client details:", err);
      setEditingClient({ id: c.id, ...emptyForm, company_name: c.company_name });
    } finally {
      setEditLoadingId(null);
    }
  };

  const loadContacts = async (clientId) => {
    setContactsLoading(true);
    setContactsError("");
    try {
      const data = await getClientContacts(clientId);
      setContacts(data?.contacts || []);
    } catch (err) {
      setContactsError(err.message || "Failed to load contacts.");
    } finally {
      setContactsLoading(false);
    }
  };

  const handleRowClick = async (c) => {
    setDetailError("");
    setInvestmentPosition(null);
    setInvestmentPositionError("");
    setContacts([]);
    setContactsError("");
    setDetailClient({ id: c.id, company_name: c.company_name });
    setDetailLoading(true);
    try {
      const full = await getClient(c.id);
      setDetailClient(full);
    } catch (err) {
      setDetailError(err.message || "Failed to load client details.");
    } finally {
      setDetailLoading(false);
    }
    try {
      const position = await getClientInvestmentPosition(c.id);
      setInvestmentPosition(position);
    } catch (err) {
      setInvestmentPositionError(err.message || "Failed to load investment position.");
    }
    loadContacts(c.id);
  };

  const handleCloseDetail = () => {
    setDetailClient(null);
    setInvestmentPosition(null);
    setInvestmentPositionError("");
    setDetailError("");
    setContacts([]);
    setContactsError("");
  };

  const rows = clients.map((c) => ({
    company_name: (
      <button
        type="button"
        onClick={() => handleRowClick(c)}
        className="text-left font-medium text-blue-700 hover:underline"
      >
        {c.company_name}
      </button>
    ),
    business_unit: c.business_unit_name || "—",
    status: (
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-700">
        {c.status}
      </span>
    ),
    actions: (
      <Button variant="ghost" onClick={() => handleEditClick(c)} disabled={editLoadingId === c.id}>
        <Pencil className="h-4 w-4" /> {editLoadingId === c.id ? "Loading…" : "Edit"}
      </Button>
    ),
  }));

  return (
    <div className="space-y-4 p-6">
      <Card
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
          <ClientForm mode="create" onCancel={() => setShowAdd(false)} onSaved={handleSaved} businessUnits={businessUnits} />
        ) : null}
        {editingClient ? (
          <ClientForm
            mode="edit"
            initial={editingClient}
            onCancel={() => setEditingClient(null)}
            onSaved={handleSaved}
            businessUnits={businessUnits}
          />
        ) : null}

        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading clients…</div>
        ) : (
          <Table
            columns={[
              { key: "company_name", header: "Company" },
              { key: "business_unit", header: "Business Unit" },
              { key: "status", header: "Status" },
              { key: "actions", header: "" },
            ]}
            rows={rows}
          />
        )}
      </Card>

      {detailClient ? (
        <ClientDetailModal
          client={detailClient}
          loading={detailLoading}
          error={detailError}
          investmentPosition={investmentPosition}
          investmentPositionError={investmentPositionError}
          contacts={contacts}
          contactsLoading={contactsLoading}
          contactsError={contactsError}
          onContactAdded={() => loadContacts(detailClient.id)}
          onClose={handleCloseDetail}
          businessUnits={businessUnits}
        />
      ) : null}
    </div>
  );
}

function ClientContactsPanel({ clientId, contacts, loading, error, onContactAdded }) {
  const emptyContact = { name: "", email: "", phone: "", role_type: "HIRING_MANAGER" };
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(emptyContact);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const handleAdd = async () => {
    if (!form.name.trim() || !form.email.trim()) {
      setSaveError("Name and email are required.");
      return;
    }
    setSaving(true);
    setSaveError("");
    try {
      await addClientContact(clientId, {
        name: form.name.trim(), email: form.email.trim(),
        phone: form.phone.trim() || null, role_type: form.role_type,
      });
      setForm(emptyContact);
      setShowAdd(false);
      onContactAdded();
    } catch (err) {
      setSaveError(err.message || "Failed to add contact.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-4 border-t pt-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
          <Users className="h-3.5 w-3.5" />
          Contacts
        </div>
        <Button variant="ghost" onClick={() => setShowAdd((v) => !v)}>
          <Plus className="h-4 w-4" /> Add Contact
        </Button>
      </div>

      {showAdd ? (
        <div className="mb-3 rounded-xl border border-gray-200 bg-gray-50 p-3">
          {saveError ? <div className="mb-2 text-xs text-rose-700">{saveError}</div> : null}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Input label="Name *" value={form.name} onChange={set("name")} />
            <Input label="Email *" value={form.email} onChange={set("email")} />
            <Input label="Phone" value={form.phone} onChange={set("phone")} />
            <Select label="Role" value={form.role_type} onChange={set("role_type")} options={CONTACT_ROLE_TYPES} />
          </div>
          <div className="mt-2 flex gap-2">
            <Button onClick={handleAdd} disabled={saving}>{saving ? "Saving…" : "Save Contact"}</Button>
            <Button variant="ghost" onClick={() => setShowAdd(false)} disabled={saving}>Cancel</Button>
          </div>
        </div>
      ) : null}

      {loading ? (
        <div className="text-sm text-gray-400">Loading contacts…</div>
      ) : error ? (
        <div className="text-sm text-rose-700">{error}</div>
      ) : contacts.length === 0 ? (
        <div className="text-sm text-gray-400">No contacts yet.</div>
      ) : (
        <div className="space-y-2">
          {contacts.map((c) => (
            <div key={c.id} className="rounded-xl border border-gray-100 bg-gray-50 p-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-gray-900">{c.name}</div>
                <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-semibold text-gray-700">
                  {c.role_type.replace(/_/g, " ")}
                </span>
              </div>
              <div className="mt-0.5 text-xs text-gray-500">
                {c.email}{c.phone ? ` · ${c.phone}` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ClientDetailModal({
  client, loading, error, investmentPosition, investmentPositionError,
  contacts, contactsLoading, contactsError, onContactAdded, onClose, businessUnits = [],
}) {
  const [selectedBU, setSelectedBU] = useState(String(client?.business_unit_id || ""));
  const [buSaving, setBuSaving] = useState(false);

  useEffect(() => {
    setSelectedBU(String(client?.business_unit_id || ""));
  }, [client?.id]);

  const handleBUChange = async (buId) => {
    setSelectedBU(buId);
    if (!buId || !client?.id) return;

    setBuSaving(true);
    try {
      await updateClient(client.id, { business_unit_id: Number(buId) });
    } catch (err) {
      console.error("Failed to update business unit:", err);
      setSelectedBU(String(client.business_unit_id || ""));
    } finally {
      setBuSaving(false);
    }
  };

  const statusColors = {
    "ACTIVE": "bg-emerald-50 text-emerald-700 border-emerald-200",
    "INACTIVE": "bg-gray-50 text-gray-700 border-gray-200",
    "PENDING": "bg-amber-50 text-amber-700 border-amber-200",
  };

  const getStatusBadge = (status) => {
    const colors = statusColors[status] || "bg-gray-50 text-gray-700 border-gray-200";
    return (
      <span className={`inline-flex rounded-full border px-3 py-1 text-sm font-semibold ${colors}`}>
        {status}
      </span>
    );
  };

  const FieldGroup = ({ label, children }) => (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</div>
      <div className="space-y-2">{children}</div>
    </div>
  );

  const FieldRow = ({ label, value }) => (
    <div className="flex justify-between gap-4 rounded-lg bg-gray-50 px-4 py-3 hover:bg-gray-100 transition">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">
        {value === undefined || value === null || value === "" ? "—" : String(value)}
      </span>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 border-b border-gray-200 bg-white px-8 py-6 rounded-t-3xl">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <Building2 className="h-6 w-6 text-blue-600" />
                <h2 className="text-2xl font-bold text-gray-900">{client.company_name}</h2>
              </div>
              <div className="mt-2">{getStatusBadge(client.status)}</div>
            </div>
            <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600 transition">
              <X className="h-6 w-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-8 py-6 space-y-8">
          {loading ? (
            <div className="py-12 text-center text-sm text-gray-500">Loading client details…</div>
          ) : error ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
          ) : (
            <>
              {/* Company Details */}
              <FieldGroup label="Company Details">
                <FieldRow label="Short Name" value={client.company_short_name} />
                <FieldRow label="Website" value={client.website} />
                <FieldRow label="Country" value={client.country} />
                <FieldRow label="Line Type" value={client.line_type} />
                <div>
                  <label className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Business Unit</label>
                  <Select
                    value={selectedBU}
                    onChange={handleBUChange}
                    options={[
                      { label: "Select Business Unit", value: "", disabled: true },
                      ...businessUnits.map((bu) => ({
                        label: bu.name,
                        value: String(bu.business_unit_id),
                      })),
                    ]}
                    disabled={buSaving}
                  />
                  {buSaving && <div className="mt-1 text-xs text-gray-500">Saving...</div>}
                </div>
              </FieldGroup>

              {/* Billing & Contract */}
              <FieldGroup label="Billing & Contract">
                <FieldRow label="Tier" value={client.tier} />
                <FieldRow label="Billing Currency" value={client.billing_currency} />
                <FieldRow label="Payment Terms (days)" value={client.payment_terms_days} />
                <FieldRow label="Billing Address" value={client.billing_address} />
                <FieldRow label="Contract Start" value={client.contract_start_date} />
                <FieldRow label="Contract End" value={client.contract_end_date} />
                <FieldRow label="NDA Signed" value={client.nda_signed === undefined ? undefined : client.nda_signed ? "Yes" : "No"} />
              </FieldGroup>

              {/* Notes */}
              {client.notes && (
                <FieldGroup label="Notes">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">{client.notes}</p>
                  </div>
                </FieldGroup>
              )}

              {/* Investment Position */}
              {!investmentPositionError && investmentPosition && (
                <FieldGroup label="Investment Position">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                    <div className="rounded-lg border border-gray-200 bg-gradient-to-br from-blue-50 to-blue-100/50 px-4 py-4 hover:from-blue-100">
                      <div className="text-xs font-semibold text-blue-600">Total Expense</div>
                      <div className="mt-2 text-lg font-bold text-gray-900">{formatUsdCents(investmentPosition.total_expense_usd_cents)}</div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gradient-to-br from-emerald-50 to-emerald-100/50 px-4 py-4 hover:from-emerald-100">
                      <div className="text-xs font-semibold text-emerald-600">Total Revenue</div>
                      <div className="mt-2 text-lg font-bold text-gray-900">{formatUsdCents(investmentPosition.total_revenue_usd_cents)}</div>
                    </div>
                    <div className={`rounded-lg border px-4 py-4 ${investmentPosition.net_position_usd_cents < 0 ? "border-rose-200 bg-gradient-to-br from-rose-50 to-rose-100/50 hover:from-rose-100" : "border-green-200 bg-gradient-to-br from-green-50 to-green-100/50 hover:from-green-100"}`}>
                      <div className={`text-xs font-semibold ${investmentPosition.net_position_usd_cents < 0 ? "text-rose-600" : "text-green-600"}`}>Net Position</div>
                      <div className={`mt-2 text-lg font-bold ${investmentPosition.net_position_usd_cents < 0 ? "text-rose-700" : "text-green-700"}`}>{formatUsdCents(investmentPosition.net_position_usd_cents)}</div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gradient-to-br from-purple-50 to-purple-100/50 px-4 py-4 hover:from-purple-100">
                      <div className="text-xs font-semibold text-purple-600">Breakeven Date</div>
                      <div className="mt-2 text-lg font-bold text-gray-900">{investmentPosition.breakeven_date || "—"}</div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gradient-to-br from-orange-50 to-orange-100/50 px-4 py-4 hover:from-orange-100">
                      <div className="text-xs font-semibold text-orange-600">Expense Records</div>
                      <div className="mt-2 text-lg font-bold text-gray-900">{investmentPosition.expense_count}</div>
                    </div>
                  </div>
                </FieldGroup>
              )}
              {investmentPositionError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{investmentPositionError}</div>
              )}

              {/* Contacts */}
              {!loading && !error ? (
                <div>
                  <div className="mb-4 flex items-center justify-between">
                    <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Contacts</div>
                  </div>
                  <ClientContactsPanel
                    clientId={client.id}
                    contacts={contacts}
                    loading={contactsLoading}
                    error={contactsError}
                    onContactAdded={onContactAdded}
                  />
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
