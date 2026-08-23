import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Briefcase,
  CalendarCheck,
  CheckCircle2,
  Clock,
  FileText,
  History,
  Loader2,
  RefreshCw,
  Search,
  User,
  XCircle,
} from "lucide-react";
import {
  getCandidateHistory,
  getLatestCandidateHistory,
  HISTORY_EVENT_TYPES,
  HISTORY_EVENT_TYPE_OPTIONS,
} from "../../services/api/candidateHistory";

const getEventIcon = (eventType) => {
  switch (eventType) {
    case HISTORY_EVENT_TYPES.APPLIED:
      return Briefcase;

    case HISTORY_EVENT_TYPES.INTERVIEW_SCHEDULED:
    case HISTORY_EVENT_TYPES.INTERVIEW_COMPLETED:
      return CalendarCheck;

    case HISTORY_EVENT_TYPES.OFFER_RELEASED:
    case HISTORY_EVENT_TYPES.OFFER_ACCEPTED:
    case HISTORY_EVENT_TYPES.OFFER_REJECTED:
      return FileText;

    case HISTORY_EVENT_TYPES.ONBOARDED:
    case HISTORY_EVENT_TYPES.PRE_ONBOARDING:
      return CheckCircle2;

    case HISTORY_EVENT_TYPES.REJECTED:
      return XCircle;

    default:
      return History;
  }
};

const formatDateTime = (value) => {
  if (!value) return "-";

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "-";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsedDate);
};

const getEventBadgeClass = (eventType) => {
  switch (eventType) {
    case HISTORY_EVENT_TYPES.APPLIED:
      return "bg-blue-50 text-blue-700 border-blue-100";

    case HISTORY_EVENT_TYPES.INTERVIEW_SCHEDULED:
      return "bg-purple-50 text-purple-700 border-purple-100";

    case HISTORY_EVENT_TYPES.INTERVIEW_COMPLETED:
      return "bg-indigo-50 text-indigo-700 border-indigo-100";

    case HISTORY_EVENT_TYPES.OFFER_RELEASED:
      return "bg-amber-50 text-amber-700 border-amber-100";

    case HISTORY_EVENT_TYPES.OFFER_ACCEPTED:
    case HISTORY_EVENT_TYPES.ONBOARDED:
      return "bg-green-50 text-green-700 border-green-100";

    case HISTORY_EVENT_TYPES.OFFER_REJECTED:
    case HISTORY_EVENT_TYPES.REJECTED:
      return "bg-red-50 text-red-700 border-red-100";

    case HISTORY_EVENT_TYPES.PRE_ONBOARDING:
      return "bg-teal-50 text-teal-700 border-teal-100";

    default:
      return "bg-gray-50 text-gray-700 border-gray-100";
  }
};

export default function HistoryTab({ candidateId }) {
  const [historyData, setHistoryData] = useState({
    candidateId: "",
    total: 0,
    events: [],
  });
  const [selectedEventType, setSelectedEventType] = useState("");
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [latestEvent, setLatestEvent] = useState(null);

  const fetchHistory = useCallback(async () => {
    if (!candidateId) return;

    try {
      setLoading(true);
      setErrorMessage("");

      const data = await getCandidateHistory(candidateId, {
        eventType: selectedEventType,
        skip: 0,
        limit: 50,
      });

      setHistoryData(data);
    } catch (err) {
      console.error("Failed to fetch candidate history", err);
      setErrorMessage(err?.message || "Failed to load candidate history.");
    } finally {
      setLoading(false);
    }
  }, [candidateId, selectedEventType]);

  // S-070 -- convenience "latest change" card, independent of the
  // event-type filter above so it always reflects the single most
  // recent event regardless of what the timeline below is filtered to.
  const fetchLatestEvent = useCallback(async () => {
    if (!candidateId) return;
    try {
      const data = await getLatestCandidateHistory(candidateId, 1);
      setLatestEvent(data?.events?.[0] || null);
    } catch (err) {
      console.error("Failed to fetch latest candidate history entry", err);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchHistory();
  }, [candidateId, selectedEventType]);

  useEffect(() => {
    fetchLatestEvent();
  }, [candidateId, fetchLatestEvent]);

  const filteredEvents = useMemo(() => {
    const events = Array.isArray(historyData?.events) ? historyData.events : [];

    const keyword = searchText.trim().toLowerCase();

    if (!keyword) return events;

    return events.filter((event) => {
      const searchableText = [
        event?.event_type,
        event?.note,
        event?.performed_by_name,
        event?.job_id,
        event?.interview_id,
        event?.offer_letter_id,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return searchableText.includes(keyword);
    });
  }, [historyData?.events, searchText]);

  if (!candidateId) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-6 text-sm text-gray-500">
        Candidate ID is missing. History cannot be loaded.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gray-100 text-gray-700">
                <History size={18} />
              </div>

              <div>
                <h3 className="text-base font-semibold text-gray-900">
                  Candidate History
                </h3>
                <p className="mt-0.5 text-sm text-gray-500">
                  Complete timeline of candidate lifecycle events.
                </p>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              fetchHistory();
              fetchLatestEvent();
            }}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <RefreshCw size={16} />
            )}
            Refresh
          </button>
        </div>

        <div className="mt-5 grid gap-3 lg:grid-cols-[260px_1fr_auto] lg:items-center">
          <select
            value={selectedEventType}
            onChange={(e) => setSelectedEventType(e.target.value)}
            className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-700 outline-none transition focus:border-gray-500"
          >
            <option value="">All event types</option>
            {HISTORY_EVENT_TYPE_OPTIONS.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>

          <div className="relative">
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search by note, user, job, interview..."
              className="w-full rounded-xl border border-gray-300 bg-white py-2.5 pl-9 pr-3 text-sm text-gray-700 outline-none transition focus:border-gray-500"
            />
          </div>

          <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-600">
            Total:{" "}
            <span className="font-semibold text-gray-900">
              {historyData?.total ?? filteredEvents.length}
            </span>
          </div>
        </div>
      </div>

      {latestEvent && (
        <div className="rounded-2xl border border-blue-100 bg-blue-50 px-5 py-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {(() => {
                const LatestIcon = getEventIcon(latestEvent.event_type);
                return <LatestIcon size={15} className="text-blue-700" />;
              })()}
              <span className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                Latest Update
              </span>
              <span
                className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${getEventBadgeClass(
                  latestEvent.event_type,
                )}`}
              >
                {latestEvent.event_type || "History Event"}
              </span>
            </div>
            <span className="text-xs text-blue-600">
              {formatDateTime(latestEvent.event_at || latestEvent.created_at)}
            </span>
          </div>
          {latestEvent.performed_by_name && (
            <p className="mt-2 text-xs text-gray-600">
              By {latestEvent.performed_by_name}
            </p>
          )}
          {latestEvent.note && (
            <p className="mt-1 text-sm text-gray-700">{latestEvent.note}</p>
          )}
        </div>
      )}

      {errorMessage && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
          {errorMessage}
        </div>
      )}

      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-14 text-sm text-gray-500">
            <Loader2 size={18} className="animate-spin" />
            Loading candidate history...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="py-14 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400">
              <History size={24} />
            </div>
            <p className="mt-4 text-sm font-semibold text-gray-800">
              No history found
            </p>
            <p className="mt-1 text-sm text-gray-500">
              Candidate timeline events will appear here once actions are
              recorded.
            </p>
          </div>
        ) : (
          <div className="relative">
            <div className="absolute left-5 top-1 h-[calc(100%-8px)] w-px bg-gray-200" />

            <div className="space-y-5">
              {filteredEvents.map((event, index) => {
                const Icon = getEventIcon(event?.event_type);
                const eventKey =
                  event?.id ||
                  `${event?.event_type || "event"}-${event?.event_at || index}`;

                return (
                  <div key={eventKey} className="relative flex gap-4">
                    <div className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-gray-200 bg-white shadow-sm">
                      <Icon size={17} className="text-gray-700" />
                    </div>

                    <div className="min-w-0 flex-1 rounded-2xl border border-gray-100 bg-gray-50 p-4 transition hover:border-gray-200 hover:bg-white">
                      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${getEventBadgeClass(
                                event?.event_type,
                              )}`}
                            >
                              {event?.event_type || "History Event"}
                            </span>

                            {event?.performed_by_name && (
                              <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                                <User size={13} />
                                {event.performed_by_name}
                              </span>
                            )}
                          </div>

                          {event?.note ? (
                            <p className="mt-3 whitespace-pre-line text-sm leading-6 text-gray-700">
                              {event.note}
                            </p>
                          ) : (
                            <p className="mt-3 text-sm leading-6 text-gray-400">
                              No note added for this event.
                            </p>
                          )}
                        </div>

                        <div className="flex shrink-0 items-center gap-1 text-xs text-gray-500">
                          <Clock size={13} />
                          {formatDateTime(event?.event_at || event?.created_at)}
                        </div>
                      </div>

                      {(event?.job_id ||
                        event?.interview_id ||
                        event?.offer_letter_id) && (
                        <div className="mt-4 flex flex-wrap gap-2 text-xs text-gray-500">
                          {event?.offer_letter_id && (
                            <span className="rounded-lg border border-gray-200 bg-white px-2.5 py-1">
                              Offer ID: {event.offer_letter_id}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
