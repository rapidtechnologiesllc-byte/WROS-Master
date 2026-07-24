// Real internal "Ask Thunder" query widget -- a floating affordance
// available on every internal screen, not a hidden/test-only tool.
// Answers come from real DB queries (candidate sourcing, candidate
// status); anything else gets an honest "can't answer that yet"
// straight from the backend, never a fabricated answer.
import { useRef, useState } from "react";
import { MessageCircleQuestion, Send, X } from "lucide-react";
import { askThunder } from "../services/api/askThunder";
import cx from "../utils/cx";

export default function AskThunderWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || sending) return;

    setSending(true);
    setMessages((prev) => [...prev, { sender: "you", body: text }]);
    setDraft("");

    try {
      const res = await askThunder(text);
      setMessages((prev) => [...prev, { sender: "thunder", body: res.reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: "thunder", body: err.message || "Something went wrong -- please try again." },
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

  return (
    <div className="fixed bottom-6 right-6 z-[9998]">
      {open ? (
        <div className="mb-3 flex h-[420px] w-80 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b bg-bx-navy px-4 py-3">
            <div>
              <div className="text-sm font-bold text-white">Ask Thunder</div>
              <div className="text-[11px] text-white/60">Sourcing &amp; candidate status</div>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white" aria-label="Close">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div ref={scrollRef} className="flex flex-1 flex-col gap-2 overflow-y-auto px-3 py-3">
            {messages.length === 0 ? (
              <div className="mt-4 text-center text-xs text-gray-500">
                Try: "find me a Java developer" or "how is Priya Sharma doing"
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
            {sending ? <div className="text-xs text-gray-400">Thunder is checking…</div> : null}
          </div>

          <div className="flex items-end gap-2 border-t px-3 py-2.5">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Thunder…"
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
        aria-label="Ask Thunder"
      >
        <MessageCircleQuestion className="h-5 w-5" />
      </button>
    </div>
  );
}
