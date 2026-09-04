import { useEffect, useState } from "react";
import { Zap, Clock, MessageSquare, CheckCircle2 } from "lucide-react";
import { getCandidateMemory } from "../services/api/aiAgent";

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
        <span className="text-xs font-medium text-blue-700 bg-white px-2.5 py-1 rounded-full">
          Active
        </span>
      </div>

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
