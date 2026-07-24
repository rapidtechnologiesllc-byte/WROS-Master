// S-015/HRMS-0415 -- Conversation Search. Standalone, mounted above
// CandidateSearch.js at the route level rather than edited into that
// already-large, heavily-branched existing screen -- lower regression
// risk, same real placement the spec calls for ("top of the
// recruiter's candidate/conversation list page").
import { useEffect, useMemo, useRef, useState } from "react";
import { Mail, MessageSquare, Monitor, RotateCcw, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { searchConversations } from "../services/api/conversationSearch";
import cx from "../utils/cx";

const CHANNELS = ["WHATSAPP", "EMAIL", "PORTAL"];
const CHANNEL_ICONS = { WHATSAPP: MessageSquare, EMAIL: Mail, PORTAL: Monitor };
const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;

function timeAgo(iso) {
  if (!iso) return "";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function highlightSnippet(snippet, query) {
  if (!query) return snippet;
  const idx = snippet.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return snippet;
  return (
    <>
      {snippet.slice(0, idx)}
      <strong>{snippet.slice(idx, idx + query.length)}</strong>
      {snippet.slice(idx + query.length)}
    </>
  );
}

export default function ConversationSearchBar() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [selectedChannels, setSelectedChannels] = useState([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | loading | error | done
  const [inlineError, setInlineError] = useState("");

  const debounceRef = useRef(null);

  const runSearch = async (targetPage) => {
    if (query.trim().length < MIN_QUERY_LENGTH) {
      setResults([]);
      setStatus("idle");
      return;
    }
    if (dateFrom && dateTo && dateTo < dateFrom) {
      setInlineError("End date must be after start date.");
      return;
    }
    setInlineError("");
    setStatus("loading");
    try {
      const res = await searchConversations({
        q: query.trim(),
        channel: selectedChannels.length === 1 ? selectedChannels[0] : undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        page: targetPage,
      });
      if (targetPage === 1) setResults(res.results);
      else setResults((prev) => [...prev, ...res.results]);
      setHasMore(res.has_more);
      setPage(targetPage);
      setStatus("done");
    } catch (err) {
      setStatus("error");
    }
  };

  // BR-03: 300ms debounce -- fire only after the user stops typing.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim().length < MIN_QUERY_LENGTH) {
      setResults([]);
      setStatus("idle");
      setInlineError(query.trim().length === 1 ? "Enter at least 2 characters to search" : "");
      return;
    }
    debounceRef.current = setTimeout(() => runSearch(1), DEBOUNCE_MS);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, selectedChannels, dateFrom, dateTo]);

  const toggleChannel = (channel) => {
    setSelectedChannels((prev) => (prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel]));
  };

  const handleResultClick = (result) => {
    if (result.candidate_id) {
      navigate(`/candidates/${result.candidate_id}`);
    }
  };

  const showResultsPanel = query.trim().length >= MIN_QUERY_LENGTH;

  return (
    <div className="relative mb-4 rounded-2xl border border-gray-200 bg-white p-3 shadow-sm">
      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search conversations by keyword or candidate name..."
          className="flex-1 text-sm outline-none"
        />
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          className="rounded-lg px-2 py-1 text-xs font-semibold text-gray-500 hover:bg-gray-100"
        >
          Filters
        </button>
      </div>

      {inlineError ? <div className="mt-1 text-xs text-rose-600">{inlineError}</div> : null}

      {showFilters ? (
        <div className="mt-3 flex flex-wrap items-end gap-4 border-t pt-3">
          <div className="flex gap-2">
            {CHANNELS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => toggleChannel(c)}
                className={cx(
                  "rounded-lg border px-2.5 py-1 text-xs font-semibold",
                  selectedChannels.includes(c) ? "border-bx-orange bg-bx-orange/10 text-bx-orange" : "border-gray-200 text-gray-600",
                )}
              >
                {c}
              </button>
            ))}
          </div>
          <label className="text-xs text-gray-600">
            From
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="ml-1 rounded-lg border px-2 py-1 text-xs" />
          </label>
          <label className="text-xs text-gray-600">
            To
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="ml-1 rounded-lg border px-2 py-1 text-xs" />
          </label>
        </div>
      ) : null}

      {showResultsPanel ? (
        <div className="mt-3 max-h-96 overflow-y-auto border-t pt-3">
          {status === "loading" && results.length === 0 ? (
            <div className="py-4 text-center text-sm text-gray-500">Searching…</div>
          ) : status === "error" ? (
            <div className="flex items-center justify-between py-4 text-sm text-rose-600">
              Search failed. Please try again.
              <button onClick={() => runSearch(1)} className="flex items-center gap-1 text-xs font-semibold underline">
                <RotateCcw className="h-3 w-3" /> Retry
              </button>
            </div>
          ) : results.length === 0 && status === "done" ? (
            <div className="py-4 text-center text-sm text-gray-500">No conversations found matching your search.</div>
          ) : (
            <div className="flex flex-col divide-y">
              {results.map((r, i) => {
                const Icon = CHANNEL_ICONS[r.channel] || MessageSquare;
                return (
                  <button
                    key={`${r.conversation_id}-${i}`}
                    onClick={() => handleResultClick(r)}
                    className="flex items-start gap-2.5 py-2.5 text-left hover:bg-gray-50"
                  >
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold">{r.candidate_name}</span>
                        <span className="shrink-0 text-xs text-gray-400">{timeAgo(r.sent_at)}</span>
                      </div>
                      <div className="truncate text-xs text-gray-600">{highlightSnippet(r.message_snippet, query)}</div>
                    </div>
                  </button>
                );
              })}
              {hasMore ? (
                <button onClick={() => runSearch(page + 1)} className="py-2 text-center text-xs font-semibold text-bx-orange hover:underline">
                  Load more results
                </button>
              ) : null}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
