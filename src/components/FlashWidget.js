// Flash -- real internal query widget -- a floating affordance
// available on every internal screen, not a hidden/test-only tool.
// Renamed 2026-08-06 from "Ask Thunder"/AskThunderWidget.js --
// functionally unchanged at rename time, plus the newly added
// finance/AR/tasks intents (see backend flash_service.py). Answers
// come from real DB queries; anything else gets an honest "can't
// answer that yet" straight from the backend, never a fabricated
// answer -- "strict mode."
// 2026-08-07: Added "Report Issue" button for production defect feedback.
import { useRef, useState } from "react";
import { MessageCircleQuestion, Send, X, AlertCircle } from "lucide-react";
import { askFlash } from "../services/api/flash";
import { reportDefect } from "../services/api/defects";
import { toast } from "react-toastify";
import cx from "../utils/cx";
import { NAV_ITEMS } from "../layout/navItems";

// Real module names, not free text -- pulled from the same nav config
// that drives the sidebar, so "Affected Screen" always maps to an
// actual screen instead of whatever a reporter happens to type.
const AFFECTED_SCREEN_OPTIONS = Array.from(
  new Set(Object.values(NAV_ITEMS).map((item) => item.label)),
).sort((a, b) => a.localeCompare(b));

export default function FlashWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportForm, setReportForm] = useState({ description: "", screen: "", screenOther: "", severity: "MEDIUM", blocking: false });
  const [reporting, setReporting] = useState(false);
  const scrollRef = useRef(null);

  // Backlog item, 2026-08-05 (wros_ask_thunder_bugs_and_memory_backlog):
  // pairs up the flat you/flash message list into {question, reply}
  // turns for the backend's history-aware classifier -- the fix for
  // "i ask a question to thunder and move to a different page it
  // looses the history and acts as a new session." Only the recent
  // tail matters (the backend caps further); no need to send everything.
  const recentHistory = (allMessages) => {
    const turns = [];
    for (let i = 0; i < allMessages.length - 1; i++) {
      if (allMessages[i].sender === "you" && allMessages[i + 1].sender === "flash") {
        turns.push({ question: allMessages[i].body, reply: allMessages[i + 1].body });
      }
    }
    return turns.slice(-3);
  };

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || sending) return;

    const history = recentHistory(messages);
    setSending(true);
    setMessages((prev) => [...prev, { sender: "you", body: text }]);
    setDraft("");

    try {
      const res = await askFlash(text, history);
      setMessages((prev) => [...prev, { sender: "flash", body: res.reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: "flash", body: err.message || "Something went wrong -- please try again." },
      ]);
    } finally {
      setSending(false);
      requestAnimationFrame(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      });
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
      toast.error("Please fill in description and affected screen.");
      return;
    }
    setReporting(true);
    try {
      const severity = reportForm.blocking ? "CRITICAL" : reportForm.severity;
      await reportDefect(reportForm.description, screen, severity, reportForm.blocking);
      toast.success("Issue reported! QA team will review it soon.");
      setReportForm({ description: "", screen: "", screenOther: "", severity: "MEDIUM", blocking: false });
      setShowReportModal(false);
    } catch (err) {
      toast.error(err.message || "Failed to report issue.");
    } finally {
      setReporting(false);
    }
  };

  return (
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
              <div className="text-[11px] text-white/60">Sourcing, status, tasks &amp; finance</div>
            </div>
            <div className="flex items-center gap-2">
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
            {messages.length === 0 ? (
              <div className="mt-4 text-center text-xs text-gray-500">
                Try: "find me a Java developer", "what's my BU's margin", or "what's on my plate"
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={cx("flex", m.sender === "you" ? "justify-end" : "justify-start")}>
                  <div
                    className={cx(
                      "max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-xs",
                      m.sender === "you" ? "bg-bx-orange text-white" : "bg-gray-100 text-gray-900",
                    )}
                  >
                    {m.body}
                  </div>
                </div>
              ))
            )}
            {sending ? <div className="text-xs text-gray-400">Flash is checking…</div> : null}
          </div>

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
        className="flex h-12 w-12 items-center justify-center rounded-full bg-bx-orange text-white shadow-xl transition hover:bg-bx-orange-hover"
        aria-label="Ask Flash"
      >
        <MessageCircleQuestion className="h-5 w-5" />
      </button>
    </div>
  );
}
