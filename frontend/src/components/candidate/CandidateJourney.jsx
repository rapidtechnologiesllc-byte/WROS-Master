// S-059/HRMS-0459 -- Candidate Journey Dashboard.
// Real architecture note: this codebase has no literal 7-value pipeline
// state -- the backend derives each stage from real artifact existence
// (conversation, scores, interviews, offer, joining readiness, employee
// conversion), not a single status column. See candidate_journey_service.py's
// module docstring for the full mapping. BR-01's "multiple visits per
// stage" has no real backing mechanism here and is not attempted.
import { useEffect, useState } from "react";
import { Check, Circle } from "lucide-react";
import { getCandidateJourney } from "../../services/api/candidateJourney";

const STAGE_TAB_TARGETS = {
  ENGAGED: "messages",
  QUALIFYING: "messages",
  SCREENED: "profile",
  INTERVIEW: "interview",
  OFFER: "documents",
  PREBOARDING: "documents",
  JOINED: "profile",
};

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function StageMetrics({ stage }) {
  const m = stage.metrics || {};
  switch (stage.stage_name) {
    case "QUALIFYING":
      return (
        <p>
          {m.profile_completeness_pct != null ? `${m.profile_completeness_pct}% complete` : "Profile incomplete"}
          {m.missing_fields_count != null ? ` — ${m.missing_fields_count} field${m.missing_fields_count === 1 ? "" : "s"} still missing.` : ""}
          {m.days_in_stage != null ? ` Days in qualifying: ${m.days_in_stage}.` : ""}
          {m.thunder_message_count != null ? ` Thunder has sent ${m.thunder_message_count} messages.` : ""}
        </p>
      );
    case "SCREENED":
      return (
        <p>
          {m.overall_score != null ? `Overall Score: ${m.overall_score}/100. ` : "Score not yet computed. "}
          {m.technical_score != null && `Technical: ${m.technical_score} | `}
          {m.compensation_score != null && `Compensation: ${m.compensation_score} | `}
          {m.availability_score != null && `Availability: ${m.availability_score}.`}
        </p>
      );
    case "INTERVIEW":
      return (
        <p>
          L1: {m.l1_outcome ? `${m.l1_outcome}${m.l1_scheduled_at ? ` (${formatDate(m.l1_scheduled_at)})` : ""}` : "Not scheduled"}.{" "}
          L2: {m.l2_outcome ? `${m.l2_outcome}${m.l2_scheduled_at ? ` (${formatDate(m.l2_scheduled_at)})` : ""}` : "Not scheduled"}.
        </p>
      );
    case "OFFER":
      return (
        <p>
          {m.released_at ? `Offer sent ${formatDate(m.released_at)}. ` : "Offer not yet released. "}
          {m.offer_expire_date ? `Expires ${formatDate(m.offer_expire_date)}. ` : ""}
          Status: {m.offer_status || "Pending"}.
        </p>
      );
    case "PREBOARDING":
      return (
        <p>
          {m.joining_readiness_score != null ? `Joining Readiness: ${m.joining_readiness_score}%. ` : ""}
          {m.documents_received != null ? `${m.documents_received} of ${m.documents_total} documents received. ` : ""}
          {m.days_until_start != null ? `Joining in ${m.days_until_start} day${m.days_until_start === 1 ? "" : "s"}.` : ""}
        </p>
      );
    case "JOINED":
      return (
        <p>
          {m.joining_date ? `Joined ${formatDate(m.joining_date)}. ` : ""}
          {m.employee_number ? `Employee ID: ${m.employee_number}.` : ""}
        </p>
      );
    case "ENGAGED":
    default:
      return (
        <p>
          {m.channel ? `Channel: ${m.channel}. ` : ""}
          {m.response_time_hours != null ? `Response time to first message: ${m.response_time_hours}h.` : ""}
        </p>
      );
  }
}

function StageIcon({ status }) {
  if (status === "completed") {
    return (
      <div className="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center">
        <Check className="w-4 h-4" />
      </div>
    );
  }
  if (status === "active") {
    return (
      <div className="w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center animate-pulse">
        <Circle className="w-3 h-3 fill-current" />
      </div>
    );
  }
  return (
    <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-400 flex items-center justify-center">
      <Circle className="w-3 h-3" />
    </div>
  );
}

export default function CandidateJourney({ candidateId, onNavigateTab }) {
  const [journey, setJourney] = useState(null);
  const [error, setError] = useState("");
  const [selectedStage, setSelectedStage] = useState(null);

  useEffect(() => {
    if (!candidateId) return;
    let cancelled = false;
    getCandidateJourney(candidateId)
      .then((data) => {
        if (cancelled) return;
        setJourney(data);
        setError("");
        const stages = data?.stages;
        if (Array.isArray(stages) && stages.length > 0) {
          const active = stages.find((s) => s.status === "active");
          setSelectedStage(active || stages[0]);
        }
      })
      .catch((err) => {
        // 2026-08-05 -- was swallowing the real error entirely, so every
        // failure (a genuine backend bug, a 403, a network blip) showed
        // the same unhelpful message with nothing to diagnose from.
        if (!cancelled) {
          console.error("Failed to load candidate journey", err);
          setError(err?.message ? `Unable to load journey: ${err.message}` : "Unable to load journey. Please refresh.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  if (error) {
    return <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">{error}</div>;
  }
  if (!journey) return null;

  const handleStageClick = (stage) => {
    if (stage.status === "pending") return;
    setSelectedStage(stage);
    const target = STAGE_TAB_TARGETS[stage.stage_name];
    if (target && onNavigateTab) onNavigateTab(target);
  };

  return (
    <div className="mb-5 bg-white border rounded-2xl shadow-sm p-5">
      <div className="flex items-center justify-between overflow-x-auto pb-2">
        {journey.stages.map((stage, idx) => (
          <div key={stage.stage_name} className="flex items-center flex-1 min-w-[100px]">
            <button
              type="button"
              onClick={() => handleStageClick(stage)}
              disabled={stage.status === "pending"}
              className={`flex flex-col items-center gap-1 flex-1 ${stage.status === "pending" ? "cursor-default" : "cursor-pointer"}`}
            >
              <StageIcon status={stage.status} />
              <span className={`text-xs font-medium ${stage.status === "pending" ? "text-gray-400" : "text-gray-800"}`}>
                {stage.stage_label}
              </span>
              {stage.entered_at && <span className="text-[10px] text-gray-400">{formatDate(stage.entered_at)}</span>}
            </button>
            {idx < journey.stages.length - 1 && (
              <div className={`h-0.5 flex-1 mx-1 ${stage.status === "pending" ? "bg-gray-200" : "bg-green-400"}`} />
            )}
          </div>
        ))}
      </div>

      {selectedStage && (
        <div className="mt-4 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-700">
          <div className="font-semibold text-gray-900 mb-1">{selectedStage.stage_label}</div>
          <StageMetrics stage={selectedStage} />
        </div>
      )}
    </div>
  );
}
