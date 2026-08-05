// S-102/HRMS-P207 -- Hiring Manager Candidate Review. Shows every
// candidate assigned to a hiring manager with their full interview
// feedback history. Approval/rejection itself happens on the existing
// candidate status action (approval_endpoint below), not here -- this
// is a read-only review surface.
//
// Real fix, 2026-08-05 -- used to make the user manually type their
// own "Hiring Manager User ID" into a text field (Avinash: "why do we
// need this field, shouldn't this be based on the current login").
// Worse than a UX smell: the old backend route took that ID as a raw
// path parameter with no ownership check, so any logged-in internal
// user could view any OTHER hiring manager's candidates by typing a
// different ID. Now loads "my own" candidates automatically from the
// authenticated session, same as every other self-service screen.
import { useEffect, useState } from "react";
import { UserCheck, CheckCircle2, XCircle, HelpCircle } from "lucide-react";
import { Card } from "../components/ui";
import cx from "../utils/cx";
import { getMyHmCandidateReview } from "../services/api/interviews";

const RECOMMENDATION_STYLES = {
  Hire: "border-emerald-200 bg-emerald-50 text-emerald-800",
  Mixed: "border-amber-200 bg-amber-50 text-amber-800",
  "No Feedback": "border-gray-200 bg-gray-50 text-gray-600",
};

function RoundCard({ round }) {
  return (
    <div className="rounded-xl border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-gray-900">{round.round_name}</div>
        <span className={cx("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", RECOMMENDATION_STYLES[round.overall_recommendation] || "border-gray-200 bg-gray-50 text-gray-600")}>
          {round.overall_recommendation}
        </span>
      </div>
      <div className="text-xs text-gray-500">
        {round.status} · {round.start_time ? new Date(round.start_time).toLocaleString() : "—"}
      </div>
      {round.feedbacks.length === 0 ? (
        <div className="mt-2 text-xs text-gray-400">No feedback submitted yet.</div>
      ) : (
        <div className="mt-2 grid gap-2">
          {round.feedbacks.map((f) => (
            <div key={f.feedback_id} className="rounded-lg border bg-gray-50 px-3 py-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-800">{f.interviewer_name}</span>
                <span
                  className={cx(
                    "inline-flex items-center gap-1 font-semibold",
                    f.recommendation === "Hire" ? "text-emerald-700" : f.recommendation === "Reject" ? "text-rose-700" : "text-amber-700",
                  )}
                >
                  {f.recommendation === "Hire" ? <CheckCircle2 className="h-3 w-3" /> : f.recommendation === "Reject" ? <XCircle className="h-3 w-3" /> : <HelpCircle className="h-3 w-3" />}
                  {f.recommendation}
                </span>
              </div>
              <div className="mt-1 text-gray-600">
                Technical {f.technical_score ?? "—"} · Communication {f.communication_score ?? "—"} · Problem Solving {f.problem_solving_score ?? "—"} · Culture Fit {f.culture_fit_score ?? "—"} · Avg {f.average_score}
              </div>
              {f.comments ? <div className="mt-1 text-gray-600">{f.comments}</div> : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateReviewCard({ item }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-gray-900">{item.candidate_name}</div>
          <div className="text-xs text-gray-500">
            {item.job_title || "—"} · {item.candidate_email} · {item.pipeline_status}
          </div>
        </div>
        <span className="text-xs text-gray-500">{item.completed_interview_count} completed round(s)</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="ghost" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Hide" : "View"} Interview Feedback
        </Button>
      </div>
      {expanded ? (
        <div className="mt-3 grid gap-2">
          {item.interviews.length === 0 ? (
            <div className="text-xs text-gray-500">No interview rounds recorded yet.</div>
          ) : (
            item.interviews.map((r) => <RoundCard key={r.interview_id} round={r} />)
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function HmCandidateReviewScreen() {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    getMyHmCandidateReview()
      .then(setReview)
      .catch((err) => setError(err.message || "Failed to load your candidate review."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="grid gap-4">
      <Card
        title="Hiring Manager Candidate Review"
        subtitle="Every candidate assigned to you as hiring manager, with their full interview feedback history. Approve/Reject/Hold happens on the candidate's own status action, not here."
        icon={<UserCheck className="h-4 w-4" />}
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}

        {loading ? (
          <div className="py-6 text-center text-sm text-gray-500">Loading...</div>
        ) : review ? (
          <div className="mt-4">
            <div className="mb-3 text-sm text-gray-600">
              {review.hiring_manager_name} · {review.total_candidates} candidate(s) assigned
            </div>
            <div className="grid gap-3">
              {review.candidates.length === 0 ? (
                <div className="py-6 text-center text-sm text-gray-500">No candidates assigned to this hiring manager.</div>
              ) : (
                review.candidates.map((item) => <CandidateReviewCard key={item.candidate_id} item={item} />)
              )}
            </div>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
