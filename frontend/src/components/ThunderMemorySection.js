// S-023/HRMS-0423 -- Candidate Memory Viewer (Recruiter UI). Mounted in
// MessagesTab below the missing-fields banner (this real screen has no
// two-column sidebar layout the spec assumed -- adapted to the actual
// single-column tab structure).
import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Pencil } from "lucide-react";
import { toast } from "react-toastify";
import { correctMemoryFact, getCandidateMemory } from "../services/api/aiAgent";
import ScreenErrorDisplay from "./ScreenErrorDisplay";
import { Clock, Zap } from "lucide-react";

const CATEGORY_LABELS = {
  SALARY: "Salary",
  PREFERENCE: "Preferences",
  CONSTRAINT: "Constraints",
  MOTIVATOR: "Motivators",
  OBJECTION: "Objections",
  AVAILABILITY: "Availability",
  SKILL: "Skills",
  EMPLOYER: "Employer",
  PERSONAL: "Other",
};
const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS);

const KEY_LABELS = {
  expected_ctc: "Expected Salary",
  current_ctc: "Current Salary",
  notice_period: "Notice Period",
  location_constraint: "Location Constraint",
  domain: "Domain Interest",
};

function formatKeyLabel(key) {
  if (KEY_LABELS[key]) return KEY_LABELS[key];
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function confidenceColor(confidence) {
  if (confidence >= 0.8) return { dot: "bg-green-500", tooltip: "High confidence" };
  if (confidence >= 0.5) return { dot: "bg-amber-500", tooltip: "Medium confidence" };
  return { dot: "bg-red-500", tooltip: "Low confidence — verify with candidate before using" };
}

function timeAgo(iso) {
  if (!iso) return "";
  const hours = Math.round((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function formatCountdown(iso) {
  if (!iso) return "—";
  const nextTime = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = nextTime - now;

  if (diffMs < 0) return "overdue";

  const hours = Math.round(diffMs / (1000 * 60 * 60));
  const minutes = Math.round((diffMs % (1000 * 60 * 60)) / (1000 * 60));

  if (hours < 1) return `in ${minutes}m`;
  if (hours < 24) return `in ${hours}h`;
  const days = Math.round(hours / 24);
  return `in ${days}d`;
}

function FactRow({ fact, candidateId, onCorrected }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(fact.value);
  const [saving, setSaving] = useState(false);
  const [screenError, setScreenError] = useState(null);
  const { dot, tooltip } = confidenceColor(fact.confidence);

  const handleSave = async () => {
    if (!draft.trim() || draft === fact.value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      const updated = await correctMemoryFact(candidateId, fact.id, draft.trim()).catch(e => { throw e; });
      onCorrected(updated);
      toast.success("Memory updated.");
      setEditing(false);
    } catch (err) {
      setScreenError(err.message || "Could not save. Please try again.");
      setDraft(fact.value);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
      <div className="group flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-gray-50">
      <div className="min-w-0 flex-1">
        <span className="text-xs text-gray-500">{formatKeyLabel(fact.key)}: </span>
        {editing ? (
          <div className="mt-1 flex items-center gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value.slice(0, 500))}
              className="flex-1 rounded-lg border px-2 py-1 text-sm"
              autoFocus
            />
            <button type="button" onClick={handleSave} disabled={saving} className="text-xs font-semibold text-bx-orange">
              Save
            </button>
            <button type="button" onClick={() => { setEditing(false); setDraft(fact.value); }} className="text-xs font-semibold text-gray-500">
              Cancel
            </button>
          </div>
        ) : (
          <span className="text-sm font-bold text-gray-900">{fact.value}</span>
        )}
      </div>
      {!editing && (
        <div className="flex shrink-0 items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dot}`} title={tooltip} />
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="opacity-0 transition group-hover:opacity-100"
            title="Correct this fact"
          >
            <Pencil className="h-3.5 w-3.5 text-gray-400 hover:text-gray-700" />
          </button>
        </div>
      )}
      </div>
    </>
  );
}

export default function ThunderMemorySection({ candidateId }) {
  const [expanded, setExpanded] = useState(false);
  const [memory, setMemory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    if (!candidateId) return;
    setLoading(true);
    setError("");
    try {
      const res = await getCandidateMemory(candidateId).catch(e => { throw e; });
      setMemory(res);
    } catch (err) {
      setError("Memory unavailable. Please refresh.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (expanded && !memory) load();
    // eslint-disable-next-line
  }, [expanded, candidateId]);

  const handleCorrected = (updatedFact) => {
    setMemory((prev) => ({
      ...prev,
      facts: prev.facts.map((f) => (f.id === updatedFact.id ? updatedFact : f)),
    }));
  };

  const factsByCategory = {};
  (memory?.facts || []).forEach((f) => {
    if (!factsByCategory[f.category]) factsByCategory[f.category] = [];
    factsByCategory[f.category].push(f);
  });

  const factCount = memory?.facts?.length || 0;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-gray-800">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          Thunder's Memory{factCount ? ` (${factCount} facts)` : ""}
        </span>
      </button>

      {expanded ? (
        <div className="border-t border-gray-100 px-4 py-3">
          {loading ? (
            <div className="text-sm text-gray-500">Loading…</div>
          ) : error ? (
            <div className="text-sm text-rose-600">{error}</div>
          ) : (
            <>
              {/* Thunder Contact Status */}
              {memory?.last_contact_at && (
                <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 p-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-blue-900 mb-2">
                    <Zap className="h-4 w-4 text-blue-600" />
                    Thunder Outreach Status
                  </div>
                  <div className="space-y-1.5 text-sm text-blue-800">
                    <div className="flex items-center gap-2">
                      <Clock className="h-3.5 w-3.5 text-blue-600" />
                      <span>Last contact: <span className="font-semibold">{timeAgo(memory.last_contact_at)}</span></span>
                    </div>
                    {memory?.next_contact_at ? (
                      <div className="flex items-center gap-2">
                        <Clock className="h-3.5 w-3.5 text-blue-600" />
                        <span>Next contact: <span className="font-semibold">{formatCountdown(memory.next_contact_at)}</span></span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-amber-700">
                        <span className="font-semibold">Thunder is paused for this candidate</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="mb-3">
                <div className="text-xs font-semibold uppercase text-gray-400">
                  Thunder's Summary{memory?.last_updated ? ` — last updated ${timeAgo(memory.last_updated)}` : ""}
                </div>
                <p className="mt-1 text-sm italic text-gray-600">
                  {memory?.summary || "Thunder is still learning about this candidate. Memory builds as conversations progress."}
                </p>
              </div>

              {CATEGORY_ORDER.filter((cat) => factsByCategory[cat]?.length).map((cat) => (
                <div key={cat} className="mb-3">
                  <div className="mb-1 text-xs font-bold text-gray-700">{CATEGORY_LABELS[cat]}</div>
                  <div className="flex flex-col divide-y divide-gray-50">
                    {factsByCategory[cat].map((fact) => (
                      <FactRow key={fact.id} fact={fact} candidateId={candidateId} onCorrected={handleCorrected} />
                    ))}
                  </div>
                </div>
              ))}
              {!factCount ? <div className="text-sm text-gray-500">No facts recorded yet.</div> : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
