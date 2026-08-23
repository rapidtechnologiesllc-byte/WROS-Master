// S-017/HRMS-0417 -- Candidate Self-Service Web Portal.
//
// Mounted at /candidate/:token entirely OUTSIDE the normal login-gated
// app tree (same precedent as /careers-chat's PublicThunderChatScreen)
// -- a candidate arriving via a WhatsApp/Email link has no internal
// account and must never see the internal login screen. The token in
// the URL path IS the real candidate auth (see
// app.services.candidate_portal_service's module docstring for why
// this replaces the spec's HRMS-P111 magic-link/session-cookie
// design) -- held only in this component's state, never written to
// localStorage under the app's own hrms_token key so it can't collide
// with (or leak into) a real internal-user session on the same device.
//
// Mobile-first (BR-03): single column, large touch targets, built for
// a 375px-wide screen since this is primarily opened via a WhatsApp
// link tap on a phone.
import { useEffect, useRef, useState } from "react";
import { Calendar, MessageSquare, User as UserIcon, Zap, Home as HomeIcon } from "lucide-react";
import cx from "../utils/cx";
import {
  downloadPortalInterviewIcs,
  getPortalHome,
  getPortalInterviews,
  getPortalMessages,
  getPortalProfileFields,
  pollPortalMessages,
  requestPortalReschedule,
  sendPortalReply,
  updatePortalProfile,
} from "../services/api/candidatePortal";

// S-346, 2026-08-06: how often the Messages tab checks for new messages
// arriving on another channel (e.g. a WhatsApp reply) while the portal
// is open. No WebSocket infra in this codebase -- this is the
// documented long-poll fallback, not a placeholder for a future one.
const MESSAGE_POLL_INTERVAL_MS = 8000;

const TABS = [
  { key: "home", label: "Home", icon: HomeIcon },
  { key: "messages", label: "Messages", icon: MessageSquare },
  { key: "profile", label: "Profile", icon: UserIcon },
  { key: "interviews", label: "Interviews", icon: Calendar },
];

export default function CandidatePortalScreen({ token }) {
  const [status, setStatus] = useState("loading"); // loading | expired | ready
  const [tab, setTab] = useState("home");
  const [home, setHome] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getPortalHome(token)
      .then((res) => {
        if (cancelled) return;
        setHome(res);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("expired");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 text-center text-sm text-gray-500">
        Loading your portal…
      </div>
    );
  }

  if (status === "expired") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-gray-50 px-6 text-center">
        <div className="rounded-xl bg-bx-orange p-3 text-white">
          <Zap className="h-6 w-6" />
        </div>
        <h1 className="text-lg font-bold text-bx-navy">This link has expired</h1>
        <p className="max-w-xs text-sm text-gray-600">
          Please ask Thunder for a new link, or reply on WhatsApp/Email and we'll send you one.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <div className="flex items-center gap-2 border-b border-gray-200 bg-white px-4 py-3">
        <div className="rounded-lg bg-bx-orange p-1.5 text-white">
          <Zap className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-extrabold text-bx-navy">Hi {home?.candidate_name}</div>
          <div className="text-xs text-gray-500">Thunder, your talent scout at BlitzenX</div>
        </div>
      </div>

      <div className="mx-auto max-w-xl px-4 py-4">
        {tab === "home" ? <HomeTab home={home} onNavigate={setTab} /> : null}
        {tab === "messages" ? <MessagesTab token={token} conversationId={home?.conversation_id} /> : null}
        {tab === "profile" ? <ProfileTab token={token} onProgress={() => {}} /> : null}
        {tab === "interviews" ? <InterviewsTab token={token} /> : null}
      </div>

      <nav className="fixed inset-x-0 bottom-0 flex border-t border-gray-200 bg-white">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cx(
                "flex min-h-[44px] flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-semibold",
                active ? "text-bx-orange" : "text-gray-400",
              )}
            >
              <Icon className="h-5 w-5" />
              {t.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

function StageBadge({ stage }) {
  if (!stage) return null;
  const colorClass =
    {
      blue: "bg-blue-100 text-blue-700",
      amber: "bg-amber-100 text-amber-700",
      green: "bg-green-100 text-green-700",
    }[stage.color] || "bg-gray-100 text-gray-700";
  return <span className={cx("inline-block rounded-full px-3 py-1 text-xs font-semibold", colorClass)}>{stage.label}</span>;
}

function HomeTab({ home, onNavigate }) {
  if (!home) return null;
  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-2 text-xs font-semibold uppercase text-gray-400">Your Stage</div>
        <StageBadge stage={home.stage} />
      </div>

      {home.pending_actions?.length ? (
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-2 text-xs font-semibold uppercase text-gray-400">Pending Actions</div>
          <ul className="flex flex-col gap-2">
            {home.pending_actions.map((action, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => onNavigate(action.toLowerCase().includes("interview") ? "interviews" : "profile")}
                  className="flex min-h-[44px] w-full items-center rounded-lg bg-gray-50 px-3 py-2 text-left text-sm font-medium text-bx-navy hover:bg-gray-100"
                >
                  {action}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-xs font-semibold uppercase text-gray-400">Recent Messages</div>
          <button type="button" onClick={() => onNavigate("messages")} className="text-xs font-semibold text-bx-orange">
            View all
          </button>
        </div>
        {home.recent_messages?.length ? (
          <div className="flex flex-col gap-2">
            {home.recent_messages.map((m) => (
              <div key={m.id} className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700">
                <span className="mr-1 text-[11px] font-semibold uppercase text-gray-400">
                  {m.sender_type === "CANDIDATE" ? "You" : "Thunder"}
                </span>
                {m.message_body}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-gray-500">No messages yet.</div>
        )}
      </div>
    </div>
  );
}

function MessagesTab({ token, conversationId }) {
  const [messages, setMessages] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  // Ref, not state -- the poll interval reads this on every tick without
  // needing to be re-created each time a new message arrives.
  const lastMessageIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    getPortalMessages(token)
      .then((res) => {
        if (cancelled) return;
        const initial = res.messages || [];
        setMessages(initial);
        if (initial.length) {
          lastMessageIdRef.current = Math.max(...initial.map((m) => Number(m.id) || 0));
        }
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // S-346 real-time fix, 2026-08-06: the backend has always supported
  // this poll endpoint (after_id) -- nothing on this screen ever called
  // it, so a reply arriving on another channel while the tab was open
  // never showed up without a manual reload. Skipped entirely until
  // conversationId is known (no conversation to poll yet).
  useEffect(() => {
    if (!conversationId) return undefined;
    let cancelled = false;

    const poll = () => {
      pollPortalMessages(token, conversationId, lastMessageIdRef.current)
        .then((res) => {
          if (cancelled) return;
          const fresh = res.messages || [];
          if (!fresh.length) return;
          lastMessageIdRef.current = Math.max(lastMessageIdRef.current, ...fresh.map((m) => Number(m.id) || 0));
          setMessages((prev) => {
            const existingIds = new Set((prev || []).map((m) => m.id));
            const toAppend = fresh.filter((m) => !existingIds.has(m.id));
            return toAppend.length ? [...(prev || []), ...toAppend] : prev;
          });
        })
        // Silent on failure -- a missed poll tick isn't worth surfacing
        // an error for; the next tick tries again.
        .catch(() => {});
    };

    const intervalId = setInterval(poll, MESSAGE_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [token, conversationId]);

  const handleSend = async () => {
    const body = draft.trim();
    if (!body || !conversationId || sending) return;
    setSending(true);
    setError("");
    try {
      const res = await sendPortalReply(token, conversationId, body);
      // Real id from the send response, not a fake local one -- 2026-08-06:
      // now that polling exists (see the effect above), a fake string id
      // would never match the real numeric id the next poll tick returns,
      // producing a visible duplicate bubble once that tick lands.
      const sentId = Number(res?.message_id) || 0;
      if (sentId) lastMessageIdRef.current = Math.max(lastMessageIdRef.current, sentId);
      setMessages((prev) => [
        ...(prev || []),
        { id: sentId || `local-${Date.now()}`, sender_type: "CANDIDATE", message_body: body, channel: "PORTAL" },
      ]);
      setDraft("");
    } catch (err) {
      setError(err.message || "Couldn't send your message. Please try again.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-2xl border border-gray-200 bg-white p-3 shadow-sm">
        {messages === null ? (
          <div className="py-6 text-center text-sm text-gray-500">Loading…</div>
        ) : messages.length === 0 ? (
          <div className="py-6 text-center text-sm text-gray-500">No messages yet.</div>
        ) : (
          <div className="flex max-h-[55vh] flex-col gap-2 overflow-y-auto">
            {messages.map((m) => {
              const isMe = m.sender_type === "CANDIDATE";
              return (
                <div key={m.id} className={cx("flex flex-col", isMe ? "items-end" : "items-start")}>
                  <div
                    className={cx(
                      "max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap",
                      isMe ? "rounded-br-sm bg-bx-orange text-white" : "rounded-bl-sm bg-gray-100 text-gray-900",
                    )}
                  >
                    {m.message_body}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

      <div className="flex items-end gap-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value.slice(0, 4000))}
          placeholder="Reply to Thunder..."
          rows={2}
          className="min-h-[44px] flex-1 resize-none rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bx-orange"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!draft.trim() || draft.length > 4000 || sending}
          className="min-h-[44px] rounded-xl bg-bx-orange px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}

const PROFILE_INPUT_TYPE = {
  candidateMobile: "tel",
  candidateDateOfBirth: "date",
  candidateJoiningDate: "date",
  candidateExperience: "text",
};

function ProfileTab({ token }) {
  const [fields, setFields] = useState(null);
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  const load = () => {
    getPortalProfileFields(token)
      .then((res) => setFields(res))
      .catch(() => setFields({ total_missing: 0, missing_fields: [] }));
  };

  useEffect(load, [token]);

  const handleSubmit = async () => {
    const payload = Object.fromEntries(Object.entries(values).filter(([, v]) => String(v || "").trim()));
    if (!Object.keys(payload).length) return;
    setSaving(true);
    setNotice("");
    try {
      const res = await updatePortalProfile(token, payload);
      setFields({ total_missing: res.total_missing, missing_fields: res.missing_fields });
      setValues({});
      setNotice("Saved. Thanks for the update!");
    } catch (err) {
      setNotice(err.message || "Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  if (!fields) {
    return <div className="py-6 text-center text-sm text-gray-500">Loading…</div>;
  }

  const startingMissing = fields.total_missing || 0;
  const completed = startingMissing === 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-1 flex items-center justify-between text-xs font-semibold text-gray-500">
          <span>Profile completeness</span>
          <span>{completed ? "Complete" : `${fields.missing_fields.length} field(s) left`}</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
          <div className="h-full rounded-full bg-bx-orange" style={{ width: completed ? "100%" : `${Math.max(15, 100 - fields.missing_fields.length * 15)}%` }} />
        </div>
      </div>

      {notice ? <div className="rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-700">{notice}</div> : null}

      {completed ? (
        <div className="rounded-2xl border border-gray-200 bg-white p-4 text-sm text-gray-600 shadow-sm">
          Your profile is complete. Thanks!
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {fields.missing_fields.map((f) => (
            <div key={f.field} className="rounded-2xl border border-gray-200 bg-white p-3 shadow-sm">
              <label className="mb-1 block text-xs font-semibold text-gray-600">{f.label}</label>
              <input
                type={PROFILE_INPUT_TYPE[f.field] || "text"}
                value={values[f.field] || ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.field]: e.target.value }))}
                className="min-h-[44px] w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bx-orange"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            className="min-h-[44px] rounded-xl bg-bx-orange px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </div>
  );
}

function InterviewsTab({ token }) {
  const [interviews, setInterviews] = useState(null);
  const [rescheduling, setRescheduling] = useState(null);
  const [note, setNote] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getPortalInterviews(token)
      .then((res) => setInterviews(res.interviews || []))
      .catch(() => setInterviews([]));
  }, [token]);

  const submitReschedule = async (interviewId) => {
    try {
      await requestPortalReschedule(token, interviewId, note);
      setNotice("Your request has been sent. Thunder or your recruiter will follow up.");
      setRescheduling(null);
      setNote("");
    } catch (err) {
      setNotice(err.message || "Failed to send request.");
    }
  };

  if (!interviews) {
    return <div className="py-6 text-center text-sm text-gray-500">Loading…</div>;
  }

  if (!interviews.length) {
    return <div className="rounded-2xl border border-gray-200 bg-white p-4 text-sm text-gray-600 shadow-sm">No upcoming interviews scheduled.</div>;
  }

  return (
    <div className="flex flex-col gap-3">
      {notice ? <div className="rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-700">{notice}</div> : null}
      {interviews.map((i) => (
        <div key={i.id} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="text-sm font-semibold text-bx-navy">
            {i.start_time ? new Date(i.start_time).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "TBD"}
          </div>
          <div className="mt-1 text-xs text-gray-500">{i.format === "video" ? "Video call" : i.format}</div>
          <div className="mt-2 text-xs text-gray-600">{i.prep_tip}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => downloadPortalInterviewIcs(token, i.id).catch(() => setNotice("Could not download the calendar file."))}
              className="min-h-[44px] rounded-lg border border-gray-300 px-3 text-xs font-semibold text-gray-700"
            >
              Add to Calendar
            </button>
            <button
              type="button"
              onClick={() => setRescheduling(rescheduling === i.id ? null : i.id)}
              className="min-h-[44px] rounded-lg border border-gray-300 px-3 text-xs font-semibold text-gray-700"
            >
              Request a different time
            </button>
          </div>
          {rescheduling === i.id ? (
            <div className="mt-3 flex flex-col gap-2">
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What time works better for you?"
                rows={2}
                className="resize-none rounded-lg border px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => submitReschedule(i.id)}
                className="min-h-[44px] rounded-xl bg-bx-orange px-4 py-2 text-sm font-semibold text-white"
              >
                Submit Request
              </button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
