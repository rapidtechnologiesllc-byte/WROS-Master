// S-070/HRMS-0470 -- Candidate Engagement Health Metrics, mounted in
// MessagesTab (this real screen is single-column, no sidebar -- same
// adaptation ThunderMemorySection/ThunderActivitySection already made).
import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { getEngagementMetrics } from "../../services/api/engagementMetrics";

function responseRateColor(rate) {
  if (rate >= 60) return "text-green-700 bg-green-50 border-green-200";
  if (rate >= 30) return "text-amber-700 bg-amber-50 border-amber-200";
  return "text-red-700 bg-red-50 border-red-200";
}

function sentimentColor(score) {
  if (score == null) return "text-gray-500 bg-gray-50 border-gray-200";
  if (score > 0) return "text-green-700 bg-green-50 border-green-200";
  if (score < 0) return "text-red-700 bg-red-50 border-red-200";
  return "text-gray-600 bg-gray-50 border-gray-200";
}

function formatResponseTime(minutes) {
  if (minutes == null) return "N/A";
  if (minutes >= 60) return `${(minutes / 60).toFixed(1)}h`;
  return `${minutes}m`;
}

function MetricCard({ label, value, colorClass }) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${colorClass || "border-gray-200 bg-gray-50 text-gray-700"}`}>
      <div className="text-[11px] font-medium opacity-80">{label}</div>
      <div className="text-sm font-bold">{value}</div>
    </div>
  );
}

export default function EngagementMetricsSection({ candidateId }) {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    if (!candidateId) return;
    let cancelled = false;
    getEngagementMetrics(candidateId)
      .then((data) => !cancelled && setMetrics(data))
      .catch(() => {
        // No metrics yet for this candidate -- section just doesn't render.
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  if (!metrics) return null;

  return (
    <div className="rounded-2xl border bg-white">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <Activity className="h-4 w-4 text-blue-600" />
        <h3 className="text-sm font-semibold text-gray-900">Engagement Health</h3>
      </div>
      <div className="grid grid-cols-2 gap-2 p-4">
        <MetricCard label="Response Rate" value={`${metrics.response_rate}%`} colorClass={responseRateColor(metrics.response_rate)} />
        <MetricCard label="Avg Reply Time" value={formatResponseTime(metrics.avg_response_time_minutes)} />
        <MetricCard label="Messages" value={`${metrics.total_messages_exchanged} total`} />
        <MetricCard
          label="Sentiment"
          value={metrics.avg_sentiment_score == null ? "N/A" : `${metrics.avg_sentiment_score > 0 ? "+" : ""}${metrics.avg_sentiment_score}`}
          colorClass={sentimentColor(metrics.avg_sentiment_score)}
        />
      </div>
    </div>
  );
}
