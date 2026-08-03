// S-005/S-006 -- Unified Conversation Timeline / Messages tab.
// S-001/S-007/S-008 -- AI agent assignment + missing-fields preview, surfaced here
// since there was previously no UI anywhere for /ai-agent/* endpoints.
// S-009/S-010 -- manual message send + ownership take-over/hand-back.
import { useCallback, useEffect, useState } from "react";
import {
  getConversationThread,
  getMissingFields,
  assignAgent,
  sendManualMessage,
  takeOverConversation,
  handBackConversation,
  pollForReply,
} from "../../services/api/aiAgent";
import { toast } from "react-toastify";
import ThunderMemorySection from "../../components/ThunderMemorySection";
import ThunderActivitySection from "../../components/activity/ThunderActivitySection";

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
  const [missingLoading, setMissingLoading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [polling, setPolling] = useState(false);

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
      setMissingLoading(true);
      const res = await getMissingFields(candidateId);
      setMissingFields(res);
    } catch (err) {
      console.error("Failed to fetch missing fields", err);
      toast.error("Failed to load missing fields");
    } finally {
      setMissingLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchMissingFields();
  }, [fetchMissingFields]);

  const handleAssignAgent = async () => {
    if (!candidateId) return;
    try {
      setAssigning(true);
      await assignAgent(candidateId);
      toast.success("AI recruiter assigned");
      await fetchThread();
      await fetchMissingFields();
    } catch (err) {
      console.error("Failed to assign AI agent", err);
      toast.error(err?.message || "Failed to assign AI agent");
    } finally {
      setAssigning(false);
    }
  };

  const handleCheckReply = async () => {
    if (!candidateId) return;
    try {
      setPolling(true);
      const res = await pollForReply(candidateId);
      if (res?.status === "no_reply_found") {
        toast.info("No new reply found yet.");
      } else if (res?.updated_fields?.length) {
        toast.success(`Updated: ${res.updated_fields.join(", ")}`);
      } else {
        toast.success("Reply processed.");
      }
      await fetchThread();
      await fetchMissingFields();
    } catch (err) {
      console.error("Failed to check for reply", err);
      toast.error(err?.message || "Failed to check for reply");
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

  return (
    <div className="space-y-6">
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

      {candidateId ? <ThunderMemorySection candidateId={candidateId} /> : null}
      {candidateId ? <ThunderActivitySection candidateId={candidateId} /> : null}

      {!conversations.length ? (
        <EmptyState
          onAssign={handleAssignAgent}
          assigning={assigning}
          missingLoading={missingLoading}
        />
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
            <button
              type="button"
              onClick={handleAssignAgent}
              disabled={assigning}
              className="inline-flex items-center rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-60"
            >
              {assigning ? "Reassigning..." : "Reassign AI Recruiter"}
            </button>
          </div>
          {conversations.map((conv) => (
            <ConversationCard
              key={conv.conversation_id}
              conversation={conv}
              onChanged={fetchThread}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ConversationCard({ conversation, onChanged }) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [ownershipBusy, setOwnershipBusy] = useState(false);

  const events = [...(conversation.events || [])].sort(
    (a, b) => new Date(a?.created_at || 0) - new Date(b?.created_at || 0),
  );

  const isHumanOwned = conversation.owner_type === "hr_user";

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
      toast.error(err?.message || "Failed to send message");
    } finally {
      setSending(false);
    }
  };

  const handleTakeOver = async () => {
    try {
      setOwnershipBusy(true);
      await takeOverConversation(conversation.conversation_id);
      toast.success("Conversation taken over");
      await onChanged?.();
    } catch (err) {
      console.error("Failed to take over conversation", err);
      toast.error(err?.message || "Failed to take over conversation");
    } finally {
      setOwnershipBusy(false);
    }
  };

  const handleHandBack = async () => {
    try {
      setOwnershipBusy(true);
      await handBackConversation(conversation.conversation_id);
      toast.success("Handed back to AI recruiter");
      await onChanged?.();
    } catch (err) {
      console.error("Failed to hand back conversation", err);
      toast.error(err?.message || "Failed to hand back conversation");
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
      </div>

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

function EventRow({ event }) {
  const label = EVENT_LABELS[event.event_type] || event.event_type;
  const data = event.event_data;
  const detail =
    data && typeof data === "object"
      ? Object.entries(data)
          .filter(([, v]) => v !== null && v !== undefined && v !== "")
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
        </div>
        {detail && (
          <div className="mt-0.5 text-xs text-gray-500 break-words">{detail}</div>
        )}
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

function EmptyState({ onAssign, assigning, missingLoading }) {
  return (
    <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white text-xl shadow-sm">
        💬
      </div>
      <h3 className="text-sm font-semibold text-gray-900">
        No AI recruiter conversation yet
      </h3>
      <p className="mt-1 text-sm text-gray-500">
        Assign the AI recruiter to start collecting missing information from
        this candidate automatically.
      </p>
      <button
        type="button"
        onClick={onAssign}
        disabled={assigning || missingLoading}
        className="mt-4 inline-flex items-center rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-60"
      >
        {assigning ? "Assigning..." : "Assign AI Recruiter"}
      </button>
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
