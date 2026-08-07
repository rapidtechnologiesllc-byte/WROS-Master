// S-237/HRMS-0208 Opportunity Pipeline (Kanban) + S-236 create form.
// Doc calls for drag-and-drop; this app has no drag-and-drop library
// anywhere else, so stage moves happen via a per-card "Move to" select
// instead -- same end result (opportunities.stage updates, logged via
// the transition endpoint) without a new UI dependency.
//
// 2026-08-06: wired 3 previously-orphaned wrappers (working backend +
// api/ function, never imported by any screen):
//  - listOpportunities (GET /opportunities) as a flat, filterable List
//    view alongside the Kanban -- the Kanban (getPipeline) already
//    shows every opportunity grouped by stage, so this isn't a new
//    dataset, it's a sortable/filterable table cut of the same data
//    (filter by stage or by client), which the board can't do.
//  - getOpportunityRevenueRollup (GET /opportunities/:id/revenue-rollup)
//    on a new click-through detail panel (no detail view existed at
//    all before -- Kanban cards and list rows were dead ends).
//  - createRoleDemandFromOpportunity (POST /opportunities/:id/role-demand)
//    as a "Create Role Demand" form inside that same detail panel,
//    shown once the opportunity is WON.
import { useEffect, useMemo, useState } from "react";
import { TrendingUp, Plus, LayoutGrid, List as ListIcon, X } from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { listClients, createClient } from "../services/api/clients";
import { getAllUsers } from "../services/api/users";
import {
  getPipeline,
  listOpportunities,
  createOpportunity,
  transitionOpportunityStage,
  getOpportunityRevenueRollup,
  createRoleDemandFromOpportunity,
} from "../services/api/opportunities";

// Shared with backend PIPELINE_STATUSES - single source of truth
// Must match app/models/opportunity.py and app/models/client.py
const STAGES = ["QUALIFICATION", "PROSPECT", "PROPOSAL", "NEGOTIATION", "CONTRACT", "ACTIVE", "LOST"];

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function CreateOpportunityForm({ clients, onCancel, onCreated, reloadClients }) {
  const [clientId, setClientId] = useState("");
  const [dealName, setDealName] = useState("");
  const [revenueValue, setRevenueValue] = useState("");
  const [probability, setProbability] = useState("50");
  const [ownerId, setOwnerId] = useState(""); // Opportunity owner
  const [expectedCloseDate, setExpectedCloseDate] = useState("");
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [addingClient, setAddingClient] = useState(false);
  const [newClientWebsite, setNewClientWebsite] = useState("");

  useEffect(() => {
    const loadUsers = async () => {
      try {
        setLoadingUsers(true);
        const userList = await getAllUsers();
        setUsers(userList || []);
      } catch (err) {
        console.error("Failed to load users:", err);
      } finally {
        setLoadingUsers(false);
      }
    };
    loadUsers();
  }, []);

  const handleAddClient = async () => {
    if (!newClientWebsite.trim()) {
      setError("Website is required to create a prospect client.");
      return;
    }
    try {
      const created = await createClient({
        company_name: newClientWebsite.trim(),
        website: newClientWebsite.trim(),
        line_type: "SPECIALITY",
        billing_currency: "USD",
      });
      await reloadClients();
      setClientId(created.id);
      setAddingClient(false);
      setNewClientWebsite("");
      setError("");
    } catch (err) {
      setError(err.message || "Failed to add prospect client.");
    }
  };

  const handleSave = async () => {
    if (!clientId) {
      setError("Client is required.");
      return;
    }
    if (!ownerId) {
      setError("Owner is required.");
      return;
    }
    const usdCents = Math.round(parseFloat(revenueValue || "0") * 100);
    if (!usdCents || usdCents <= 0) {
      setError("Revenue value must be a positive number.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createOpportunity({
        client_id: clientId,
        revenue_value_usd_cents: usdCents,
        probability_pct: Number(probability),
        owner_employee_id: ownerId,
        expected_close_date: expectedCloseDate || null,
        stage: "QUALIFICATION",
      });
      onCreated();
    } catch (err) {
      setError(err.message || "Failed to create opportunity.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">New opportunity</div>
      {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <div>
          <Select
            label="Client"
            value={clientId}
            onChange={setClientId}
            options={[
              { label: "Select client", value: "", disabled: true },
              ...clients.map((c) => ({ label: c.company_name, value: c.id })),
            ]}
          />
          {addingClient ? (
            <div className="mt-1 flex gap-1">
              <input
                className="w-full rounded-lg border px-2 py-1 text-xs"
                placeholder="Website (e.g. acme.com)"
                value={newClientWebsite}
                onChange={(e) => setNewClientWebsite(e.target.value)}
              />
              <Button variant="secondary" onClick={handleAddClient}>Add</Button>
            </div>
          ) : (
            <button
              type="button"
              className="mt-1 text-xs font-semibold text-bx-orange"
              onClick={() => setAddingClient(true)}
            >
              + New prospect
            </button>
          )}
        </div>
        <Select
          label="Owner"
          value={ownerId}
          onChange={setOwnerId}
          options={[
            { label: "Select owner", value: "", disabled: true },
            ...users.map((u) => ({ label: `${u.first_name} ${u.last_name}`, value: u.id })),
          ]}
          disabled={loadingUsers}
        />
        <Input label="Revenue Value (USD)" value={revenueValue} onChange={setRevenueValue} placeholder="500000" />
        <Input label="Win Probability (%)" value={probability} onChange={setProbability} placeholder="50" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 mt-3">
        <Input
          label="Expected Close Date"
          type="date"
          value={expectedCloseDate}
          onChange={setExpectedCloseDate}
        />
      </div>
      <div className="mt-3 flex gap-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Create"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function OpportunityCard({ opportunity, onMoved, onOpenDetail }) {
  const [moving, setMoving] = useState(false);

  const handleMove = async (newStage) => {
    if (!newStage || newStage === opportunity.stage) return;
    setMoving(true);
    try {
      await transitionOpportunityStage(opportunity.id, { new_stage: newStage });
      onMoved();
    } catch (err) {
      alert(err.message || "Could not move opportunity.");
    } finally {
      setMoving(false);
    }
  };

  const closed = opportunity.stage === "WON" || opportunity.stage === "LOST";

  return (
    <div
      className="mb-2 cursor-pointer rounded-xl border border-gray-200 bg-white p-3 shadow-sm transition hover:border-gray-400"
      onClick={() => onOpenDetail(opportunity)}
    >
      <div className="text-sm font-semibold text-gray-900">{opportunity.client_name}</div>
      <div className="mt-1 text-xs text-gray-600">
        {formatUsdCents(opportunity.revenue_value_usd_cents)} · {opportunity.probability_pct}% ·{" "}
        {formatUsdCents(opportunity.weighted_forecast_usd_cents)} weighted
      </div>
      {opportunity.owner_name ? (
        <div className="mt-1 text-xs text-gray-500">Owner: {opportunity.owner_name}</div>
      ) : null}
      {opportunity.expected_close_date ? (
        <div className="mt-1 text-xs text-gray-500">Close: {opportunity.expected_close_date}</div>
      ) : null}
      {!closed ? (
        <select
          className="mt-2 w-full rounded-lg border bg-white px-2 py-1 text-xs"
          value=""
          disabled={moving}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => handleMove(e.target.value)}
        >
          <option value="" disabled>
            Move to…
          </option>
          {STAGES.filter((s) => s !== opportunity.stage).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      ) : null}
    </div>
  );
}

// Click-through detail panel for a single opportunity -- previously no
// such view existed anywhere (Kanban cards and list rows were dead
// ends). Surfaces the revenue rollup (GET .../revenue-rollup) and, once
// WON, a form to spin up the role demand (POST .../role-demand).
function OpportunityDetailPanel({ opportunity, onClose, onRoleDemandCreated }) {
  const [rollup, setRollup] = useState(null);
  const [rollupLoading, setRollupLoading] = useState(true);
  const [rollupError, setRollupError] = useState("");

  const [form, setForm] = useState({
    job_title: "",
    required_skills: "",
    min_experience_years: "",
    work_location: "",
    quantity: "1",
    duration_hours: "",
    billing_rate_usd_cents: "",
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [created, setCreated] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setRollupLoading(true);
    setRollupError("");
    getOpportunityRevenueRollup(opportunity.id)
      .then((data) => {
        if (!cancelled) setRollup(data);
      })
      .catch((err) => {
        if (!cancelled) setRollupError(err.message || "Failed to load revenue rollup.");
      })
      .finally(() => {
        if (!cancelled) setRollupLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [opportunity.id]);

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  // S-240: Real-time revenue potential calculation (billing_rate * duration_hours * quantity)
  const revenuePotentialUsdCents = useMemo(() => {
    const rate = Math.round(parseFloat(form.billing_rate_usd_cents || "0") * 100);
    const duration = parseInt(form.duration_hours || "0", 10);
    const qty = parseInt(form.quantity || "1", 10);
    if (!rate || !duration || !qty) return null;
    return rate * duration * qty;
  }, [form.billing_rate_usd_cents, form.duration_hours, form.quantity]);

  const handleCreateRoleDemand = async () => {
    setFormError("");
    if (!form.job_title.trim() || !form.required_skills.trim() || !form.work_location.trim()) {
      setFormError("Job title, required skills, and work location are required.");
      return;
    }
    const minExperienceYears = parseFloat(form.min_experience_years || "0");
    const quantity = parseInt(form.quantity || "0", 10);
    const durationHours = parseInt(form.duration_hours || "0", 10);
    const billingRateUsdCents = Math.round(parseFloat(form.billing_rate_usd_cents || "0") * 100);
    if (!quantity || quantity <= 0) {
      setFormError("Quantity must be a positive number.");
      return;
    }
    if (!billingRateUsdCents || billingRateUsdCents <= 0) {
      setFormError("Billing rate must be a positive number.");
      return;
    }
    setSaving(true);
    try {
      const demand = await createRoleDemandFromOpportunity(opportunity.id, {
        job_title: form.job_title,
        required_skills: form.required_skills,
        min_experience_years: minExperienceYears,
        work_location: form.work_location,
        quantity,
        duration_hours: durationHours,
        billing_rate_usd_cents: billingRateUsdCents,
      });
      setCreated(demand);
      onRoleDemandCreated?.();
      // Roll-up now includes this new demand's revenue -- refresh it.
      getOpportunityRevenueRollup(opportunity.id).then(setRollup).catch(() => {});
    } catch (err) {
      setFormError(err.message || "Failed to create role demand.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="text-sm font-semibold text-gray-900">{opportunity.client_name}</div>
          <button className="text-gray-400 hover:text-gray-700" onClick={onClose}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-1 rounded-xl border bg-gray-50 p-3 text-xs text-gray-700">
          <div>
            Stage: <span className="font-semibold text-gray-900">{opportunity.stage}</span>
          </div>
          <div>
            Revenue Value: <span className="font-semibold">{formatUsdCents(opportunity.revenue_value_usd_cents)}</span>
          </div>
          <div>
            Win Probability: <span className="font-semibold">{opportunity.probability_pct}%</span>
          </div>
          <div>
            Weighted Forecast: <span className="font-semibold">{formatUsdCents(opportunity.weighted_forecast_usd_cents)}</span>
          </div>
          {opportunity.owner_name ? <div>Owner: <span className="font-semibold">{opportunity.owner_name}</span></div> : null}
          {opportunity.expected_close_date ? (
            <div>Expected Close: <span className="font-semibold">{opportunity.expected_close_date}</span></div>
          ) : null}
        </div>

        <div className="mt-4">
          <div className="mb-1 text-xs font-semibold uppercase text-gray-500">Revenue Rollup</div>
          {rollupLoading ? (
            <div className="text-xs text-gray-500">Loading…</div>
          ) : rollupError ? (
            <div className="text-xs text-rose-700">{rollupError}</div>
          ) : (
            <div className="rounded-xl border bg-white p-3 text-xs text-gray-700">
              Role Demand Revenue:{" "}
              <span className="font-semibold text-gray-900">
                {formatUsdCents(rollup?.role_demand_revenue_usd_cents)}
              </span>
              <div className="mt-1 text-[11px] text-gray-500">
                Sum of billing revenue across role demand created from this opportunity.
              </div>
            </div>
          )}
        </div>

        {opportunity.stage === "WON" ? (
          <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-3">
            <div className="mb-2 text-xs font-semibold uppercase text-gray-500">Create Role Demand</div>
            {formError ? <div className="mb-2 text-xs text-rose-700">{formError}</div> : null}
            {created ? (
              <div className="mb-2 rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-800">
                Created "{created.job_title}" — status {created.status}, headcount {created.headcount}
                {created.revenue_potential_usd_cents != null
                  ? `, revenue potential ${formatUsdCents(created.revenue_potential_usd_cents)}`
                  : ""}
                .
              </div>
            ) : null}
            <div className="space-y-2">
              <Input label="Job Title" value={form.job_title} onChange={set("job_title")} placeholder="Senior Guidewire Developer" />
              <Input
                label="Required Skills"
                value={form.required_skills}
                onChange={set("required_skills")}
                placeholder="Guidewire PolicyCenter, Java"
              />
              <div className="grid grid-cols-2 gap-2">
                <Input label="Min Experience (yrs)" value={form.min_experience_years} onChange={set("min_experience_years")} placeholder="5" />
                <Input label="Quantity" value={form.quantity} onChange={set("quantity")} placeholder="1" />
              </div>
              <Input label="Work Location" value={form.work_location} onChange={set("work_location")} placeholder="Remote / Hyderabad" />
              <div className="grid grid-cols-2 gap-2">
                <Input label="Duration (hours)" value={form.duration_hours} onChange={set("duration_hours")} placeholder="2080" />
                <Input label="Billing Rate (USD/hr)" value={form.billing_rate_usd_cents} onChange={set("billing_rate_usd_cents")} placeholder="85" />
              </div>
            </div>
            {revenuePotentialUsdCents != null ? (
              <div className="mt-2 rounded-lg bg-blue-50 border border-blue-200 p-2">
                <div className="text-xs text-blue-700">
                  <span className="font-semibold">Revenue Potential:</span> {formatUsdCents(revenuePotentialUsdCents)}
                </div>
              </div>
            ) : null}
            <Button className="mt-3" onClick={handleCreateRoleDemand} disabled={saving}>
              {saving ? "Creating…" : "Create Role Demand"}
            </Button>
          </div>
        ) : (
          <div className="mt-4 text-xs text-gray-500">
            Role demand can be created once this opportunity is moved to WON.
          </div>
        )}
      </div>
    </div>
  );
}

export default function OpportunityPipelineScreen() {
  const [viewMode, setViewMode] = useState("kanban");
  const [columns, setColumns] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);

  // Flat/filterable list view -- GET /opportunities (listOpportunities),
  // a genuinely different cut from the Kanban's GET /opportunities/pipeline:
  // filter by stage or client instead of seeing everything grouped.
  const [listStage, setListStage] = useState("");
  const [listClientId, setListClientId] = useState("");
  const [listRows, setListRows] = useState([]);
  const [listLoading, setListLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [pipeline, clientList] = await Promise.all([
        getPipeline(),
        listClients(),
      ]);
      setColumns(pipeline?.columns || []);
      setClients(clientList?.clients || []);
    } catch (err) {
      console.error("Failed to load pipeline:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadList = async () => {
    setListLoading(true);
    try {
      const data = await listOpportunities({
        stage: listStage || undefined,
        clientId: listClientId || undefined,
      });
      setListRows(data?.opportunities || []);
    } catch (err) {
      console.error("Failed to load opportunity list:", err);
    } finally {
      setListLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (viewMode === "list") {
      loadList();
    }
  }, [viewMode, listStage, listClientId]);

  const refreshAll = () => {
    load();
    if (viewMode === "list") loadList();
  };

  const listTableRows = listRows.map((o) => ({
    client_name: o.client_name || "—",
    stage: o.stage,
    revenue: formatUsdCents(o.revenue_value_usd_cents),
    probability: `${o.probability_pct}%`,
    weighted: formatUsdCents(o.weighted_forecast_usd_cents),
    owner: o.owner_name || "—",
    close_date: o.expected_close_date || "—",
    actions: (
      <Button variant="ghost" onClick={() => setSelectedOpportunity(o)}>
        View
      </Button>
    ),
  }));

  return (
    <div className="space-y-4 p-6">
      <Card
        title="Opportunity Pipeline"
        subtitle="Revenue Visibility Engine -- pipeline value, win probability, and weighted forecast per stage."
        icon={<TrendingUp className="h-4 w-4" />}
        right={
          <div className="flex items-center gap-2">
            <div className="flex overflow-hidden rounded-xl border">
              <button
                className={`flex items-center gap-1 px-3 py-1.5 text-xs font-semibold ${
                  viewMode === "kanban" ? "bg-gray-900 text-white" : "bg-white text-gray-600"
                }`}
                onClick={() => setViewMode("kanban")}
              >
                <LayoutGrid className="h-3.5 w-3.5" /> Kanban
              </button>
              <button
                className={`flex items-center gap-1 px-3 py-1.5 text-xs font-semibold ${
                  viewMode === "list" ? "bg-gray-900 text-white" : "bg-white text-gray-600"
                }`}
                onClick={() => setViewMode("list")}
              >
                <ListIcon className="h-3.5 w-3.5" /> List
              </button>
            </div>
            <Button onClick={() => setShowCreate((v) => !v)}>
              <Plus className="h-4 w-4" /> New Opportunity
            </Button>
          </div>
        }
      >
        {showCreate ? (
          <CreateOpportunityForm
            clients={clients}
            onCancel={() => setShowCreate(false)}
            onCreated={() => {
              setShowCreate(false);
              refreshAll();
            }}
            reloadClients={load}
          />
        ) : null}

        {viewMode === "kanban" ? (
          loading ? (
            <div className="py-8 text-center text-sm text-gray-500">Loading pipeline…</div>
          ) : (
            <div className="grid grid-cols-1 gap-3 overflow-x-auto sm:grid-cols-5">
              {columns.map((col) => (
                <div key={col.stage} className="min-w-[220px] rounded-2xl border bg-gray-50 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="text-xs font-bold uppercase text-gray-700">{col.stage}</div>
                    <div className="text-xs font-semibold text-gray-900">
                      {formatUsdCents(col.total_revenue_usd_cents)}
                    </div>
                  </div>
                  <div className="mb-2 text-[11px] text-gray-500">
                    Weighted: {formatUsdCents(col.total_weighted_forecast_usd_cents)}
                  </div>
                  {col.opportunities.length === 0 ? (
                    <div className="py-4 text-center text-xs text-gray-400">No opportunities</div>
                  ) : (
                    col.opportunities.map((o) => (
                      <OpportunityCard
                        key={o.id}
                        opportunity={o}
                        onMoved={refreshAll}
                        onOpenDetail={setSelectedOpportunity}
                      />
                    ))
                  )}
                </div>
              ))}
            </div>
          )
        ) : (
          <div>
            <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Select
                label="Filter by Stage"
                value={listStage}
                onChange={setListStage}
                options={[{ label: "All stages", value: "" }, ...STAGES.map((s) => ({ label: s, value: s }))]}
              />
              <Select
                label="Filter by Client"
                value={listClientId}
                onChange={setListClientId}
                options={[
                  { label: "All clients", value: "" },
                  ...clients.map((c) => ({ label: c.company_name, value: c.id })),
                ]}
              />
            </div>
            {listLoading ? (
              <div className="py-8 text-center text-sm text-gray-500">Loading opportunities…</div>
            ) : listTableRows.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-500">No opportunities match this filter.</div>
            ) : (
              <Table
                columns={[
                  { key: "client_name", header: "Client" },
                  { key: "stage", header: "Stage" },
                  { key: "revenue", header: "Revenue" },
                  { key: "probability", header: "Win %" },
                  { key: "weighted", header: "Weighted" },
                  { key: "owner", header: "Owner" },
                  { key: "close_date", header: "Expected Close" },
                  { key: "actions", header: "" },
                ]}
                rows={listTableRows}
              />
            )}
          </div>
        )}
      </Card>

      {selectedOpportunity ? (
        <OpportunityDetailPanel
          opportunity={selectedOpportunity}
          onClose={() => setSelectedOpportunity(null)}
          onRoleDemandCreated={refreshAll}
        />
      ) : null}
    </div>
  );
}
