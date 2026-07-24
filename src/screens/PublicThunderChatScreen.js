// Public Thunder Chat -- the real, unauthenticated candidate-facing chat
// widget (careers page / job listing link). No login, no Shell wrapper --
// a genuine external visitor lands here directly. Talks to the same real
// Thunder brain (context-aware LLM replies against real open roles) that
// WhatsApp candidates get; becomes a real Candidate row on first message.
//
// Session model: the candidate_id returned by startPublicChat() is held
// in localStorage so a returning visitor resumes their real conversation
// instead of re-introducing themselves every visit.
import { useEffect, useRef, useState } from "react";
import { Send, Zap } from "lucide-react";
import { Button, Input } from "../components/ui";
import cx from "../utils/cx";
import {
  getPublicChatHistory,
  sendPublicChatMessage,
  startPublicChat,
} from "../services/api/publicChat";

const SESSION_KEY = "public_thunder_chat_candidate_id";

export default function PublicThunderChatScreen() {
  const [candidateId, setCandidateId] = useState(() => localStorage.getItem(SESSION_KEY) || "");
  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({ fullName: "", email: "", phone: "", consent: false });
  const [starting, setStarting] = useState(false);

  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  const jobId = new URLSearchParams(window.location.search).get("job") || null;

  useEffect(() => {
    if (!candidateId) return;
    let cancelled = false;
    setLoadingHistory(true);
    getPublicChatHistory(candidateId)
      .then((res) => {
        if (cancelled) return;
        setMessages(res?.messages || []);
      })
      .catch(() => {
        // Stale/invalid session id -- start over rather than getting stuck.
        if (cancelled) return;
        localStorage.removeItem(SESSION_KEY);
        setCandidateId("");
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const handleStart = async (e) => {
    e.preventDefault();
    if (!form.fullName.trim() || !form.email.trim() || !form.consent) return;

    setStarting(true);
    setError("");
    try {
      const res = await startPublicChat({
        fullName: form.fullName.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        jobId,
        consent: form.consent,
      });
      localStorage.setItem(SESSION_KEY, res.candidate_id);
      setCandidateId(res.candidate_id);
      setMessages([{ sender: "thunder", body: res.message, created_at: res.created_at }]);
    } catch (err) {
      setError(err.message || "Couldn't start the chat. Please try again.");
    } finally {
      setStarting(false);
    }
  };

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || sending) return;

    setSending(true);
    setError("");
    setMessages((prev) => [
      ...prev,
      { sender: "candidate", body: text, created_at: new Date().toISOString(), pending: true },
    ]);
    setDraft("");

    try {
      const res = await sendPublicChatMessage({ candidateId, message: text });
      setMessages((prev) => [
        ...prev.filter((m) => !m.pending),
        { sender: "candidate", body: text, created_at: res.created_at },
        { sender: "thunder", body: res.reply, created_at: res.created_at },
      ]);
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.pending));
      setError(err.message || "Thunder couldn't reply just now. Please try again.");
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="mx-auto flex max-w-xl flex-col gap-4">
        <div className="flex items-center gap-2">
          <div className="rounded-xl bg-bx-orange p-2 text-white">
            <Zap className="h-5 w-5" />
          </div>
          <div>
            <div className="text-lg font-extrabold text-bx-navy">Chat with Thunder</div>
            <div className="text-xs text-gray-500">BlitzenX's AI hiring assistant</div>
          </div>
        </div>

        {error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {!candidateId ? (
          <form
            onSubmit={handleStart}
            className="flex flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm"
          >
            <p className="text-sm text-gray-600">
              Tell Thunder a little about yourself to get started -- it'll answer questions
              about our open roles and see how you match up.
            </p>
            <Input
              label="Full name"
              value={form.fullName}
              onChange={(v) => setForm((f) => ({ ...f, fullName: v }))}
              placeholder="Jane Doe"
            />
            <Input
              label="Email"
              type="email"
              value={form.email}
              onChange={(v) => setForm((f) => ({ ...f, email: v }))}
              placeholder="jane@example.com"
            />
            <Input
              label="Phone (optional)"
              value={form.phone}
              onChange={(v) => setForm((f) => ({ ...f, phone: v }))}
              placeholder="+1 555 000 0000"
            />
            <label className="flex items-start gap-2 text-xs text-gray-600">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={form.consent}
                onChange={(e) => setForm((f) => ({ ...f, consent: e.target.checked }))}
              />
              I agree to be contacted by BlitzenX about job opportunities based on this
              conversation.
            </label>
            <Button
              type="submit"
              disabled={starting || !form.fullName.trim() || !form.email.trim() || !form.consent}
            >
              {starting ? "Starting…" : "Start chatting"}
            </Button>
          </form>
        ) : (
          <div className="flex flex-col rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div
              ref={scrollRef}
              className="flex h-[60vh] flex-col gap-3 overflow-y-auto px-5 py-4"
            >
              {loadingHistory ? (
                <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
              ) : (
                messages.map((m, i) => <ChatBubble key={i} message={m} />)
              )}
              {sending ? (
                <div className="flex justify-start">
                  <div className="max-w-[70%] rounded-2xl rounded-bl-sm bg-gray-100 px-4 py-2 text-sm text-gray-500">
                    Thunder is typing…
                  </div>
                </div>
              ) : null}
            </div>
            <div className="flex items-end gap-2 border-t px-5 py-4">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about a role, or tell Thunder about yourself…"
                rows={1}
                className="flex-1 resize-none rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bx-orange"
              />
              <Button onClick={handleSend} disabled={sending || !draft.trim()}>
                <Send className="h-4 w-4" /> Send
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ChatBubble({ message }) {
  const isCandidate = message.sender === "candidate";
  return (
    <div className={cx("flex flex-col", isCandidate ? "items-end" : "items-start")}>
      <span className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
        {isCandidate ? "You" : "Thunder"}
      </span>
      <div
        className={cx(
          "max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap",
          isCandidate
            ? "rounded-br-sm bg-bx-orange text-white"
            : "rounded-bl-sm bg-gray-100 text-gray-900",
          message.pending ? "opacity-60" : "",
        )}
      >
        {message.body}
      </div>
    </div>
  );
}
