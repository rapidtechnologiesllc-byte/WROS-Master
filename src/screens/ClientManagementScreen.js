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
import { Building2, Plus, Pencil, TrendingUp, X } from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { listClients, createClient, updateClient, getClient } from "../services/api/clients";
import { getClientInvestmentPosition } from "../services/api/expenses";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

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
  const [editLoadingId, setEditLoadingId] = useState(null);
  const [detailClient, setDetailClient] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [investmentPosition, setInvestmentPosition] = useState(null);
  const [investmentPositionError, setInvestmentPositionError] = useState("");

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
        notes: full.notes || "",
      });
    } catch (err) {
      console.error("Failed to load client details:", err);
      setEditingClient({ id: c.id, ...emptyForm, company_name: c.company_name });
    } finally {
      setEditLoadingId(null);
    }
  };

  const handleRowClick = async (c) => {
    setDetailError("");
    setInvestmentPosition(null);
    setInvestmentPositionError("");
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
  };

  const handleCloseDetail = () => {
    setDetailClient(null);
    setInvestmentPosition(null);
    setInvestmentPositionError("");
    setDetailError("");
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

      {detailClient ? (
        <ClientDetailModal
          client={detailClient}
          loading={detailLoading}
          error={detailError}
          investmentPosition={investmentPosition}
          investmentPositionError={investmentPositionError}
          onClose={handleCloseDetail}
        />
      ) : null}
    </div>
  );
}

function ClientDetailModal({ client, loading, error, investmentPosition, investmentPositionError, onClose }) {
  const fields = [
    { label: "Company Name", value: client.company_name },
    { label: "Short Name", value: client.company_short_name },
    { label: "Status", value: client.status },
    { label: "Line Type", value: client.line_type },
    { label: "Tier", value: client.tier },
    { label: "Country", value: client.country },
    { label: "Website", value: client.website },
    { label: "Billing Currency", value: client.billing_currency },
    { label: "Payment Terms (days)", value: client.payment_terms_days },
    { label: "Billing Address", value: client.billing_address },
    { label: "Contract Start", value: client.contract_start_date },
    { label: "Contract End", value: client.contract_end_date },
    { label: "NDA Signed", value: client.nda_signed === undefined ? undefined : client.nda_signed ? "Yes" : "No" },
    { label: "Notes", value: client.notes },
  ];

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-5 py-4">
          <div className="text-base font-semibold text-gray-900">{client.company_name}</div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-4">
          {loading ? (
            <div className="py-6 text-center text-sm text-gray-500">Loading client details…</div>
          ) : error ? (
            <div className="text-sm text-rose-700">{error}</div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {fields.map((f) => (
                <div key={f.label} className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">{f.label}</div>
                  <div className="mt-1 break-words text-sm font-medium text-gray-900">
                    {f.value === undefined || f.value === null || f.value === "" ? "-" : String(f.value)}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 border-t pt-4">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
              <TrendingUp className="h-3.5 w-3.5" />
              Investment Position
            </div>
            {investmentPositionError ? (
              <div className="text-sm text-rose-700">{investmentPositionError}</div>
            ) : !investmentPosition ? (
              <div className="text-sm text-gray-400">Loading…</div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">Total Expense</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">
                    {formatUsdCents(investmentPosition.total_expense_usd_cents)}
                  </div>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">Total Revenue</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">
                    {formatUsdCents(investmentPosition.total_revenue_usd_cents)}
                  </div>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">Net Position</div>
                  <div
                    className={`mt-1 text-sm font-semibold ${
                      investmentPosition.net_position_usd_cents < 0 ? "text-rose-700" : "text-green-700"
                    }`}
                  >
                    {formatUsdCents(investmentPosition.net_position_usd_cents)}
                  </div>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">Breakeven Date</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">
                    {investmentPosition.breakeven_date || "Not yet"}
                  </div>
                </div>
                <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">Expense Records</div>
                  <div className="mt-1 text-sm font-semibold text-gray-900">{investmentPosition.expense_count}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
