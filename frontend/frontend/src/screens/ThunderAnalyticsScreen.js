// S-071/HRMS-0471 -- AI Recruiter Performance Analytics dashboard.
// No charting library installed in this codebase (same posture as
// S-063's Risk Dashboard) -- trend line and donut are hand-built SVG.
import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { getThunderAnalytics } from "../services/api/thunderAnalytics";

const RANGE_PRESETS = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
];

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function kpiColor(value, greenAt, amberAt, higherIsBetter) {
  const meetsGreen = higherIsBetter ? value >= greenAt : value < greenAt;
  const meetsAmber = higherIsBetter ? value >= amberAt : value <= amberAt;
  if (meetsGreen) return "border-green-200 bg-green-50 text-green-800";
  if (meetsAmber) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-red-200 bg-red-50 text-red-800";
}

function KpiCard({ label, value, suffix, colorClass, subtext }) {
  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${colorClass}`}>
      <div className="text-xs font-semibold opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-extrabold">{value}{suffix}</div>
      {subtext && <div className="mt-1 text-[11px] opacity-70">{subtext}</div>}
    </div>
  );
}

function TrendChart({ trends }) {
  const width = 640;
  const height = 200;
  const pad = 30;
  if (!trends.length) return null;
  const maxVal = Math.max(1, ...trends.flatMap((t) => [t.qualifications, t.escalations, t.ghostings]));
  const xStep = (width - pad * 2) / (trends.length - 1 || 1);
  const toY = (v) => height - pad - (v / maxVal) * (height - pad * 2);
  const line = (key) => trends.map((t, i) => `${pad + i * xStep},${toY(t[key])}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-48">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#e5e7eb" />
      <polyline points={line("qualifications")} fill="none" stroke="#16a34a" strokeWidth="2" />
      <polyline points={line("escalations")} fill="none" stroke="#dc2626" strokeWidth="2" />
      <polyline points={line("ghostings")} fill="none" stroke="#6b7280" strokeWidth="2" />
    </svg>
  );
}

function DonutChart({ thunderPct }) {
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const thunderLength = (thunderPct / 100) * circumference;
  return (
    <svg viewBox="0 0 160 160" className="h-40 w-40 mx-auto">
      <circle cx="80" cy="80" r={radius} fill="none" stroke="#e5e7eb" strokeWidth="20" />
      <circle
        cx="80" cy="80" r={radius} fill="none" stroke="#2563eb" strokeWidth="20"
        strokeDasharray={`${thunderLength} ${circumference}`}
        strokeDashoffset={circumference / 4}
        transform="rotate(-90 80 80)"
      />
      <text x="80" y="85" textAnchor="middle" className="fill-gray-900 text-lg font-bold">{thunderPct}%</text>
    </svg>
  );
}

export default function ThunderAnalyticsScreen() {
  const [data, setData] = useState(null);
  const [rangeDays, setRangeDays] = useState(30);
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const load = async (dateFrom, dateTo) => {
    try {
      const result = await getThunderAnalytics({ dateFrom, dateTo });
      console.log("Thunder Analytics Data:", result);
      console.log("Summary:", result?.summary);
      setData(result);
    } catch (error) {
      console.error("Thunder Analytics Error:", error);
      toast.error("Analytics unavailable. Please try again.");
    }
  };

  useEffect(() => {
    if (customFrom && customTo) {
      load(customFrom, customTo);
    } else {
      load(isoDaysAgo(rangeDays), isoDaysAgo(0));
    }
  }, [rangeDays, customFrom, customTo]);

  if (!data) return <div className="p-6 text-center text-sm text-gray-500">Loading...</div>;

  const { summary, trends, top_risk_candidates: topRisk, agent_actions_breakdown: breakdown } = data;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {RANGE_PRESETS.map((preset) => (
            <button
              key={preset.days}
              onClick={() => {
                setCustomFrom("");
                setCustomTo("");
                setRangeDays(preset.days);
              }}
              className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${!customFrom && rangeDays === preset.days ? "border-blue-500 bg-blue-50 text-blue-700" : "border-gray-300 text-gray-600 hover:bg-gray-50"}`}
            >
              {preset.label}
            </button>
          ))}
          <input type="date" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} className="rounded-lg border border-gray-300 px-2 py-1.5 text-xs" />
          <input type="date" value={customTo} onChange={(e) => setCustomTo(e.target.value)} className="rounded-lg border border-gray-300 px-2 py-1.5 text-xs" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <KpiCard label="Candidates Reached" value={summary.candidates_reached} suffix="" colorClass="border-blue-200 bg-blue-50 text-blue-800" />
        <KpiCard label="Candidates Responded" value={summary.candidates_responded} suffix="" colorClass="border-green-200 bg-green-50 text-green-800" />
        <KpiCard label="Jobs Connected" value={summary.jobs_connected_to_thunder} suffix="" colorClass="border-purple-200 bg-purple-50 text-purple-800" />
        <KpiCard label="Qualification Rate" value={summary.qualification_rate} suffix="%" colorClass={kpiColor(summary.qualification_rate, 70, 50, true)} />
        <KpiCard label="Escalation Rate" value={summary.escalation_rate} suffix="%" colorClass={kpiColor(summary.escalation_rate, 10, 20, false)} />
        <KpiCard label="Ghosting Rate" value={summary.ghosting_rate} suffix="%" colorClass="border-gray-200 bg-gray-50 text-gray-700" />
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <KpiCard
          label="Human Intervention"
          value={summary.human_intervention_rate}
          suffix="%"
          colorClass={kpiColor(summary.human_intervention_rate, 20, 30, false)}
          subtext={`Target: <${summary.human_dependency_target_pct}%`}
        />
      </div>

      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold text-gray-900">Daily Trends</h3>
        <div className="mb-2 flex gap-4 text-xs">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-600" /> Qualifications</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-600" /> Escalations</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-gray-500" /> Ghostings</span>
        </div>
        <TrendChart trends={trends} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-900">Avg Days to Qualify</h3>
          <div className="mt-2 text-2xl font-extrabold text-gray-900">{summary.avg_days_to_qualify ?? "N/A"}</div>
        </div>
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-900">Avg Messages / Candidate</h3>
          <div className="mt-2 text-2xl font-extrabold text-gray-900">{summary.avg_messages_per_candidate}</div>
        </div>
        <div className="rounded-2xl border bg-white p-4 shadow-sm text-center">
          <h3 className="text-sm font-semibold text-gray-900">Thunder vs Human Actions</h3>
          <DonutChart thunderPct={breakdown.thunder_pct} />
          <div className="text-xs text-gray-500">Thunder {breakdown.thunder_pct}% · Human {100 - breakdown.thunder_pct}%</div>
        </div>
      </div>

      <div className="rounded-2xl border bg-white shadow-sm">
        <h3 className="border-b px-4 py-3 text-sm font-semibold text-gray-900">Top 5 Risk Candidates</h3>
        {topRisk.length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-500">No at-risk candidates right now.</div>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {topRisk.map((c) => (
                <tr key={c.candidate_id} className="border-b last:border-b-0">
                  <td className="px-4 py-2 font-semibold text-gray-900">{c.name}</td>
                  <td className="px-4 py-2 text-gray-600">{c.risk_level}</td>
                  <td className="px-4 py-2 text-right text-gray-600">{c.drop_risk_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
