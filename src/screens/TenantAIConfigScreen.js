// S-077/HRMS-0477 -- Tenant AI Configuration. Unified admin page over
// settings previously scattered across S-011 (identity), S-041
// (follow-up timing), S-020 (SLA), S-065 (digest), S-075 (global
// pause) -- each section is its own independent read/edit/save unit,
// per Step 3. No config-history UI (Section 9 explicitly excludes it)
// -- "Last updated" below is the one real, unified timestamp this
// story's own table actually stores, not per-section fabricated history.
import { useEffect, useState } from "react";
import { Bot, Clock, Gauge, Mail, Power, RefreshCw } from "lucide-react";
import { toast } from "react-toastify";
import { Card, Button, Input, TextArea, Select } from "../components/ui";
import { getTenantAIConfig, updateTenantAIConfig } from "../services/api/tenantAiConfig";

const GREETING_CHANNELS = ["BOTH_PARALLEL", "WHATSAPP_FIRST", "EMAIL_FIRST"];

export default function TenantAIConfigScreen() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getTenantAIConfig();
      setConfig(res);
    } catch (err) {
      setError(err.message || "Failed to load AI configuration.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (updates) => {
    try {
      const res = await updateTenantAIConfig(updates);
      setConfig(res);
      toast.success("Saved.");
      return true;
    } catch (err) {
      toast.error(err.message || "Failed to save.");
      return false;
    }
  };

  if (loading || !config) {
    return (
      <div className="grid gap-4">
        <Card title="Tenant AI Configuration" subtitle="Loading Thunder's settings...">
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        </Card>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      ) : null}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Tenant AI Configuration</h1>
          <p className="text-sm text-gray-500">
            All of Thunder's settings for this org, in one place. Last updated{" "}
            {config.updated_at ? new Date(config.updated_at).toLocaleString() : "never"}
            {config.updated_by ? ` by ${config.updated_by}` : ""}.
          </p>
        </div>
        <Button variant="ghost" onClick={load}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <IdentitySection config={config} save={save} />
      <EngagementTimingSection config={config} save={save} />
      <SlaSection config={config} save={save} />
      <DigestSection config={config} save={save} />
      <GlobalControlsSection config={config} save={save} />
    </div>
  );
}

function SectionShell({ title, subtitle, icon, children, editing, onEdit, onCancel, onSave, saving }) {
  return (
    <Card
      title={title}
      subtitle={subtitle}
      icon={icon}
      right={
        editing ? (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onCancel} disabled={saving}>
              Cancel
            </Button>
            <Button variant="primary" onClick={onSave} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        ) : (
          <Button variant="ghost" onClick={onEdit}>
            Edit
          </Button>
        )
      }
    >
      {children}
    </Card>
  );
}

function IdentitySection({ config, save }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState(config.ai_agent_name);
  const [persona, setPersona] = useState(config.ai_agent_persona || "");
  const [baApproved, setBaApproved] = useState(false);

  const startEdit = () => {
    setName(config.ai_agent_name);
    setPersona(config.ai_agent_persona || "");
    setBaApproved(false);
    setEditing(true);
  };

  const handleSave = async () => {
    const updates = {};
    if (name !== config.ai_agent_name) {
      if (!window.confirm("Changing the agent name will affect all future messages. Current active conversations will see the new name on next message. Continue?")) {
        return;
      }
      updates.ai_agent_name = name;
    }
    if (persona !== (config.ai_agent_persona || "")) {
      if (!baApproved) {
        toast.error("Persona changes require confirming Lead BA approval first.");
        return;
      }
      updates.ai_agent_persona = persona;
      updates.ba_approved = true;
    }
    if (Object.keys(updates).length === 0) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const ok = await save(updates);
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <SectionShell
      title="Identity"
      subtitle="Thunder's name and persona, used in every message this org's candidates receive."
      icon={<Bot className="h-4 w-4" />}
      editing={editing}
      onEdit={startEdit}
      onCancel={() => setEditing(false)}
      onSave={handleSave}
      saving={saving}
    >
      {editing ? (
        <div className="grid max-w-xl gap-4">
          <Input label="AI Agent Name" value={name} onChange={setName} placeholder="Thunder" />
          <TextArea label="AI Agent Persona" value={persona} onChange={setPersona} rows={4} />
          {persona !== (config.ai_agent_persona || "") && (
            <label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <input type="checkbox" className="mt-0.5" checked={baApproved} onChange={(e) => setBaApproved(e.target.checked)} />
              The AI persona change requires Lead BA written approval before it goes live. I confirm the BA has approved this change.
            </label>
          )}
        </div>
      ) : (
        <div className="grid max-w-xl gap-2 text-sm">
          <div><span className="font-medium text-gray-700">Name:</span> {config.ai_agent_name}</div>
          <div><span className="font-medium text-gray-700">Persona:</span> {config.ai_agent_persona || <span className="text-gray-400">(default)</span>}</div>
        </div>
      )}
    </SectionShell>
  );
}

function EngagementTimingSection({ config, save }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [greeting, setGreeting] = useState(config.greeting_channel);
  const [waHours, setWaHours] = useState(String(config.whatsapp_followup_hours));
  const [emailHours, setEmailHours] = useState(String(config.email_followup_hours));
  const [maxFollowups, setMaxFollowups] = useState(String(config.max_followup_count));
  const [reactivationDays, setReactivationDays] = useState(String(config.ghosting_reactivation_days));

  const startEdit = () => {
    setGreeting(config.greeting_channel);
    setWaHours(String(config.whatsapp_followup_hours));
    setEmailHours(String(config.email_followup_hours));
    setMaxFollowups(String(config.max_followup_count));
    setReactivationDays(String(config.ghosting_reactivation_days));
    setEditing(true);
  };

  const handleSave = async () => {
    const wa = Number(waHours);
    const em = Number(emailHours);
    const maxN = Number(maxFollowups);
    if (wa < 1 || wa > 168 || em < 1 || em > 168) {
      toast.error("Follow-up hours must be between 1 and 168 (7 days).");
      return;
    }
    if (maxN < 1 || maxN > 10) {
      toast.error("Max follow-ups must be between 1 and 10.");
      return;
    }
    if (maxN > 5 && !window.confirm("High follow-up counts may feel spammy to candidates. Continue?")) {
      return;
    }
    setSaving(true);
    const ok = await save({
      greeting_channel: greeting,
      whatsapp_followup_hours: wa,
      email_followup_hours: em,
      max_followup_count: maxN,
      ghosting_reactivation_days: Number(reactivationDays),
    });
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <SectionShell
      title="Engagement Timing"
      subtitle="First-touch channel and follow-up cadence."
      icon={<Clock className="h-4 w-4" />}
      editing={editing}
      onEdit={startEdit}
      onCancel={() => setEditing(false)}
      onSave={handleSave}
      saving={saving}
    >
      {editing ? (
        <div className="grid max-w-xl gap-4">
          <Select label="Greeting Channel" value={greeting} onChange={setGreeting} options={GREETING_CHANNELS} />
          <Input label="WhatsApp Follow-up Hours" type="number" value={waHours} onChange={setWaHours} />
          <Input label="Email Follow-up Hours" type="number" value={emailHours} onChange={setEmailHours} />
          <Input label="Max Follow-ups" type="number" value={maxFollowups} onChange={setMaxFollowups} />
          <Input label="Ghosting Reactivation Days" type="number" value={reactivationDays} onChange={setReactivationDays} />
        </div>
      ) : (
        <div className="grid max-w-xl gap-2 text-sm">
          <div><span className="font-medium text-gray-700">Greeting Channel:</span> {config.greeting_channel}</div>
          <div><span className="font-medium text-gray-700">WhatsApp Follow-up:</span> every {config.whatsapp_followup_hours}h</div>
          <div><span className="font-medium text-gray-700">Email Follow-up:</span> every {config.email_followup_hours}h</div>
          <div><span className="font-medium text-gray-700">Max Follow-ups:</span> {config.max_followup_count}</div>
          <div><span className="font-medium text-gray-700">Ghosting Reactivation:</span> after {config.ghosting_reactivation_days} days</div>
        </div>
      )}
    </SectionShell>
  );
}

function SlaSection({ config, save }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [firstContact, setFirstContact] = useState(String(config.sla_first_contact_seconds));
  const [noContact, setNoContact] = useState(String(config.sla_no_contact_hours));

  const startEdit = () => {
    setFirstContact(String(config.sla_first_contact_seconds));
    setNoContact(String(config.sla_no_contact_hours));
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    const ok = await save({
      sla_first_contact_seconds: Number(firstContact),
      sla_no_contact_hours: Number(noContact),
    });
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <SectionShell
      title="SLA Settings"
      subtitle="How fast Thunder must make first contact, and when a stale conversation counts as a breach."
      icon={<Gauge className="h-4 w-4" />}
      editing={editing}
      onEdit={startEdit}
      onCancel={() => setEditing(false)}
      onSave={handleSave}
      saving={saving}
    >
      {editing ? (
        <div className="grid max-w-xl gap-4">
          <Input label="First Contact SLA (seconds)" type="number" value={firstContact} onChange={setFirstContact} />
          <Input label="No-Contact Breach Alert (hours)" type="number" value={noContact} onChange={setNoContact} />
        </div>
      ) : (
        <div className="grid max-w-xl gap-2 text-sm">
          <div><span className="font-medium text-gray-700">First Contact SLA:</span> {config.sla_first_contact_seconds}s</div>
          <div><span className="font-medium text-gray-700">No-Contact Breach Alert:</span> {config.sla_no_contact_hours}h</div>
        </div>
      )}
    </SectionShell>
  );
}

function DigestSection({ config, save }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(config.digest_enabled);
  const [sendTime, setSendTime] = useState(config.digest_send_time);

  const startEdit = () => {
    setEnabled(config.digest_enabled);
    setSendTime(config.digest_send_time);
    setEditing(true);
  };

  const handleSave = async () => {
    if (!/^\d{2}:\d{2}$/.test(sendTime)) {
      toast.error("Send time must be in HH:MM format.");
      return;
    }
    setSaving(true);
    const ok = await save({ digest_enabled: enabled, digest_send_time: sendTime });
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <SectionShell
      title="Daily Digest"
      subtitle="Morning summary sent to each recruiter, in their own local timezone."
      icon={<Mail className="h-4 w-4" />}
      editing={editing}
      onEdit={startEdit}
      onCancel={() => setEditing(false)}
      onSave={handleSave}
      saving={saving}
    >
      {editing ? (
        <div className="grid max-w-xl gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            Digest Enabled
          </label>
          <Input label="Digest Send Time (HH:MM, local)" value={sendTime} onChange={setSendTime} placeholder="08:00" />
        </div>
      ) : (
        <div className="grid max-w-xl gap-2 text-sm">
          <div><span className="font-medium text-gray-700">Enabled:</span> {config.digest_enabled ? "Yes" : "No"}</div>
          <div><span className="font-medium text-gray-700">Send Time:</span> {config.digest_send_time} (each recruiter's local time)</div>
        </div>
      )}
    </SectionShell>
  );
}

function GlobalControlsSection({ config, save }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(config.thunder_enabled);
  const [keywords, setKeywords] = useState((config.escalation_keywords || []).join(", "));

  const startEdit = () => {
    setEnabled(config.thunder_enabled);
    setKeywords((config.escalation_keywords || []).join(", "));
    setEditing(true);
  };

  const handleSave = async () => {
    const updates = {};
    if (enabled !== config.thunder_enabled) {
      if (!enabled && !window.confirm("Disabling Thunder will pause all AI activity for all candidates immediately. Continue?")) {
        return;
      }
      updates.thunder_enabled = enabled;
    }
    const keywordList = keywords.split(",").map((k) => k.trim()).filter(Boolean);
    updates.escalation_keywords = keywordList;
    setSaving(true);
    const ok = await save(updates);
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <SectionShell
      title="Global Controls"
      subtitle="Kill switch and custom escalation triggers, org-wide."
      icon={<Power className="h-4 w-4" />}
      editing={editing}
      onEdit={startEdit}
      onCancel={() => setEditing(false)}
      onSave={handleSave}
      saving={saving}
    >
      {editing ? (
        <div className="grid max-w-xl gap-4">
          <div className="rounded-xl border border-red-200 bg-red-50 p-3">
            <label className="flex items-center gap-2 text-sm font-semibold text-red-700">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              Thunder Enabled
            </label>
          </div>
          <Input
            label="Escalation Keywords (comma-separated, merged with the built-in legal-keyword list)"
            value={keywords}
            onChange={setKeywords}
            placeholder="e.g. harassment, compensation dispute"
          />
        </div>
      ) : (
        <div className="grid max-w-xl gap-2 text-sm">
          <div>
            <span className="font-medium text-gray-700">Thunder:</span>{" "}
            <span className={config.thunder_enabled ? "text-emerald-700" : "text-red-700 font-semibold"}>
              {config.thunder_enabled ? "Enabled" : "Disabled"}
            </span>
          </div>
          <div>
            <span className="font-medium text-gray-700">Custom Escalation Keywords:</span>{" "}
            {(config.escalation_keywords || []).length ? config.escalation_keywords.join(", ") : <span className="text-gray-400">(none)</span>}
          </div>
        </div>
      )}
    </SectionShell>
  );
}
