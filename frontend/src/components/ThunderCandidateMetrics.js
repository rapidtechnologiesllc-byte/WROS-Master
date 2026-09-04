import { useEffect, useState } from "react";
import { Zap, Clock, MessageSquare, CheckCircle2 } from "lucide-react";
import { toast } from "react-toastify";
import { getCandidateMemory, pauseThunder, resumeThunder } from "../services/api/aiAgent";

function timeAgo(iso) {
  if (!iso) return "—";
  const hours = Math.round((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function formatCountdown(iso) {
  if (!iso) return "—";
  const nextTime = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = nextTime - now;

  if (diffMs < 0) return "overdue";

  const hours = Math.round(diffMs / (1000 * 60 * 60));
  const minutes = Math.round((diffMs % (1000 * 60 * 60)) / (1000 * 60));

  if (hours < 1) return `${minutes}m`;
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days}d`;
}

export default function ThunderCandidateMetrics({ candidateId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pauseLoading, setPauseLoading] = useState(false);
  const [showPauseModal, setShowPauseModal] = useState(false);

  useEffect(() => {
    if (!candidateId) return;

    const fetch = async () => {
      setLoading(true);
      try {
        const res = await getCandidateMemory(candidateId).catch(e => { throw e; });
        setData(res);
      } catch (err) {
        console.error("Failed to load Thunder metrics", err);
      } finally {
        setLoading(false);
      }
    };

    fetch();
  }, [candidateId]);

  const handlePause = async (durationMs) => {
    try {
      setPauseLoading(true);
      if (!data?.conversation_id) {
        toast.error("Cannot pause: conversation ID not found");
        return;
      }
      const resumeAt = durationMs ? new Date(Date.now() + durationMs).toISOString() : null;
      await pauseThunder(data.conversation_id, resumeAt).catch(e => { throw e; });
      toast.success("Thunder paused successfully");
      setShowPauseModal(false);
      // Refresh data
      const res = await getCandidateMemory(candidateId).catch(e => { throw e; });
      setData(res);
    } catch (err) {
      console.error("Failed to pause Thunder", err);
      toast.error(err?.message || "Failed to pause Thunder");
    } finally {
      setPauseLoading(false);
    }
  };

  const handleResume = async () => {
    try {
      setPauseLoading(true);
      if (!data?.conversation_id) {
        toast.error("Cannot resume: conversation ID not found");
        return;
      }
      await resumeThunder(data.conversation_id).catch(e => { throw e; });
      toast.success("Thunder resumed successfully");
      // Refresh data
      const res = await getCandidateMemory(candidateId).catch(e => { throw e; });
      setData(res);
    } catch (err) {
      console.error("Failed to resume Thunder", err);
      toast.error(err?.message || "Failed to resume Thunder");
    } finally {
      setPauseLoading(false);
    }
  };

  if (loading || !data) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-500">
          <Zap className="h-4 w-4" />
          Thunder Engagement
        </div>
        <div className="mt-2 text-xs text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-blue-900">
          <Zap className="h-4 w-4 text-blue-600" />
          Thunder Engagement
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
            data?.is_thunder_paused
              ? 'text-amber-700 bg-amber-100'
              : 'text-green-700 bg-green-100'
          }`}>
            {data?.is_thunder_paused ? "Paused" : "Active"}
          </span>
          <button
            onClick={() => data?.is_thunder_paused ? handleResume() : setShowPauseModal(true)}
            disabled={pauseLoading}
            title={data?.is_thunder_paused ? "Resume Thunder outreach" : "Pause Thunder outreach"}
            className="text-xs font-medium text-blue-700 bg-white px-2.5 py-1 rounded-full hover:bg-blue-50 transition disabled:opacity-60"
          >
            {pauseLoading ? "..." : data?.is_thunder_paused ? "Resume" : "Pause"}
          </button>
        </div>
      </div>

      {showPauseModal && (
        <PauseThunderModal
          busy={pauseLoading}
          onConfirm={handlePause}
          onCancel={() => setShowPauseModal(false)}
          inProfile={true}
        />
      )}

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {/* Last Contact */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-900">
            <Clock className="h-3.5 w-3.5 text-blue-600" />
            Last Contact
          </div>
          <div className="text-sm font-bold text-blue-800">{timeAgo(data?.last_contact_at)}</div>
          <div className="text-xs text-blue-600">{data?.last_contact_at ? new Date(data.last_contact_at).toLocaleDateString() : "—"}</div>
        </div>

        {/* Next Contact */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-900">
            <Clock className="h-3.5 w-3.5 text-blue-600" />
            Next Contact
          </div>
          <div className="text-sm font-bold text-blue-800">
            {data?.next_contact_at ? `in ${formatCountdown(data.next_contact_at)}` : "Paused"}
          </div>
          <div className="text-xs text-blue-600">
            {data?.next_contact_at ? new Date(data.next_contact_at).toLocaleDateString() : "—"}
          </div>
        </div>

        {/* Messages Sent */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-900">
            <MessageSquare className="h-3.5 w-3.5 text-blue-600" />
            Messages
          </div>
          <div className="text-sm font-bold text-blue-800">{data?.message_count || 0}</div>
          <div className="text-xs text-blue-600">sent by Thunder</div>
        </div>

        {/* Profile Completeness */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-900">
            <CheckCircle2 className="h-3.5 w-3.5 text-blue-600" />
            Profile
          </div>
          <div className="text-sm font-bold text-blue-800">{data?.completeness || 0}%</div>
          <div className="text-xs text-blue-600">complete</div>
        </div>
      </div>

      {/* Summary */}
      {data?.summary && (
        <div className="mt-4 rounded-lg bg-white/60 p-3 border border-blue-100">
          <div className="text-xs font-semibold text-blue-900 mb-1">Summary</div>
          <p className="text-sm text-blue-800 italic">{data.summary}</p>
        </div>
      )}
    </div>
  );
}

const PAUSE_DURATION_OPTIONS = [
  { label: "24 hours", ms: 24 * 60 * 60 * 1000 },
  { label: "48 hours", ms: 48 * 60 * 60 * 1000 },
  { label: "1 week", ms: 7 * 24 * 60 * 60 * 1000 },
  { label: "Until I manually resume", ms: null },
];

function PauseThunderModal({ busy, onConfirm, onCancel, inProfile }) {
  const [selectedMs, setSelectedMs] = useState(PAUSE_DURATION_OPTIONS[0].ms);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-gray-900">Pause Thunder?</h3>
        <p className="mt-1 text-sm text-gray-500">
          Thunder will stop sending follow-ups to this candidate. Ownership stays with the AI recruiter -- no hand-back needed when it resumes.
        </p>
        <div className="mt-4 space-y-2">
          {PAUSE_DURATION_OPTIONS.map((opt) => (
            <label
              key={opt.label}
              className="flex cursor-pointer items-center gap-2 rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              <input
                type="radio"
                name="pause-duration"
                checked={selectedMs === opt.ms}
                onChange={() => setSelectedMs(opt.ms)}
              />
              Resume in: {opt.label}
            </label>
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(selectedMs)}
            disabled={busy}
            className="rounded-xl border border-amber-200 bg-amber-500 px-3 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-60"
          >
            {busy ? "Pausing..." : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
