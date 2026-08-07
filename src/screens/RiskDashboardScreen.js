// S-063/HRMS-0463 -- Candidate Risk Dashboard.
// No charting library is installed in this codebase -- rather than add
// a new dependency for two small charts, the sentiment trend line and
// stage risk bars are hand-built as plain inline SVG (self-contained,
// no new install risk).
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { addCandidateToInterventionQueue, getRiskDashboard } from "../services/api/riskDashboard";

const RISK_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const STAGES = ["ENGAGED", "QUALIFYING", "SCREENED", "INTERVIEW", "OFFER", "PREBOARDING"];
const DIMENSIONS = [
  { label: "All", match: () => true },
  { label: "Low Response Rate", match: (s) => /response rate/i.test(s) },
  { label: "Negative Sentiment", match: (s) => /sentiment/i.test(s) },
  { label: "Stuck in Stage", match: (s) => /stuck|no contact|no response|no recent/i.test(s) },
  { label: "Low Readiness", match: (s) => /readiness/i.test(s) },
];

const SUMMARY_CARD_DEFS = [
  { key: "critical_count", label: "Critical", level: "CRITICAL", color: "bg-red-100 text-red-800 border-red-300" },
  { key: "high_count", label: "High", level: "HIGH", color: "bg-red-50 text-red-700 border-red-200" },
  { key: "medium_count", label: "Medium", level: "MEDIUM", color: "bg-amber-50 text-amber-700 border-amber-200" },
  { key: "low_count", label: "Low", level: "LOW", color: "bg-green-50 text-green-700 border-green-200" },
];

function riskBarColor(score) {
  if (score >= 80) return "bg-red-500";
  if (score >= 50) return "bg-amber-500";
  return "bg-green-500";
}

function SentimentTrendChart({ data }) {
  const width = 560;
  const height = 160;
  const pad = 24;
  if (!data.length) return null;
  const xStep = (width - pad * 2) / (data.length - 1 || 1);
  const toY = (pct) => height - pad - (pct / 100) * (height - pad * 2);
  const linePoints = (key) => data.map((d, i) => `${pad + i * xStep},${toY(d[key])}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#e5e7eb" />
      <polyline points={linePoints("avg_positive_pct")} fill="none" stroke="#16a34a" strokeWidth="2" />
      <polyline points={linePoints("avg_negative_pct")} fill="none" stroke="#dc2626" strokeWidth="2" />
    </svg>
  );
}

function StageRiskBars({ data }) {
  if (!data.length) return <p className="text-sm text-gray-500">No stage data yet.</p>;
  return (
    <div className="space-y-2">
      {data.map((row) => (
        <div key={row.stage} className="flex items-center gap-2 text-xs">
          <div className="w-24 shrink-0 text-gray-600">{row.stage}</div>
          <div className="flex-1 h-3 rounded-full bg-gray-100 overflow-hidden">
            <div className={`h-full ${riskBarColor(row.avg_risk_score)}`} style={{ width: `${row.avg_risk_score}%` }} />
          </div>
          <div className="w-20 shrink-0 text-right text-gray-500">{row.avg_risk_score} avg ({row.candidate_count})</div>
        </div>
      ))}
    </div>
  );
}

export default function RiskDashboardScreen() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [riskFilter, setRiskFilter] = useState("All");
  const [stageFilter, setStageFilter] = useState("All");
  const [dimensionFilter, setDimensionFilter] = useState("All");
  const lastGoodRef = useRef(null);
  const navigate = useNavigate();

  const load = async () => {
    try {
      const result = await getRiskDashboard();
      lastGoodRef.current = result;
      setData(result);
      setError("");
    } catch {
      if (lastGoodRef.current) {
        setData(lastGoodRef.current); // BR: cache last successful response for 5 min
      } else {
        setError("Dashboard unavailable. Please refresh.");
      }
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleAddToQueue = async (candidateId) => {
    try {
      await addCandidateToInterventionQueue(candidateId);
      toast.success("Added to intervention queue.");
    } catch (err) {
      toast.error(err?.message || "Failed to add to queue.");
    }
  };

  if (error) {
    return <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  }
  if (!data) return <div className="p-6 text-center text-sm text-gray-500">Loading...</div>;

  const filteredCandidates = data.candidates_at_risk.filter((c) => {
    if (riskFilter !== "All" && c.risk_level !== riskFilter) return false;
    if (stageFilter !== "All" && c.stage !== stageFilter) return false;
    const dimension = DIMENSIONS.find((d) => d.label === dimensionFilter);
    if (dimension && !dimension.match(c.top_risk_signal)) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {SUMMARY_CARD_DEFS.map((def) => (
          <button
            key={def.key}
            onClick={() => setRiskFilter(riskFilter === def.level ? "All" : def.level)}
            className={`rounded-2xl border p-4 text-left shadow-sm transition hover:shadow ${def.color} ${riskFilter === def.level ? "ring-2 ring-offset-1" : ""}`}
          >
            <div className="text-xs font-semibold">{def.label}</div>
            <div className="mt-1 text-2xl font-extrabold">{data.risk_summary[def.key]}</div>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm">
          <option value="All">All Risk Levels</option>
          {RISK_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm">
          <option value="All">All Stages</option>
          {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={dimensionFilter} onChange={(e) => setDimensionFilter(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm">
          {DIMENSIONS.map((d) => <option key={d.label} value={d.label}>{d.label}</option>)}
        </select>
      </div>

      <div className="rounded-2xl border bg-white shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs font-semibold text-gray-500">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Stage</th>
              <th className="px-4 py-3">Drop Risk Score</th>
              <th className="px-4 py-3">Top Signal</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredCandidates.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-gray-500">No candidates match the current filters.</td></tr>
            ) : (
              filteredCandidates.map((c) => (
                <tr key={c.candidate_id} className="border-b last:border-b-0">
                  <td className="px-4 py-3 font-semibold text-gray-900">{c.name}</td>
                  <td className="px-4 py-3 text-gray-600">{c.stage}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 rounded-full bg-gray-100 overflow-hidden">
                        <div className={`h-full ${riskBarColor(c.drop_risk_score)}`} style={{ width: `${c.drop_risk_score}%` }} />
                      </div>
                      <span className="text-xs text-gray-600">{c.drop_risk_score}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{c.top_risk_signal}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button onClick={() => navigate(`/candidates/${c.candidate_id}?tab=messages`)} className="text-xs font-semibold text-blue-600 hover:underline">
                        View
                      </button>
                      <button onClick={() => handleAddToQueue(c.candidate_id)} className="rounded-md border border-gray-300 px-2 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50">
                        Add to Queue
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-semibold text-gray-900">Sentiment Trend (14 days)</h3>
          <div className="mb-2 flex gap-4 text-xs">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-600" /> Positive %</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-600" /> Negative %</span>
          </div>
          <SentimentTrendChart data={data.sentiment_trend} />
        </div>
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-gray-900">Stage Risk Breakdown</h3>
          <StageRiskBars data={data.stage_risk_breakdown} />
        </div>
      </div>
    </div>
  );
}
