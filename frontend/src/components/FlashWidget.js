// Flash -- real internal query widget -- a floating affordance
// available on every internal screen, not a hidden/test-only tool.
// Renamed 2026-08-06 from "Ask Thunder"/AskThunderWidget.js --
// functionally unchanged at rename time, plus the newly added
// finance/AR/tasks intents (see backend flash_service.py). Answers
// come from real DB queries; anything else gets an honest "can't
// answer that yet" straight from the backend, never a fabricated
// answer -- "strict mode."
// 2026-08-07: Added "Report Issue" button for production defect feedback.
// 2026-10-15: the conversation lives on the server (one per user): loaded on mount, polled while
// the bubble is closed (unread badge), opened on a record by a deep link (?flash=kind:ref, e.g.
// a Core certification decision from its task), with chips for the decisions waiting.
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { MessageCircleQuestion, Send, X, AlertCircle, CheckCircle, RotateCcw } from "lucide-react";
import {
  FLASH_WORKFLOW_DONE_EVENT,
  askFlash,
  getFlashConversation,
  markFlashRead,
  openFlashWorkflow,
  resetFlashConversation,
} from "../services/api/flash";
import { reportDefect } from "../services/api/defects";
import cx from "../utils/cx";
import { NAV_ITEMS } from "../layout/navItems";
import ScreenErrorDisplay from "./ScreenErrorDisplay";

// Real module names, not free text -- pulled from the same nav config
// that drives the sidebar, so "Affected Screen" always maps to an
// actual screen instead of whatever a reporter happens to type.
const AFFECTED_SCREEN_OPTIONS = Array.from(
  new Set(Object.values(NAV_ITEMS).map((item) => item.label)),
).sort((a, b) => a.localeCompare(b));

// The query parameter of a deep link into Flash: ?flash=<kind>:<ref>
const FLASH_PARAM = "flash";

const newestId = (list, current) =>
  list.reduce((max, m) => (typeof m.id === "number" && m.id > (max ?? 0) ? m.id : max), current);

export default function FlashWidget() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [unread, setUnread] = useState(0);
  const [pollSeconds, setPollSeconds] = useState(null);
  const [activeWorkflow, setActiveWorkflow] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportForm, setReportForm] = useState({ description: "", screen: "", screenOther: "", severity: "MEDIUM", blocking: false });
  const [reporting, setReporting] = useState(false);
  const [screenError, setScreenError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const scrollRef = useRef(null);
  const lastIdRef = useRef(null);
  const workflowRef = useRef(null);
  const handledLinkRef = useRef(null);

  const scrollToEnd = () =>
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    });

  const addMessages = useCallback((incoming) => {
    if (!incoming || incoming.length === 0) return;
    setMessages((prev) => {
      const seen = new Set(prev.map((m) => m.id));
      const fresh = incoming.filter((m) => !seen.has(m.id));
      return fresh.length ? [...prev, ...fresh] : prev;
    });
    lastIdRef.current = newestId(incoming, lastIdRef.current);
    scrollToEnd();
  }, []);

  // A local message (e.g. a failed request) shown in the bubble, never stored
  const addLocalNote = useCallback((body) => {
    setMessages((prev) => [...prev, { id: `local-${Date.now()}-${prev.length}`, role: "flash", body }]);
    scrollToEnd();
  }, []);

  const trackWorkflow = useCallback((next) => {
    const previous = workflowRef.current;
    workflowRef.current = next || null;
    setActiveWorkflow(next || null);
    if (previous && !next) {
      window.dispatchEvent(new CustomEvent(FLASH_WORKFLOW_DONE_EVENT, { detail: { kind: previous } }));
    }
  }, []);

  const applyConversation = useCallback(
    (data) => {
      addMessages(data.messages);
      setDecisions(data.pending_decisions || []);
      setUnread(data.unread || 0);
      setPollSeconds(data.poll_seconds || null);
      trackWorkflow(data.active_workflow);
    },
    [addMessages, trackWorkflow],
  );

  const refresh = useCallback(async () => {
    try {
      applyConversation(await getFlashConversation(lastIdRef.current));
    } catch (err) {
      setScreenError(`Flash could not load your conversation: ${err.message}`);
    }
  }, [applyConversation]);

  // The conversation is kept on the server: load it on any screen, after any reload
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Opening the bubble shows the latest (polling stops while it is open)
  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  // While the bubble is closed, check for news (interval served by the backend)
  useEffect(() => {
    if (open || !pollSeconds) return undefined;
    const timer = setInterval(refresh, pollSeconds * 1000);
    return () => clearInterval(timer);
  }, [open, pollSeconds, refresh]);

  // An open bubble has shown everything up to the newest message
  useEffect(() => {
    if (!open || unread === 0 || lastIdRef.current == null) return;
    markFlashRead(lastIdRef.current)
      .then(() => setUnread(0))
      .catch((err) => setScreenError(`Flash could not mark messages read: ${err.message}`));
  }, [open, unread]);

  const startWorkflow = useCallback(
    async (kind, ref) => {
      setOpen(true);
      setSending(true);
      try {
        const res = await openFlashWorkflow(kind, ref);
        addMessages(res.messages);
        trackWorkflow(res.active_workflow);
        await refresh();
      } catch (err) {
        addLocalNote(err.message || "Flash could not open that discussion.");
      } finally {
        setSending(false);
      }
    },
    [addMessages, addLocalNote, refresh, trackWorkflow],
  );

  // Deep link: ?flash=<kind>:<ref> opens the bubble on that discussion, on any screen
  const flashLink = searchParams.get(FLASH_PARAM);
  useEffect(() => {
    if (!flashLink || handledLinkRef.current === flashLink) return;
    handledLinkRef.current = flashLink;
    const next = new URLSearchParams(searchParams);
    next.delete(FLASH_PARAM);
    setSearchParams(next, { replace: true });
    const split = flashLink.indexOf(":");
    const kind = split > 0 ? flashLink.slice(0, split) : "";
    const ref = split > 0 ? flashLink.slice(split + 1) : "";
    if (!kind || !ref) {
      setOpen(true);
      addLocalNote("That Flash link is incomplete, so there is nothing to open.");
      return;
    }
    startWorkflow(kind, ref);
  }, [flashLink, searchParams, setSearchParams, startWorkflow, addLocalNote]);

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setPendingQuestion(text);
    setDraft("");
    scrollToEnd();
    try {
      const res = await askFlash(text);
      addMessages(res.messages);
      trackWorkflow(res.active_workflow);
    } catch (err) {
      addLocalNote(err.message || "Something went wrong -- please try again.");
    } finally {
      setPendingQuestion(null);
      setSending(false);
    }
  };

  const handleDecision = (decision) => {
    if (decision.workflow) {
      startWorkflow(decision.kind, decision.ref);
    } else if (decision.link) {
      setOpen(false);
      navigate(decision.link);
    }
  };

  const handleReset = async () => {
    if (sending) return;
    try {
      await resetFlashConversation();
      setMessages([]);
      lastIdRef.current = null;
      trackWorkflow(null);
      await refresh();
    } catch (err) {
      setScreenError(`Flash could not start a new conversation: ${err.message}`);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleReportDefect = async () => {
    const screen = reportForm.screen === "Other" ? reportForm.screenOther.trim() : reportForm.screen;
    if (!reportForm.description.trim() || !screen) {
      setScreenError("Please fill in description and affected screen.");
      return;
    }
    setReporting(true);
    try {
      const severity = reportForm.blocking ? "CRITICAL" : reportForm.severity;
      await reportDefect(reportForm.description, screen, severity, reportForm.blocking);
      setActionSuccess("Issue reported! QA team will review it soon.");
      setReportForm({ description: "", screen: "", screenOther: "", severity: "MEDIUM", blocking: false });
      setShowReportModal(false);
    } catch (err) {
      setScreenError(err.message || "Failed to report issue.");
    } finally {
      setReporting(false);
    }
  };

  return (
    <>
      <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
      {actionSuccess && (
        <div className="fixed bottom-24 left-6 z-[9998] p-4 bg-green-50 border border-green-200 rounded-lg flex items-start justify-between max-w-xs">
          <div className="flex items-start gap-3">
            <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-green-800">{actionSuccess}</div>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-green-600 hover:text-green-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      <div className="fixed bottom-6 left-6 z-[9998]">
      {showReportModal ? (
        <div className="fixed inset-0 z-[9999] flex items-end justify-center bg-black/30 sm:items-center">
          <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
            <div className="border-b px-4 py-3">
              <div className="text-sm font-bold">Report an Issue</div>
            </div>
            <div className="space-y-3 px-4 py-3">
              <div>
                <label className="block text-xs font-semibold text-gray-900 mb-1">Affected Screen *</label>
                <select
                  value={reportForm.screen}
                  onChange={(e) => setReportForm({ ...reportForm, screen: e.target.value })}
                  className="w-full rounded-lg border px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-bx-orange"
                >
                  <option value="" disabled>Select the screen with the issue…</option>
                  {AFFECTED_SCREEN_OPTIONS.map((label) => (
                    <option key={label} value={label}>{label}</option>
                  ))}
                  <option value="Other">Other (not listed)</option>
                </select>
                {reportForm.screen === "Other" ? (
                  <input
                    type="text"
                    value={reportForm.screenOther}
                    onChange={(e) => setReportForm({ ...reportForm, screenOther: e.target.value })}
                    placeholder="Describe which screen"
                    className="mt-2 w-full rounded-lg border px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-bx-orange"
                  />
                ) : null}
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-900 mb-1">Description *</label>
                <textarea
                  value={reportForm.description}
                  onChange={(e) => setReportForm({ ...reportForm, description: e.target.value })}
                  placeholder="What went wrong? Be as specific as possible."
                  rows={4}
                  className="w-full rounded-lg border px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-bx-orange resize-none"
                />
              </div>
              <div className="rounded-lg border border-red-200 bg-red-50 p-2.5">
                <label className="flex items-start gap-2 text-xs font-semibold text-red-800">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={reportForm.blocking}
                    onChange={(e) => setReportForm({ ...reportForm, blocking: e.target.checked })}
                  />
                  This is blocking a production function (nobody can complete this workflow right now)
                </label>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-900 mb-1">Severity</label>
                <select
                  value={reportForm.blocking ? "CRITICAL" : reportForm.severity}
                  onChange={(e) => setReportForm({ ...reportForm, severity: e.target.value })}
                  disabled={reportForm.blocking}
                  className="w-full rounded-lg border px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-bx-orange disabled:bg-gray-100 disabled:text-gray-500"
                >
                  <option>LOW</option>
                  <option>MEDIUM</option>
                  <option>HIGH</option>
                  <option>CRITICAL</option>
                </select>
                {reportForm.blocking ? (
                  <div className="mt-1 text-[11px] text-gray-500">Auto-set to CRITICAL because this is blocking production.</div>
                ) : null}
              </div>
            </div>
            <div className="flex gap-2 border-t px-4 py-3">
              <button
                onClick={handleReportDefect}
                disabled={reporting}
                className="flex-1 rounded-lg bg-bx-orange py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                {reporting ? "Sending…" : "Report Issue"}
              </button>
              <button
                onClick={() => setShowReportModal(false)}
                disabled={reporting}
                className="flex-1 rounded-lg border py-2 text-xs font-semibold text-gray-900 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {open ? (
        <div className="mb-3 flex h-[420px] w-80 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b bg-bx-navy px-4 py-3">
            <div>
              <div className="text-sm font-bold text-white">Ask Flash</div>
              <div className="text-[11px] text-white/60">
                {activeWorkflow ? "In a discussion: type cancel to leave it" : "Sourcing, status, tasks & finance"}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleReset}
                className="rounded p-1 text-white/70 hover:bg-white/10 hover:text-white"
                title="Start a new conversation"
                aria-label="Start a new conversation"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
              <button
                onClick={() => setShowReportModal(true)}
                className="rounded p-1 text-white/70 hover:bg-white/10 hover:text-white"
                title="Report an issue"
              >
                <AlertCircle className="h-4 w-4" />
              </button>
              <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white" aria-label="Close">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div ref={scrollRef} className="flex flex-1 flex-col gap-2 overflow-y-auto px-3 py-3">
            {messages.length === 0 && !pendingQuestion ? (
              <div className="mt-4 text-center text-xs text-gray-500">
                Try: "find me a Java developer", "what's my BU's margin", or "what's on my plate"
              </div>
            ) : (
              messages.map((m) => (
                <div key={m.id} className={cx("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                  <div
                    className={cx(
                      "max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-xs",
                      m.role === "user" && "bg-bx-orange text-white",
                      m.role === "flash" && "bg-gray-100 text-gray-900",
                      m.role === "event" && "border border-blue-100 bg-blue-50 text-blue-900",
                    )}
                  >
                    {m.body}
                  </div>
                </div>
              ))
            )}
            {pendingQuestion ? (
              <div className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-xl bg-bx-orange px-3 py-2 text-xs text-white opacity-70">
                  {pendingQuestion}
                </div>
              </div>
            ) : null}
            {sending ? <div className="text-xs text-gray-400">Flash is checking…</div> : null}
          </div>

          {decisions.length > 0 ? (
            <div className="border-t bg-amber-50 px-3 py-2">
              <div className="text-[11px] font-semibold text-amber-900">
                {decisions.length === 1 ? "1 decision is" : `${decisions.length} decisions are`} waiting for you
              </div>
              <div className="mt-1 flex max-h-20 flex-wrap gap-1 overflow-y-auto">
                {decisions.map((d) => (
                  <button
                    key={`${d.kind}:${d.ref}`}
                    onClick={() => handleDecision(d)}
                    disabled={sending}
                    className="rounded-full border border-amber-300 bg-white px-2 py-0.5 text-left text-[11px] text-amber-900 hover:bg-amber-100 disabled:opacity-50"
                  >
                    {d.text}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex items-end gap-2 border-t px-3 py-2.5">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Flash…"
              rows={1}
              className="flex-1 resize-none rounded-lg border px-2.5 py-1.5 text-xs outline-none focus:ring-2 focus:ring-bx-orange"
            />
            <button
              onClick={handleSend}
              disabled={sending || !draft.trim()}
              className="rounded-lg bg-bx-orange p-2 text-white disabled:opacity-50"
              aria-label="Send"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ) : null}

      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex h-12 w-12 items-center justify-center rounded-full bg-bx-orange text-white shadow-xl transition hover:bg-bx-orange-hover"
        aria-label={unread > 0 ? `Ask Flash (${unread} unread)` : "Ask Flash"}
      >
        <MessageCircleQuestion className="h-5 w-5" />
        {!open && unread > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </button>
      </div>
    </>
  );
}
