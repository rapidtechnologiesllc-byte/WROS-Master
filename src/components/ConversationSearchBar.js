// S-015/S-016 (HRMS-0415/0416) -- Conversation Search + Filters.
// Standalone, mounted above CandidateSearch.js at the route level rather
// than edited into that already-large, heavily-branched existing screen
// -- lower regression risk, same real placement the spec calls for
// ("top of the recruiter's candidate/conversation list page").
//
// S-016 filter vocabulary is adapted to this codebase's real fields --
// CandidateConversation really has two orthogonal columns, status
// ("open"/"awaiting_candidate"/"closed") and escalation_state, not the
// spec's single fictional Qualifying/Qualified/Escalated/Paused/
// Completed enum. So the panel below exposes real status checkboxes
// plus a separate Escalated toggle, rather than inventing values the
// backend doesn't have.
import { useEffect, useMemo, useRef, useState } from "react";
import { Mail, MessageSquare, Monitor, RotateCcw, Search } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { searchConversations } from "../services/api/conversationSearch";
import cx from "../utils/cx";

const CHANNELS = ["WHATSAPP", "EMAIL", "PORTAL"];
const CHANNEL_ICONS = { WHATSAPP: MessageSquare, EMAIL: Mail, PORTAL: Monitor };
const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;

const STATUS_OPTIONS = [
  { value: "open", label: "Open" },
  { value: "awaiting_candidate", label: "Awaiting Candidate" },
  { value: "closed", label: "Closed" },
];

const LAST_ACTIVITY_OPTIONS = [
  { value: "any", label: "Any time" },
  { value: "24h", label: "Last 24 hours" },
  { value: "48h", label: "Last 48 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "custom", label: "Custom range" },
];

const LAST_ACTIVITY_HOURS = { "24h": 24, "48h": 48, "7d": 24 * 7 };

function isoHoursAgo(hours) {
  const d = new Date(Date.now() - hours * 60 * 60 * 1000);
  return d.toISOString();
}

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
  const [searchParams, setSearchParams] = useSearchParams();

  // BR-02: filters (and the query) hydrate once from the URL on mount so
  // a bookmarked/shared link pre-applies -- read with a lazy initializer,
  // not an effect, so the very first render already reflects the URL.
  const [query, setQuery] = useState(() => searchParams.get("q") || "");
  const [showFilters, setShowFilters] = useState(false);
  const [selectedChannels, setSelectedChannels] = useState(() => {
    const c = searchParams.get("channels");
    return c ? c.split(",").filter(Boolean) : [];
  });
  const [dateFrom, setDateFrom] = useState(() => searchParams.get("date_from") || "");
  const [dateTo, setDateTo] = useState(() => searchParams.get("date_to") || "");
  const [statusFilter, setStatusFilter] = useState(() => searchParams.getAll("status"));
  const [escalatedFilter, setEscalatedFilter] = useState(() => searchParams.get("escalated") || "all"); // all | true | false
  const [profileFilter, setProfileFilter] = useState(() => {
    const v = searchParams.get("has_missing_fields");
    return v === "true" ? "missing" : v === "false" ? "complete" : "all";
  });
  const [lastActivity, setLastActivity] = useState(() => searchParams.get("last_activity") || "any");
  const [customFrom, setCustomFrom] = useState(() => searchParams.get("custom_from") || "");
  const [customTo, setCustomTo] = useState(() => searchParams.get("custom_to") || "");

  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | loading | error | done
  const [inlineError, setInlineError] = useState("");

  const debounceRef = useRef(null);

  const escalated = escalatedFilter === "true" ? true : escalatedFilter === "false" ? false : undefined;
  const hasMissingFields = profileFilter === "missing" ? true : profileFilter === "complete" ? false : undefined;

  const updatedAfter = useMemo(() => {
    if (lastActivity === "any") return undefined;
    if (lastActivity === "custom") return customFrom ? new Date(customFrom).toISOString() : undefined;
    return isoHoursAgo(LAST_ACTIVITY_HOURS[lastActivity]);
  }, [lastActivity, customFrom]);

  const updatedBefore = useMemo(() => {
    if (lastActivity !== "custom" || !customTo) return undefined;
    return new Date(customTo).toISOString();
  }, [lastActivity, customTo]);

  // BR-02: keep the URL in sync with every active filter so the view is
  // always bookmarkable/shareable, without polluting history (replace).
  useEffect(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (selectedChannels.length) params.set("channels", selectedChannels.join(","));
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    statusFilter.forEach((s) => params.append("status", s));
    if (escalatedFilter !== "all") params.set("escalated", escalatedFilter);
    if (profileFilter !== "all") params.set("has_missing_fields", profileFilter === "missing" ? "true" : "false");
    if (lastActivity !== "any") params.set("last_activity", lastActivity);
    if (lastActivity === "custom" && customFrom) params.set("custom_from", customFrom);
    if (lastActivity === "custom" && customTo) params.set("custom_to", customTo);
    setSearchParams(params, { replace: true });
  }, [query, selectedChannels, dateFrom, dateTo, statusFilter, escalatedFilter, profileFilter, lastActivity, customFrom, customTo, setSearchParams]);

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
        status: statusFilter.length ? statusFilter : undefined,
        escalated,
        hasMissingFields,
        updatedAfter,
        updatedBefore,
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

  // BR-03: 300ms debounce for free-text; filter changes re-run immediately
  // (no debounce needed -- these are discrete clicks, not keystrokes).
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
  }, [query, selectedChannels, dateFrom, dateTo, statusFilter, escalatedFilter, profileFilter, lastActivity, customFrom, customTo]);

  const toggleChannel = (channel) => {
    setSelectedChannels((prev) => (prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel]));
  };

  const toggleStatus = (value) => {
    setStatusFilter((prev) => (prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]));
  };

  const clearAllFilters = () => {
    setSelectedChannels([]);
    setDateFrom("");
    setDateTo("");
    setStatusFilter([]);
    setEscalatedFilter("all");
    setProfileFilter("all");
    setLastActivity("any");
    setCustomFrom("");
    setCustomTo("");
  };

  const activeFilterCount =
    (selectedChannels.length ? 1 : 0) +
    (dateFrom || dateTo ? 1 : 0) +
    statusFilter.length +
    (escalatedFilter !== "all" ? 1 : 0) +
    (profileFilter !== "all" ? 1 : 0) +
    (lastActivity !== "any" ? 1 : 0);

  const activeTags = useMemo(() => {
    const tags = [];
    selectedChannels.forEach((c) => tags.push({ key: `channel-${c}`, label: c, onRemove: () => toggleChannel(c) }));
    statusFilter.forEach((s) => {
      const opt = STATUS_OPTIONS.find((o) => o.value === s);
      tags.push({ key: `status-${s}`, label: `Status: ${opt ? opt.label : s}`, onRemove: () => toggleStatus(s) });
    });
    if (escalatedFilter !== "all") {
      tags.push({
        key: "escalated",
        label: escalatedFilter === "true" ? "Escalated" : "Not Escalated",
        onRemove: () => setEscalatedFilter("all"),
      });
    }
    if (profileFilter !== "all") {
      tags.push({
        key: "profile",
        label: profileFilter === "missing" ? "Has missing fields" : "Profile complete",
        onRemove: () => setProfileFilter("all"),
      });
    }
    if (lastActivity !== "any") {
      const opt = LAST_ACTIVITY_OPTIONS.find((o) => o.value === lastActivity);
      tags.push({ key: "activity", label: opt ? opt.label : lastActivity, onRemove: () => setLastActivity("any") });
    }
    if (dateFrom || dateTo) {
      tags.push({ key: "dates", label: "Custom date range", onRemove: () => { setDateFrom(""); setDateTo(""); } });
    }
    return tags;
  }, [selectedChannels, statusFilter, escalatedFilter, profileFilter, lastActivity, dateFrom, dateTo]);

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
          Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
        </button>
      </div>

      {inlineError ? <div className="mt-1 text-xs text-rose-600">{inlineError}</div> : null}

      {activeTags.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {activeTags.map((tag) => (
            <span
              key={tag.key}
              className="flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700"
            >
              {tag.label}
              <button type="button" onClick={tag.onRemove} className="text-gray-400 hover:text-gray-700" aria-label={`Remove ${tag.label} filter`}>
                ✕
              </button>
            </span>
          ))}
          <button type="button" onClick={clearAllFilters} className="text-[11px] font-semibold text-bx-orange hover:underline">
            Clear all filters
          </button>
        </div>
      ) : null}

      {showFilters ? (
        <div className="mt-3 flex flex-col gap-3 border-t pt-3">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase text-gray-400">Channel</div>
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

          <div className="flex flex-wrap items-start gap-6">
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase text-gray-400">Status</div>
              <div className="flex flex-col gap-1">
                {STATUS_OPTIONS.map((opt) => (
                  <label key={opt.value} className="flex items-center gap-1.5 text-xs text-gray-700">
                    <input type="checkbox" checked={statusFilter.includes(opt.value)} onChange={() => toggleStatus(opt.value)} />
                    {opt.label}
                  </label>
                ))}
                <label className="flex items-center gap-1.5 text-xs text-gray-700">
                  <input
                    type="checkbox"
                    checked={escalatedFilter === "true"}
                    onChange={(e) => setEscalatedFilter(e.target.checked ? "true" : "all")}
                  />
                  Escalated
                </label>
              </div>
            </div>

            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase text-gray-400">Profile Status</div>
              <div className="flex flex-col gap-1">
                {[
                  { value: "all", label: "All" },
                  { value: "missing", label: "Has missing fields" },
                  { value: "complete", label: "Profile complete" },
                ].map((opt) => (
                  <label key={opt.value} className="flex items-center gap-1.5 text-xs text-gray-700">
                    <input
                      type="radio"
                      name="profile-status"
                      checked={profileFilter === opt.value}
                      onChange={() => setProfileFilter(opt.value)}
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase text-gray-400">Last Activity</div>
              <select
                value={lastActivity}
                onChange={(e) => setLastActivity(e.target.value)}
                className="rounded-lg border px-2 py-1 text-xs text-gray-700"
              >
                {LAST_ACTIVITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              {lastActivity === "custom" ? (
                <div className="mt-2 flex gap-2">
                  <input type="date" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} className="rounded-lg border px-2 py-1 text-xs" />
                  <input type="date" value={customTo} onChange={(e) => setCustomTo(e.target.value)} className="rounded-lg border px-2 py-1 text-xs" />
                </div>
              ) : null}
            </div>
          </div>
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
