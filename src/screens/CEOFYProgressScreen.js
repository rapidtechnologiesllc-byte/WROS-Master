import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { CheckCircle, AlertCircle, TrendingUp } from "lucide-react";
import { Card } from "../components/ui";
import { apiRequest } from "../services/api/requests";

export default function CEOFYProgressScreen() {
  const [summary, setSummary] = useState(null);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        // Fetch FY summary
        const summaryRes = await apiRequest("/agents/ceo/fy-summary");
        if (summaryRes?.data) {
          setSummary(summaryRes.data);
        }

        // Fetch full progress
        const progressRes = await apiRequest("/agents/ceo/fy-progress");
        if (progressRes?.data) {
          setProgress(progressRes.data);
        }
      } catch (err) {
        toast.error("Failed to load FY progress dashboard");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <div className="p-6 text-center text-gray-500">Loading FY progress...</div>;
  if (!summary) return <div className="p-6 text-center text-gray-500">No data available</div>;

  const ProgressBar = ({ current, target, pct }) => (
    <div className="w-full">
      <div className="flex justify-between mb-2">
        <span className="text-sm text-gray-600">{current} / {target}</span>
        <span className="text-sm font-semibold text-gray-900">{pct.toFixed(0)}%</span>
      </div>
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct >= 90 ? "bg-green-500" : pct >= 70 ? "bg-blue-500" : "bg-amber-500"
          }`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );

  const MetricCard = ({ metric, status }) => (
    <Card className="mb-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-semibold text-gray-900">{metric.label}</h3>
            {status === "ON_TRACK" ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <AlertCircle className="h-5 w-5 text-amber-500" />
            )}
          </div>
          <ProgressBar
            current={metric.current}
            target={metric.target}
            pct={metric.progress_pct}
          />
          <div className="text-xs text-gray-500 mt-2">{metric.detail}</div>
        </div>
      </div>
    </Card>
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">FY 2026 Progress Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Overall organizational progress: {summary.overall_health_pct}% health</p>
      </div>

      {/* Executive Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100/50">
          <div>
            <div className="text-xs font-semibold text-blue-600 uppercase">FY Progress</div>
            <div className="text-3xl font-bold text-blue-900 mt-2">{summary.fy_progress_pct.toFixed(0)}%</div>
            <div className="text-xs text-blue-600 mt-2">Through the fiscal year</div>
          </div>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-green-100/50">
          <div>
            <div className="text-xs font-semibold text-green-600 uppercase">On Track</div>
            <div className="text-3xl font-bold text-green-900 mt-2">{summary.on_track_count} / 7</div>
            <div className="text-xs text-green-600 mt-2">Key metrics on plan</div>
          </div>
        </Card>

        <Card className="bg-gradient-to-br from-amber-50 to-amber-100/50">
          <div>
            <div className="text-xs font-semibold text-amber-600 uppercase">Behind</div>
            <div className="text-3xl font-bold text-amber-900 mt-2">{summary.behind_count}</div>
            <div className="text-xs text-amber-600 mt-2">Needs attention</div>
          </div>
        </Card>
      </div>

      {/* Key Metrics */}
      <Card title="Key Metrics" className="mb-6">
        <div className="text-sm text-gray-600 mb-4">{summary.headline}</div>
        <div className="space-y-2">
          {Object.entries(summary.key_metrics).map(([key, value]) => (
            <div key={key} className="flex justify-between text-sm">
              <span className="text-gray-600 capitalize">{key}</span>
              <span className="font-semibold text-gray-900">{value}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Detailed Metrics */}
      {progress && (
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Detailed Progress</h2>
          <MetricCard
            metric={{
              label: "Headcount",
              current: progress.headcount.current,
              target: progress.headcount.target,
              progress_pct: progress.headcount.progress_pct,
              detail: `Target: ${progress.headcount.target} employees`
            }}
            status={progress.headcount.status}
          />
          <MetricCard
            metric={{
              label: "Revenue",
              current: (progress.revenue.current_usd / 1000000).toFixed(1),
              target: (progress.revenue.target_usd / 1000000).toFixed(1),
              progress_pct: progress.revenue.progress_pct,
              detail: `${progress.revenue.progress_pct.toFixed(0)}% of annual target`
            }}
            status={progress.revenue.status}
          />
          <MetricCard
            metric={{
              label: "New Logos",
              current: progress.new_logos.current,
              target: progress.new_logos.target,
              progress_pct: progress.new_logos.progress_pct,
              detail: `Customer acquisition on track`
            }}
            status={progress.new_logos.status}
          />
          <MetricCard
            metric={{
              label: "Engagement",
              current: progress.engagement.current_score.toFixed(0),
              target: progress.engagement.target_score,
              progress_pct: progress.engagement.progress_pct,
              detail: "Opportunity pipeline health"
            }}
            status={progress.engagement.status}
          />
          <MetricCard
            metric={{
              label: "Retention",
              current: progress.retention.current_pct.toFixed(0),
              target: progress.retention.target_pct,
              progress_pct: progress.retention.progress_pct,
              detail: "Employee retention rate"
            }}
            status={progress.retention.status}
          />
          <MetricCard
            metric={{
              label: "Utilization",
              current: progress.utilization.current_pct.toFixed(0),
              target: progress.utilization.target_pct,
              progress_pct: progress.utilization.progress_pct,
              detail: "Billable hours vs available capacity"
            }}
            status={progress.utilization.status}
          />
          <MetricCard
            metric={{
              label: "Margin",
              current: progress.margin.current_pct.toFixed(0),
              target: progress.margin.target_pct,
              progress_pct: progress.margin.progress_pct,
              detail: "Gross margin percentage"
            }}
            status={progress.margin.status}
          />
        </div>
      )}

      {/* CEO Priorities */}
      {summary.priorities && (
        <Card title="CEO Priorities" className="mt-6">
          <div className="space-y-4">
            {summary.priorities.map((priority, i) => (
              <div key={i} className="flex gap-4 pb-4 border-b last:border-0">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center font-semibold text-blue-600">
                  {priority.rank}
                </div>
                <div className="flex-1">
                  <div className="font-semibold text-gray-900">{priority.metric}</div>
                  <div className="text-sm text-gray-600 mt-1">{priority.gap}</div>
                  <div className="text-sm font-medium text-blue-600 mt-1">{priority.action}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
