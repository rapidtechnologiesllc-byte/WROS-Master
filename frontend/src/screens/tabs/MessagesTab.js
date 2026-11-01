// S-005/S-006 -- Unified Conversation Timeline / Messages tab.
// S-001/S-007/S-008 -- AI agent assignment + missing-fields preview, surfaced here
// since there was previously no UI anywhere for /ai-agent/* endpoints.
// S-009/S-010 -- manual message send + ownership take-over/hand-back.
import { useCallback, useEffect, useState } from "react";
import {
  getConversationThread,
  getMissingFields,
  sendManualMessage,
  takeOverConversation,
  handBackConversation,
  pollForReply,
  pauseThunder,
  resumeThunder,
} from "../../services/api/aiAgent";
import { AlertCircle, CheckCircle, X } from "lucide-react";
import ThunderMemorySection from "../../components/ThunderMemorySection";
import ThunderActivitySection from "../../components/activity/ThunderActivitySection";
import EngagementMetricsSection from "../../components/engagement/EngagementMetricsSection";

// State for action feedback (replaces toast notifications)
const useActionFeedback = () => {
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const clearError = () => setActionError(null);
  const clearSuccess = () => setActionSuccess(null);

  return { actionError, setActionError, actionSuccess, setActionSuccess, clearError, clearSuccess };
};

const EVENT_LABELS = {
  ai_assigned: "AI Agent Assigned",
  field_check: "Missing-Field Check",
  ai_message_sent: "Message Sent",
  hr_message_sent: "Message Sent",
  ownership_changed: "Ownership Changed",
  candidate_reply: "Candidate Replied",
  gemini_parse: "AI Parsed Reply",
  fields_merged: "Fields Updated",
  status_changed: "Status Changed",
};

export default function MessagesTab({ candidateId }) {
  const [thread, setThread] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [missingFields, setMissingFields] = useState(null);
  const [polling, setPolling] = useState(false);

  // Action feedback state
  const { actionError, setActionError, actionSuccess, setActionSuccess, clearError, clearSuccess } = useActionFeedback();

  const fetchThread = useCallback(async () => {
    if (!candidateId) return;
    try {
      setLoading(true);
      setError("");
      const res = await getConversationThread(candidateId);
      setThread(res);
    } catch (err) {
      console.error("Failed to fetch conversation thread", err);
      setError("Failed to load messages");
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchThread();
  }, [fetchThread]);

  const fetchMissingFields = useCallback(async () => {
    if (!candidateId) return;
    try {
      const res = await getMissingFields(candidateId);
      setMissingFields(res);
    } catch (err) {
      console.error("Failed to fetch missing fields", err);
      setActionError("Failed to load missing fields");
    }
  }, [candidateId, setActionError]);

  useEffect(() => {
    fetchMissingFields();
  }, [fetchMissingFields]);

  // AI recruiter auto-assigned - no manual assignment needed

  const handleCheckReply = async () => {
    if (!candidateId) return;
    try {
      setPolling(true);
      const res = await pollForReply(candidateId);
      if (res?.status === "no_reply_found") {
        setActionSuccess("No new reply found yet.");
      } else if (res?.updated_fields?.length) {
        setActionSuccess(`Updated: ${res.updated_fields.join(", ")}`);
      } else {
        setActionSuccess("Reply processed.");
      }
      await fetchThread();
      await fetchMissingFields();
    } catch (err) {
      console.error("Failed to check for reply", err);
      setActionError(err?.message || "Failed to check for reply");
    } finally {
      setPolling(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <SectionHeader
          title="Messages"
          subtitle="Loading conversation history..."
        />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <SectionHeader
          title="Messages"
          subtitle="Could not load the conversation timeline."
        />
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  const conversations = thread?.conversations || [];
  const thunder = thread?.thunder;
  const hasThunderItems = !!thunder?.items?.length;

  return (
    <div className="space-y-6">
      {/* Error Banner */}
      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <p className="text-sm text-red-700">{actionError}</p>
          </div>
          <button
            onClick={clearError}
            className="text-red-600 hover:text-red-700 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Success Banner */}
      {actionSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-emerald-600 flex-shrink-0" />
            <p className="text-sm text-emerald-700">{actionSuccess}</p>
          </div>
          <button
            onClick={clearSuccess}
            className="text-emerald-600 hover:text-emerald-700 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <SectionHeader
        title="Messages"
        subtitle="AI recruiter conversation timeline for this candidate."
      />

      {!!missingFields?.total_missing && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="text-sm font-semibold text-amber-800">
            {missingFields.total_missing} missing field
            {missingFields.total_missing === 1 ? "" : "s"}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {missingFields.missing_fields.map((f) => (
              <span
                key={f.field}
                className="rounded-full border border-amber-200 bg-white px-2.5 py-1 text-xs font-medium text-amber-700"
              >
                {f.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* AI recruiter auto-assigned on candidate creation */}
      {candidateId ? <ThunderMemorySection candidateId={candidateId} /> : null}
      {candidateId ? <ThunderActivitySection candidateId={candidateId} /> : null}
      {candidateId ? <EngagementMetricsSection candidateId={candidateId} /> : null}

      {hasThunderItems && <ThunderEmailsCard thunder={thunder} />}

      {!conversations.length ? (
        hasThunderItems ? null : <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center">
          <p className="text-sm text-gray-500">No messages yet</p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap justify-end gap-2">
            {conversations.some((c) => c.status === "awaiting_candidate") && (
              <button
                type="button"
                onClick={handleCheckReply}
                disabled={polling}
                title="Poll the AI recruiter's mailbox for a new candidate reply and process it"
                className="inline-flex items-center rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700 transition hover:bg-emerald-100 disabled:opacity-60"
              >
                {polling ? "Checking..." : "Check for Reply"}
              </button>
            )}
          </div>
          {conversations.map((conv) => (
            <ConversationCard
              key={conv.conversation_id}
              conversation={conv}
              onChanged={fetchThread}
              setActionError={setActionError}
              setActionSuccess={setActionSuccess}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ConversationCard({ conversation, onChanged, setActionError, setActionSuccess }) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [ownershipBusy, setOwnershipBusy] = useState(false);
  const [pauseBusy, setPauseBusy] = useState(false);
  const [showPauseModal, setShowPauseModal] = useState(false);

  const events = [...(conversation.events || [])].sort(
    (a, b) => new Date(a?.created_at || 0) - new Date(b?.created_at || 0),
  );

  const isHumanOwned = conversation.owner_type === "hr_user";
  const isAiOwned = conversation.owner_type === "ai_agent";

  const handlePause = async (durationMs) => {
    try {
      setPauseBusy(true);
      const resumeAt = durationMs ? new Date(Date.now() + durationMs).toISOString() : null;
      await pauseThunder(conversation.conversation_id, resumeAt);
      setActionSuccess("Thunder paused for this candidate");
      setShowPauseModal(false);
      await onChanged?.();
    } catch (err) {
      console.error("Failed to pause Thunder", err);
      setActionError(err?.message || "Failed to pause Thunder");
    } finally {
      setPauseBusy(false);
    }
  };

  const handleResume = async () => {
    try {
      setPauseBusy(true);
      await resumeThunder(conversation.conversation_id);
      setActionSuccess("Thunder resumed for this candidate");
      await onChanged?.();
    } catch (err) {
      console.error("Failed to resume Thunder", err);
      setActionError(err?.message || "Failed to resume Thunder");
    } finally {
      setPauseBusy(false);
    }
  };

  // S-035/HRMS-0435 6A: "Escalation Reason" text, sourced from the latest
  // escalation_triggered event already present in this conversation's own
  // event log -- no separate backend field needed for this.
  const escalationReason =
    conversation.escalation_state === "escalated"
      ? [...events].reverse().find((e) => e.event_type === "escalation_triggered")
          ?.event_data?.reason
      : null;

  const handleSend = async () => {
    if (!message.trim()) return;
    try {
      setSending(true);
      await sendManualMessage(conversation.conversation_id, message.trim());
      setMessage("");
      await onChanged?.();
    } catch (err) {
      console.error("Failed to send message", err);
      setActionError(err?.message || "Failed to send message");
    } finally {
      setSending(false);
    }
  };

  const handleTakeOver = async () => {
    try {
      setOwnershipBusy(true);
      await takeOverConversation(conversation.conversation_id);
      setActionSuccess("Conversation taken over");
      await onChanged?.();
    } catch (err) {
      console.error("Failed to take over conversation", err);
      setActionError(err?.message || "Failed to take over conversation");
    } finally {
      setOwnershipBusy(false);
    }
  };

  const handleHandBack = async () => {
    try {
      setOwnershipBusy(true);
      await handBackConversation(conversation.conversation_id);
      setActionSuccess("Handed back to AI recruiter");
      await onChanged?.();
    } catch (err) {
      console.error("Failed to hand back conversation", err);
      setActionError(err?.message || "Failed to hand back conversation");
    } finally {
      setOwnershipBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-base font-semibold text-gray-900">
            {conversation.ai_agent_name || "AI Recruiter"}
          </h4>
          <StatusBadge value={conversation.status} />
          {conversation.owner_type && (
            <span className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-600">
              Owner: {conversation.owner_type}
            </span>
          )}
          {conversation.channel_preference && (
            <span className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-600">
              {conversation.channel_preference}
            </span>
          )}
          {conversation.escalation_state &&
            conversation.escalation_state !== "none" && (
              <span className="rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700">
                {conversation.escalation_state === "escalated"
                  ? "Needs human attention"
                  : `Escalation: ${conversation.escalation_state}`}
              </span>
            )}
          {conversation.is_thunder_paused && (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
              Thunder: PAUSED
              {conversation.thunder_resume_at
                ? ` — resumes ${formatDateTime(conversation.thunder_resume_at)}`
                : " — until manually resumed"}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400">
          Updated {formatDateTime(conversation.updated_at)}
        </span>
      </div>

      {escalationReason && (
        <p className="mt-2 text-sm text-red-700">
          Escalation reason: {escalationReason}
        </p>
      )}

      {conversation.summary && (
        <p className="mt-3 text-sm italic text-gray-600">
          Thunder's summary: {conversation.summary}
        </p>
      )}
      {conversation.no_contact_breach_hours != null && (
        <p className="mt-2 text-sm font-medium text-amber-600">
          ⚠ No contact in {Math.round(conversation.no_contact_breach_hours)} hours
        </p>
      )}
      {conversation.next_action && (
        <p className="mt-1 text-xs font-medium text-indigo-600">
          Next: {conversation.next_action}
        </p>
      )}

      <div className="mt-4 space-y-3 border-t border-gray-100 pt-4">
        {events.length ? (
          events.map((ev) => <EventRow key={ev.id} event={ev} />)
        ) : (
          <div className="text-sm text-gray-400">No events logged yet.</div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-4">
        {isHumanOwned ? (
          <button
            type="button"
            onClick={handleHandBack}
            disabled={ownershipBusy}
            className="inline-flex items-center rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-60"
          >
            {ownershipBusy ? "Working..." : "Hand Back to AI"}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleTakeOver}
            disabled={ownershipBusy}
            className="inline-flex items-center rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100 disabled:opacity-60"
          >
            {ownershipBusy ? "Working..." : "Take Over"}
          </button>
        )}
        {isAiOwned &&
          (conversation.is_thunder_paused ? (
            <button
              type="button"
              onClick={handleResume}
              disabled={pauseBusy}
              className="inline-flex items-center rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700 transition hover:bg-emerald-100 disabled:opacity-60"
            >
              {pauseBusy ? "Working..." : "Resume Thunder"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setShowPauseModal(true)}
              disabled={pauseBusy}
              className="inline-flex items-center rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100 disabled:opacity-60"
            >
              Pause Thunder for this candidate
            </button>
          ))}
      </div>

      {showPauseModal && (
        <PauseThunderModal
          busy={pauseBusy}
          onConfirm={handlePause}
          onCancel={() => setShowPauseModal(false)}
        />
      )}

      <div className="mt-3 flex items-end gap-2">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type a message to send to the candidate..."
          rows={2}
          className="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm outline-none transition focus:border-gray-400"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={sending || !message.trim()}
          className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-60"
        >
          {sending ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}

const INTENT_SOURCE_LABELS = {
  rule: "decided by rule",
  llm: "decided by AI",
  keyword: "keyword fallback (AI unavailable)",
};

function humanize(value) {
  return String(value || "").toLowerCase().replace(/_/g, " ");
}

// How Thunder read one of the candidate's emails: intent, how it was decided, the matched words.
function intentDescription(item) {
  if (!item.intent) return "Not classified yet";
  const parts = [`Read as ${humanize(item.intent)}`];
  if (item.intent_source) parts.push(INTENT_SOURCE_LABELS[item.intent_source] || item.intent_source);
  if (item.intent_confidence != null) parts.push(`${Math.round(item.intent_confidence * 100)}% confidence`);
  if (item.intent_evidence) parts.push(`matched "${item.intent_evidence}"`);
  return parts.join(" · ");
}

// Thunder's own email thread (ThunderEmailMessage): what Thunder sent, what the candidate wrote,
// and what stopped Thunder.
function ThunderEmailsCard({ thunder }) {
  const items = thunder.items || [];
  const stopper = items.find((i) => i.id === thunder.stopped_by_item_id);
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-base font-semibold text-gray-900">Thunder emails</h4>
        {thunder.stage && <StatusBadge value={thunder.stage} />}
      </div>
      {thunder.stage === "STOPPED" && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <div className="font-medium">
            Thunder stopped{thunder.stop_reason ? ` (${thunder.stop_reason})` : ""}
          </div>
          <div className="mt-0.5 text-xs">
            {!stopper
              ? "The email or opt-out that stopped Thunder is not on record."
              : stopper.kind === "opt_out"
                ? `Email opt-out recorded from ${stopper.source} on ${formatDateTime(stopper.at)}.`
                : `The candidate's email of ${formatDateTime(stopper.at)} (shown below): ${intentDescription(stopper)}.`}
          </div>
        </div>
      )}
      <div className="mt-4 space-y-3 border-t border-gray-100 pt-4">
        {items.map((item) => (
          <ThunderItemRow key={item.id} item={item} isStopper={item.id === thunder.stopped_by_item_id} />
        ))}
      </div>
    </div>
  );
}

function ThunderItemRow({ item, isStopper }) {
  const [expanded, setExpanded] = useState(isStopper);
  if (item.kind === "opt_out") {
    return (
      <div className={`flex gap-3 ${isStopper ? "rounded-lg bg-red-50 p-2" : ""}`}>
        <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-red-400" />
        <div className="flex-1">
          <span className="text-sm font-medium text-gray-800">Email opt-out recorded</span>
          <span className="ml-2 text-xs text-gray-400">{formatDateTime(item.at)}</span>
          <div className="mt-0.5 text-xs text-gray-500">Source: {item.source}</div>
        </div>
      </div>
    );
  }
  const inbound = item.direction === "IN";
  const body = item.body || "";
  const long = body.length > 300;
  return (
    <div className={`flex gap-3 ${isStopper ? "rounded-lg bg-red-50 p-2" : ""}`}>
      <div className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${inbound ? "bg-emerald-400" : "bg-indigo-400"}`} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="text-sm font-medium text-gray-800">
            {inbound ? "Candidate's email" : `Thunder sent${item.step ? ` (step ${item.step})` : ""}`}
          </span>
          <span className="text-xs text-gray-400">{formatDateTime(item.at)}</span>
        </div>
        {item.subject && <div className="mt-0.5 text-xs font-medium text-gray-600">{item.subject}</div>}
        {inbound && (
          <div className={`mt-1 text-xs font-medium ${isStopper ? "text-red-700" : "text-gray-500"}`}>
            {intentDescription(item)}
          </div>
        )}
        {body ? (
          <div className="mt-1 whitespace-pre-wrap break-words text-sm text-gray-700">
            {long && !expanded ? `${body.slice(0, 300)}…` : body}
            {long && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="ml-1 text-xs font-semibold text-blue-600 hover:underline"
              >
                {expanded ? "Show less" : "Show all"}
              </button>
            )}
          </div>
        ) : (
          <div className="mt-1 text-xs text-gray-400">
            {inbound ? "The email had no text." : "Email text not stored (sent before Thunder kept a copy)."}
          </div>
        )}
      </div>
    </div>
  );
}

// S-064/HRMS-0464 -- keys this codebase's own event_data may carry that
// explain a Thunder message; excluded from the generic key:value dump
// below and surfaced instead via the dedicated "Why?" toggle.
const EXPLANATION_KEYS = new Set(["explanation", "prompt_type", "context_snapshot", "explanation_generated_at"]);
const PROMPT_TYPE_LABELS = { conversational_reply: "Conversational Reply" };

function EventRow({ event }) {
  const [showWhy, setShowWhy] = useState(false);
  const label = EVENT_LABELS[event.event_type] || event.event_type;
  const data = event.event_data;
  const hasExplanation = event.event_type === "ai_message_sent" && data && data.explanation;
  const detail =
    data && typeof data === "object"
      ? Object.entries(data)
          .filter(([k, v]) => !EXPLANATION_KEYS.has(k) && v !== null && v !== undefined && v !== "")
          .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
          .join(" · ")
      : "";

  return (
    <div className="flex gap-3">
      <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-indigo-400" />
      <div className="flex-1">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="text-sm font-medium text-gray-800">{label}</span>
          <span className="text-xs text-gray-400">
            {formatDateTime(event.created_at)}
          </span>
          {event.triggered_by && (
            <span className="text-xs text-gray-400">by {event.triggered_by}</span>
          )}
          {hasExplanation && (
            <button
              type="button"
              onClick={() => setShowWhy((v) => !v)}
              className="text-xs font-semibold text-blue-600 hover:underline"
            >
              Why?
            </button>
          )}
        </div>
        {detail && (
          <div className="mt-0.5 text-xs text-gray-500 break-words">{detail}</div>
        )}
        {hasExplanation && showWhy && (
          <div className="mt-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
            <div>Thunder sent this because: {data.explanation.replace(/^Thunder replied to continue the conversation\.\s*/, "")}</div>
            <div className="mt-1 text-gray-500">Type: {PROMPT_TYPE_LABELS[data.prompt_type] || data.prompt_type}</div>
            {data.context_snapshot && (
              <div className="mt-1 text-gray-400">
                At this moment: Profile {data.context_snapshot.completeness_at_time}% complete
                {" | "}State: {data.context_snapshot.state_at_time}
                {" | "}Memory facts: {data.context_snapshot.memory_facts_count}
                {data.context_snapshot.missing_fields_at_time?.length
                  ? ` | Missing: ${data.context_snapshot.missing_fields_at_time.join(", ")}`
                  : ""}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// S-075/HRMS-0475 6A: "Pause for: 24h / 48h / 1 week / Until manually resume".
const PAUSE_DURATION_OPTIONS = [
  { label: "24 hours", ms: 24 * 60 * 60 * 1000 },
  { label: "48 hours", ms: 48 * 60 * 60 * 1000 },
  { label: "1 week", ms: 7 * 24 * 60 * 60 * 1000 },
  { label: "Until I manually resume", ms: null },
];

function PauseThunderModal({ busy, onConfirm, onCancel }) {
  const [selectedMs, setSelectedMs] = useState(PAUSE_DURATION_OPTIONS[0].ms);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-gray-900">Pause Thunder?</h3>
        <p className="mt-1 text-sm text-gray-500">
          Thunder will stop sending follow-ups to this candidate. Ownership stays with the AI recruiter -- no hand-back needed when it resumes.
        </p>
        <div className="mt-4 space-y-2">
          {PAUSE_DURATION_OPTIONS.map((opt) => (
            <label
              key={opt.label}
              className="flex cursor-pointer items-center gap-2 rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              <input
                type="radio"
                name="pause-duration"
                checked={selectedMs === opt.ms}
                onChange={() => setSelectedMs(opt.ms)}
              />
              Resume in: {opt.label}
            </label>
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(selectedMs)}
            disabled={busy}
            className="rounded-xl border border-amber-200 bg-amber-500 px-3 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-60"
          >
            {busy ? "Pausing..." : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ value }) {
  const normalized = String(value || "").toLowerCase();
  let styles = "bg-gray-100 text-gray-700 border-gray-200";
  if (normalized.includes("open") || normalized.includes("awaiting")) {
    styles = "bg-blue-50 text-blue-700 border-blue-200";
  } else if (normalized.includes("completed") || normalized.includes("closed")) {
    styles = "bg-green-50 text-green-700 border-green-200";
  } else if (normalized.includes("escalat")) {
    styles = "bg-red-50 text-red-700 border-red-200";
  }
  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${styles}`}
    >
      {value || "unknown"}
    </span>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <p className="text-sm text-gray-500">{subtitle}</p>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="animate-pulse space-y-3">
        <div className="h-4 w-48 rounded bg-gray-200" />
        <div className="h-3 w-64 rounded bg-gray-100" />
        <div className="h-3 w-56 rounded bg-gray-100" />
      </div>
    </div>
  );
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
