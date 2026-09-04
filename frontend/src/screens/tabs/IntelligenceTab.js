// S-350/HRMS-P120 -- HR Intelligence Briefing (Candidate Desire Dashboard).
// Real access model per Avinash's explicit 2026-08-05 direction: visible
// to everyone who can see the candidate (candidate.view, same as every
// other tab) -- NOT the spec's literal "HR/Director only" restriction.
// Editing (regenerating the narrative/talking points) is restricted to
// users with 'candidate.desire_intelligence.edit' permission
// (assigned by role templates: Partner, BU Head, HR Manager, Super User)
// The Refresh button below is hidden for everyone else as a UX courtesy,
// the real gate is the API (permission-driven, not hardcoded role names).
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { getDesireIntelligence, refreshDesireIntelligence } from "../../services/api/desireIntelligence";
import { hasPermission } from "../../utils/permissionsRbac";

// REMOVED: CAN_EDIT_ROLES hardcoded list
// Now using permission-based check: hasPermission('candidate.desire_intelligence.edit')

const CATEGORY_LABELS = {
  CAREER_GROWTH: "Career Growth",
  COMPENSATION: "Compensation",
  STABILITY: "Stability",
  REMOTE_FLEXIBILITY: "Remote Flexibility",
  DOMAIN_INTEREST: "Domain Interest",
  COMPANY_REPUTATION: "Company Reputation",
  WORK_LIFE_BALANCE: "Work-Life Balance",
  SPEED_OF_DECISION: "Speed of Decision",
};

const ENGAGEMENT_BADGE = {
  HOT: { emoji: "🔥", label: "HOT", styles: "border-red-200 bg-red-50 text-red-700" },
  WARM: { emoji: "☀️", label: "WARM", styles: "border-amber-200 bg-amber-50 text-amber-700" },
  COOL: { emoji: "🌤️", label: "COOL", styles: "border-yellow-200 bg-yellow-50 text-yellow-700" },
  COLD: { emoji: "❄️", label: "COLD", styles: "border-blue-200 bg-blue-50 text-blue-700" },
};

function categoryLabel(category) {
  return CATEGORY_LABELS[category] || category;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function timeAgo(iso) {
  if (!iso) return "";
  const hours = Math.round((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function SectionCard({ title, children, right }) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">{title}</h3>
        {right || null}
      </div>
      {children}
    </section>
  );
}

function DesireBar({ label, score, direction }) {
  const pct = Math.max(0, Math.min(100, Math.round((score || 0) * 100)));
  const barColor = direction === "AWAY_FROM" ? "bg-red-500" : "bg-green-500";
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-gray-800">{label}</span>
        <span className="text-xs text-gray-500">{score != null ? score.toFixed(2) : "-"}</span>
      </div>
      <div className="h-3 w-full rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function IntelligenceTab({ candidateId, currentRole }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  // RBAC-driven: Check permission instead of hardcoded role names
  const canEdit = hasPermission('candidate.desire_intelligence.edit');

  const load = useCallback(async () => {
    if (!candidateId) return;
    try {
      setLoading(true);
      setError("");
      const result = await getDesireIntelligence(candidateId);
      setData(result);
    } catch (err) {
      setError(err?.message || "Failed to load Desire Intelligence.");
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      const result = await refreshDesireIntelligence(candidateId);
      setData(result);
      toast.success("Desire Intelligence refreshed.");
    } catch (err) {
      toast.error(err?.message || "Failed to refresh Desire Intelligence.");
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return <div className="rounded-2xl border bg-white p-6 text-center text-sm text-gray-500">Loading Desire Intelligence...</div>;
  }
  if (error) {
    return <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">{error}</div>;
  }
  if (!data || !data.has_profile) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center text-gray-500">
        No behavioral signals recorded for this candidate yet. Desire Intelligence builds up as Thunder observes real
        conversations, questions, objections, and portal activity.
      </div>
    );
  }

  const engagement = ENGAGEMENT_BADGE[data.engagement_level] || null;

  return (
    <div className="space-y-6">
      {data.has_competing_offer ? (
        <div className="rounded-2xl border border-red-300 bg-red-50 px-5 py-4">
          <div className="text-sm font-bold text-red-800">
            ⚠ COMPETING OFFER DETECTED -- URGENCY: {data.decision_urgency || "CRITICAL"}
          </div>
          <div className="mt-1 text-xs text-red-700">
            This candidate is considering another opportunity. Engage directly as soon as possible.
          </div>
        </div>
      ) : null}

      <SectionCard
        title="Desire Profile"
        right={
          engagement ? (
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${engagement.styles}`}>
              {engagement.emoji} {engagement.label}
            </span>
          ) : null
        }
      >
        <div className="space-y-4">
          {data.desire_ranking.length === 0 ? (
            <div className="text-sm text-gray-500">No categorized desires yet.</div>
          ) : (
            data.desire_ranking.map((item) => (
              <DesireBar key={item.category} label={categoryLabel(item.category)} score={item.score} direction="TOWARDS" />
            ))
          )}
          {data.primary_fear ? (
            <div className="pt-2 border-t">
              <DesireBar label={`${categoryLabel(data.primary_fear)} (fear)`} score={data.primary_fear_score} direction="AWAY_FROM" />
            </div>
          ) : null}
        </div>
        {data.profile_updated_at ? (
          <div className="mt-4 text-xs text-gray-400">Profile last updated {timeAgo(data.profile_updated_at)}</div>
        ) : null}
      </SectionCard>

      <SectionCard
        title="Thunder's Analysis"
        right={
          canEdit ? (
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing}
              className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs font-semibold text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          ) : null
        }
      >
        {data.narrative_summary ? (
          <>
            <div className="mb-2 text-xs text-gray-400">
              {data.narrative_updated_at ? `Updated ${timeAgo(data.narrative_updated_at)}` : null}
            </div>
            <div className="whitespace-pre-line text-sm leading-relaxed text-gray-800">{data.narrative_summary}</div>
          </>
        ) : (
          <div className="text-sm text-gray-500">
            No briefing generated yet.{" "}
            {canEdit ? "Click Refresh to generate one." : "Contact your manager to generate a briefing."}
          </div>
        )}
      </SectionCard>

      <SectionCard title="Talking Points for Your Next Conversation">
        {data.talking_points && data.talking_points.length > 0 ? (
          <ul className="space-y-2">
            {data.talking_points.map((point, idx) => (
              <li key={idx} className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-2.5 text-sm text-gray-800">
                {point}
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-sm text-gray-500">No talking points generated yet.</div>
        )}
      </SectionCard>

      <SectionCard title="Thunder Motivation History">
        {data.motivation_history.length === 0 ? (
          <div className="text-sm text-gray-500">Thunder hasn't sent any proactive motivation messages yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold text-gray-500">
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Trigger</th>
                  <th className="px-3 py-2">Desire Targeted</th>
                  <th className="px-3 py-2">Message</th>
                  <th className="px-3 py-2">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {data.motivation_history.map((row) => (
                  <tr key={row.id} className="border-b last:border-b-0">
                    <td className="px-3 py-2 text-gray-500">{formatDateTime(row.sent_at)}</td>
                    <td className="px-3 py-2 text-gray-700">{row.trigger_type.replace(/_/g, " ")}</td>
                    <td className="px-3 py-2 text-gray-700">{row.desire_category_targeted ? categoryLabel(row.desire_category_targeted) : "-"}</td>
                    <td className="px-3 py-2 text-gray-600">{row.message_preview}...</td>
                    <td className="px-3 py-2 text-gray-600">
                      {row.offer_accepted === true
                        ? "Offer accepted"
                        : row.response_within_24h === true
                          ? "Replied within 24h"
                          : row.response_within_24h === false
                            ? "No response"
                            : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
