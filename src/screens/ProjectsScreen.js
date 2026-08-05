// HRMS-0801 (Project Lifecycle) + HRMS-0804 (Milestones) + HRMS-0805
// (Unfilled Roles) + HRMS-0806 (Revenue Estimate, "not a finance
// figure") + S-358/HRMS-0519 (SI Partner Engagement Tagging -- required
// whenever delivery_engine=SPECIALITY).
import { useEffect, useState } from "react";
import { FolderKanban, RefreshCw, Flag, Users, TrendingUp, CheckCircle2 } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import cx from "../utils/cx";
import {
  createProject,
  getProjects,
  transitionProjectStatus,
  createMilestone,
  getMilestones,
  completeMilestone,
  getUnfilledRoles,
  getExpectedRevenue,
} from "../services/api/projects";

const STATUS_STYLES = {
  PLANNING: "border-gray-200 bg-gray-50 text-gray-800",
  ACTIVE: "border-emerald-200 bg-emerald-50 text-emerald-800",
  ON_HOLD: "border-amber-200 bg-amber-50 text-amber-800",
  COMPLETED: "border-blue-200 bg-blue-50 text-blue-800",
  CLOSED: "border-gray-300 bg-gray-100 text-gray-600",
};

const STATUS_TRANSITIONS = {
  PLANNING: ["ACTIVE", "CLOSED"],
  ACTIVE: ["ON_HOLD", "COMPLETED", "CLOSED"],
  ON_HOLD: ["ACTIVE", "CLOSED"],
  COMPLETED: ["CLOSED"],
  CLOSED: [],
};

const SI_PARTNERS = ["PWC", "EY", "CASTLEBAY", "ZENSAR", "LTI_MINDTREE", "OTHER"];
// Backlog item, 2026-08-05: Avinash -- "If Speciality then always =
// Staff Augmentation so you don't need another field, but when it is
// core we need to break down the subtype of revenue." Only shown (and
// only required) when Delivery Engine = Core.
const BUSINESS_TYPES = ["T_AND_M", "MANAGED_SERVICES", "PROJECT", "POD", "PILOT"];
const SPECIALITY_CURRENCIES = ["INR", "USD"];
const CORE_CURRENCIES = ["USD"];

function CreateProjectForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [clientId, setClientId] = useState("");
  const [name, setName] = useState("");
  const [deliveryEngine, setDeliveryEngine] = useState("SPECIALITY");
  const [siPartner, setSiPartner] = useState("PWC");
  const [endClient, setEndClient] = useState("");
  const [clientPartner, setClientPartner] = useState("");
  const [businessType, setBusinessType] = useState(BUSINESS_TYPES[0]);
  const [currency, setCurrency] = useState("USD");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const currencyOptions = deliveryEngine === "SPECIALITY" ? SPECIALITY_CURRENCIES : CORE_CURRENCIES;

  const handleDeliveryEngineChange = (value) => {
    setDeliveryEngine(value);
    // Currency must stay valid for whichever engine is now selected.
    const validCurrencies = value === "SPECIALITY" ? SPECIALITY_CURRENCIES : CORE_CURRENCIES;
    if (!validCurrencies.includes(currency)) {
      setCurrency(validCurrencies[0]);
    }
  };

  const handleSubmit = async () => {
    if (!clientId.trim() || !name.trim()) {
      setError("Client ID and project name are both required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createProject({
        client_id: clientId.trim(),
        name: name.trim(),
        delivery_engine: deliveryEngine,
        currency,
        si_partner: deliveryEngine === "SPECIALITY" ? siPartner : null,
        end_client: deliveryEngine === "SPECIALITY" && endClient.trim() ? endClient.trim() : null,
        client_partner: deliveryEngine === "CORE" && clientPartner.trim() ? clientPartner.trim() : null,
        business_type: deliveryEngine === "CORE" ? businessType : null,
      });
      setClientId("");
      setName("");
      setEndClient("");
      setClientPartner("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err.message || "Failed to create project.");
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <Button variant="primary" onClick={() => setOpen(true)}>
        <FolderKanban className="h-4 w-4" /> New Project
      </Button>
    );
  }

  return (
    <div className="rounded-2xl border p-4">
      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Client ID" value={clientId} onChange={setClientId} placeholder="client UUID" />
        <Input label="Project Name" value={name} onChange={setName} placeholder="PolicyCenter Rollout" />
        <Select label="Delivery Engine" value={deliveryEngine} onChange={handleDeliveryEngineChange} options={["SPECIALITY", "CORE"]} />
        <Select label="Currency" value={currency} onChange={setCurrency} options={currencyOptions} />
        {deliveryEngine === "SPECIALITY" ? (
          <>
            <Select label="SI Partner (required for Speciality)" value={siPartner} onChange={setSiPartner} options={SI_PARTNERS} />
            <Input label="End Client (optional)" value={endClient} onChange={setEndClient} placeholder="Staff Augmentation end client" />
          </>
        ) : (
          <>
            <Select label="Business Type (required for Core)" value={businessType} onChange={setBusinessType} options={BUSINESS_TYPES} />
            <Input label="Client Partner (optional)" value={clientPartner} onChange={setClientPartner} placeholder="Direct client / managed service partner" />
          </>
        )}
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={saving} onClick={handleSubmit}>
          {saving ? "Creating…" : "Create Project"}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function ProjectDetailPanel({ project, onChanged }) {
  const [milestones, setMilestones] = useState(null);
  const [unfilledRoles, setUnfilledRoles] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [showMilestoneForm, setShowMilestoneForm] = useState(false);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const [mRes, uRes, rRes] = await Promise.all([
        getMilestones(project.id),
        getUnfilledRoles(project.id),
        getExpectedRevenue(project.id),
      ]);
      setMilestones(mRes.milestones || []);
      setUnfilledRoles(uRes.roles || []);
      setRevenue(rRes);
    } catch (err) {
      setError(err.message || "Failed to load project details.");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [project.id]);

  const handleAddMilestone = async () => {
    if (!title.trim() || !dueDate) {
      setError("Title and due date are required.");
      return;
    }
    setError("");
    try {
      await createMilestone(project.id, { title: title.trim(), due_date: dueDate });
      setTitle("");
      setDueDate("");
      setShowMilestoneForm(false);
      load();
    } catch (err) {
      setError(err.message || "Failed to add milestone.");
    }
  };

  const handleComplete = async (milestoneId) => {
    try {
      await completeMilestone(project.id, milestoneId);
      load();
    } catch (err) {
      setError(err.message || "Failed to complete milestone.");
    }
  };

  const formatUsdCents = (cents) =>
    cents == null ? "—" : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="mt-3 grid gap-3 border-t pt-3">
      {error ? <div className="text-xs text-rose-700">{error}</div> : null}

      <div>
        <div className="mb-1 flex items-center justify-between">
          <div className="flex items-center gap-1 text-xs font-semibold text-gray-700">
            <Flag className="h-3 w-3" /> Milestones
          </div>
          <Button variant="ghost" onClick={() => setShowMilestoneForm((v) => !v)}>
            {showMilestoneForm ? "Cancel" : "Add"}
          </Button>
        </div>
        {showMilestoneForm ? (
          <div className="mb-2 flex flex-wrap gap-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Milestone title"
              className="rounded-lg border px-2 py-1 text-xs outline-none"
            />
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="rounded-lg border px-2 py-1 text-xs outline-none"
            />
            <Button variant="secondary" onClick={handleAddMilestone}>
              Save
            </Button>
          </div>
        ) : null}
        {!milestones ? (
          <div className="text-xs text-gray-500">Loading…</div>
        ) : milestones.length === 0 ? (
          <div className="text-xs text-gray-500">No milestones yet.</div>
        ) : (
          <ul className="space-y-1">
            {milestones.map((m) => (
              <li key={m.id} className="flex items-center justify-between rounded-lg border px-2 py-1 text-xs">
                <span>
                  {m.title} · due {m.due_date}
                  {m.is_complete === "COMPLETE" ? ` · completed ${m.completion_date} (delay ${m.delay_days}d)` : ""}
                </span>
                {m.is_complete === "PENDING" ? (
                  <Button variant="ghost" onClick={() => handleComplete(m.id)}>
                    <CheckCircle2 className="h-3 w-3" /> Complete
                  </Button>
                ) : (
                  <span className="text-emerald-700">Done</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-gray-700">
          <Users className="h-3 w-3" /> Unfilled Roles
        </div>
        {!unfilledRoles ? (
          <div className="text-xs text-gray-500">Loading…</div>
        ) : unfilledRoles.length === 0 ? (
          <div className="text-xs text-gray-500">No open headcount gaps.</div>
        ) : (
          <ul className="space-y-1">
            {unfilledRoles.map((r) => (
              <li key={r.demand_id} className="rounded-lg border px-2 py-1 text-xs">
                {r.job_title} · {r.open_positions} open · {r.gap_status}
                {r.days_until_start != null ? ` · ${r.days_until_start}d until start` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-gray-700">
          <TrendingUp className="h-3 w-3" /> Expected Revenue
        </div>
        {!revenue ? (
          <div className="text-xs text-gray-500">Loading…</div>
        ) : (
          <div className="text-xs text-gray-700">
            {formatUsdCents(revenue.expected_revenue_usd_cents)}
            {revenue.margin_usd_cents != null ? ` · margin ${formatUsdCents(revenue.margin_usd_cents)}` : ""}
            {" · "}
            <span
              className={cx(
                "font-semibold",
                revenue.margin_indicator === "AT_RISK" ? "text-rose-700" : revenue.margin_indicator === "HEALTHY" ? "text-emerald-700" : "text-gray-500",
              )}
            >
              {revenue.margin_indicator}
            </span>
            <div className="mt-1 text-[11px] text-gray-400">{revenue.note}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function ProjectCard({ project, onChanged }) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const nextStatuses = STATUS_TRANSITIONS[project.status] || [];

  const handleTransition = async (status) => {
    setBusy(true);
    setError("");
    try {
      await transitionProjectStatus(project.id, status);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to change status.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-gray-900">{project.name}</div>
          <div className="text-xs text-gray-500">
            {project.delivery_engine}
            {project.si_partner ? ` · ${project.si_partner}` : ""}
            {project.business_type ? ` · ${project.business_type}` : ""} · {project.billing_type} · {project.currency}
          </div>
          {project.end_client || project.client_partner ? (
            <div className="text-xs text-gray-400">
              {project.end_client ? `End Client: ${project.end_client}` : ""}
              {project.end_client && project.client_partner ? " · " : ""}
              {project.client_partner ? `Client Partner: ${project.client_partner}` : ""}
            </div>
          ) : null}
        </div>
        <span className={cx("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", STATUS_STYLES[project.status])}>
          {project.status}
        </span>
      </div>
      {error ? <div className="mt-2 text-xs text-rose-700">{error}</div> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {nextStatuses.map((s) => (
          <Button key={s} variant="secondary" disabled={busy} onClick={() => handleTransition(s)}>
            → {s}
          </Button>
        ))}
        <Button variant="ghost" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Hide Details" : "View Details"}
        </Button>
      </div>
      {expanded ? <ProjectDetailPanel project={project} onChanged={onChanged} /> : null}
    </div>
  );
}

export default function ProjectsScreen() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getProjects();
      setProjects(res?.projects || []);
    } catch (err) {
      setError(err.message || "Failed to load projects.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="grid gap-4">
      <Card
        title="Projects"
        subtitle="SI Partner is required for Speciality Engine projects -- revenue attribution and RM Agent continuity scoring depend on it."
        icon={<FolderKanban className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}

        <div className="mb-4">
          <CreateProjectForm onCreated={load} />
        </div>

        <div className="grid gap-3">
          {loading ? (
            <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
          ) : projects.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">No projects yet.</div>
          ) : (
            projects.map((p) => <ProjectCard key={p.id} project={p} onChanged={load} />)
          )}
        </div>
      </Card>
    </div>
  );
}
