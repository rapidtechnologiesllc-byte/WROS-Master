// Test Thunder -- chat with Thunder as if you were a candidate.
// Real send-governance (R-08 ownership lock, consent, 60s debounce) stays
// live underneath; only the outbound WhatsApp transport is mocked (no
// live WhatsApp Business API is provisioned in this codebase yet).
import { useEffect, useRef, useState } from "react";
import { Zap, RotateCcw, Send } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import {
  sendTestChatMessage,
  getTestChatHistory,
  resetTestChat,
} from "../services/api/thunder";

export default function ThunderChatScreen() {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getTestChatHistory();
      setMessages(res?.messages || []);
    } catch (err) {
      setError(err.message || "Failed to load Thunder chat history.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

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
      const res = await sendTestChatMessage(text);
      setMessages((prev) => [
        ...prev.filter((m) => !m.pending),
        { sender: "candidate", body: res.candidate_message, created_at: res.created_at },
        { sender: "thunder", body: res.thunder_reply, created_at: res.created_at },
      ]);
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.pending));
      setError(err.message || "Thunder failed to reply.");
    } finally {
      setSending(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm("Start a fresh Test Thunder conversation?")) return;
    setError("");
    try {
      await resetTestChat();
      setMessages([]);
    } catch (err) {
      setError(err.message || "Failed to reset.");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Test Thunder"
        subtitle="Chat with Thunder as if you were a candidate. Real governance (ownership lock, consent, duplicate-send debounce) stays active -- only the WhatsApp transport is mocked."
        icon={<Zap className="h-4 w-4" />}
        right={
          <Button variant="secondary" onClick={handleReset}>
            <RotateCcw className="h-4 w-4" /> Reset
          </Button>
        }
        bodyClassName="p-0"
      >
        {error ? (
          <div className="mx-5 mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div
          ref={scrollRef}
          className="flex h-[55vh] flex-col gap-3 overflow-y-auto px-5 py-4"
        >
          {loading ? (
            <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
          ) : messages.length === 0 ? (
            <div className="flex h-full items-center justify-center text-center text-sm text-gray-500">
              No messages yet. Say hi to Thunder below.
            </div>
          ) : (
            messages.map((m, i) => (
              <ChatBubble key={i} message={m} />
            ))
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
            placeholder="Type a message as the test candidate…"
            rows={1}
            className="flex-1 resize-none rounded-xl border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bx-orange"
          />
          <Button onClick={handleSend} disabled={sending || !draft.trim()}>
            <Send className="h-4 w-4" /> Send
          </Button>
        </div>
      </Card>
    </div>
  );
}

function ChatBubble({ message }) {
  const isCandidate = message.sender === "candidate";
  const label = isCandidate ? "You (as candidate)" : message.sender === "hr" ? "HR" : "Thunder";
  return (
    <div className={cx("flex flex-col", isCandidate ? "items-end" : "items-start")}>
      <span className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
        {label}
      </span>
      <div
        className={cx(
          "max-w-[70%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap",
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
