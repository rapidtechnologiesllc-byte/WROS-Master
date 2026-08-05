// S-237/HRMS-0208 Opportunity Pipeline (Kanban) + S-236 create form.
// Doc calls for drag-and-drop; this app has no drag-and-drop library
// anywhere else, so stage moves happen via a per-card "Move to" select
// instead -- same end result (opportunities.stage updates, logged via
// the transition endpoint) without a new UI dependency.
import { useEffect, useState } from "react";
import { TrendingUp, Plus } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import { listClients } from "../services/api/clients";
import {
  getPipeline,
  createOpportunity,
  transitionOpportunityStage,
} from "../services/api/opportunities";

const STAGES = ["QUALIFICATION", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function CreateOpportunityForm({ clients, onCancel, onCreated }) {
  const [clientId, setClientId] = useState("");
  const [revenueValue, setRevenueValue] = useState("");
  const [probability, setProbability] = useState("50");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!clientId) {
      setError("Client is required.");
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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Select
          label="Client"
          value={clientId}
          onChange={setClientId}
          options={[
            { label: "Select client", value: "", disabled: true },
            ...clients.map((c) => ({ label: c.company_name, value: c.id })),
          ]}
        />
        <Input label="Revenue Value (USD)" value={revenueValue} onChange={setRevenueValue} placeholder="500000" />
        <Input label="Win Probability (%)" value={probability} onChange={setProbability} placeholder="50" />
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

function OpportunityCard({ opportunity, onMoved }) {
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
    <div className="mb-2 rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
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

export default function OpportunityPipelineScreen() {
  const [columns, setColumns] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

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

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-4 p-6">
      <Card
        title="Opportunity Pipeline"
        subtitle="Revenue Visibility Engine -- pipeline value, win probability, and weighted forecast per stage."
        icon={<TrendingUp className="h-4 w-4" />}
        right={
          <Button onClick={() => setShowCreate((v) => !v)}>
            <Plus className="h-4 w-4" /> New Opportunity
          </Button>
        }
      >
        {showCreate ? (
          <CreateOpportunityForm
            clients={clients}
            onCancel={() => setShowCreate(false)}
            onCreated={() => {
              setShowCreate(false);
              load();
            }}
          />
        ) : null}

        {loading ? (
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
                    <OpportunityCard key={o.id} opportunity={o} onMoved={load} />
                  ))
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
