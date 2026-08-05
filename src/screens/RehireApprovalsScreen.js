// Rehire guard -- Part 2 of the interview regrouping + rehire guard
// priority (2026-08-05). Candidates with a past no-hire outcome whose
// re-interview justification was NOT clearly justified enough for AI
// to auto-clear land here; no interview panel exists for any of these
// until a hiring manager decides. Same visual pattern as
// InterventionQueueScreen.js.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { decideRehireReview, getRehireReviews } from "../services/api/interviews";

function timeAgo(iso) {
  if (!iso) return "";
  const hours = Math.round((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function RehireApprovalsScreen() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [decidingId, setDecidingId] = useState(null);
  const [decisionNote, setDecisionNote] = useState("");
  const navigate = useNavigate();

  const load = async () => {
    try {
      const data = await getRehireReviews();
      setReviews(data?.reviews || []);
    } catch {
      toast.error("Unable to load rehire approvals.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDecide = async (review, decision) => {
    try {
      await decideRehireReview({ reviewId: review.id, decision, note: decisionNote || undefined });
      toast.success(
        decision === "approve"
          ? `Approved -- interview round created for ${review.candidate_name || review.candidate_id}.`
          : `Rejected -- no interview round will be scheduled.`,
      );
      setDecidingId(null);
      setDecisionNote("");
      load();
    } catch (err) {
      toast.error(err?.message || "Failed to record decision.");
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Rehire Approvals</h1>
        <p className="text-sm text-gray-500">
          Candidates with a past no-hire outcome, requested for re-interview, whose
          justification needs your sign-off before a round can be scheduled.
        </p>
      </div>

      <div className="rounded-2xl border bg-white shadow-sm">
        {loading ? (
          <div className="p-6 text-center text-sm text-gray-500">Loading...</div>
        ) : reviews.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-500">Nothing pending approval right now.</div>
        ) : (
          <div className="divide-y">
            {reviews.map((review) => (
              <div key={review.id} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <button
                      onClick={() => navigate(`/candidates/${review.candidate_id}`)}
                      className="font-semibold text-gray-900 hover:underline"
                    >
                      {review.candidate_name || review.candidate_id}
                    </button>
                    <div className="mt-0.5 text-xs text-gray-500">
                      Requesting round: <span className="font-medium">{review.round_name}</span>
                      {review.job_title ? ` for ${review.job_title}` : ""}
                      {review.requested_by_name ? ` -- requested by ${review.requested_by_name}` : ""}
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">{timeAgo(review.created_at)}</span>
                </div>

                <div className="mt-2 rounded-lg bg-gray-50 p-3 text-sm">
                  <div className="text-xs font-semibold text-gray-500">Recruiter's justification</div>
                  <div className="mt-1 text-gray-800">{review.justification}</div>
                </div>

                {review.ai_reasoning ? (
                  <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
                    <div className="text-xs font-semibold text-amber-700">Thunder's review</div>
                    <div className="mt-1 text-amber-900">{review.ai_reasoning}</div>
                  </div>
                ) : null}

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => handleDecide(review, "approve")}
                    className="rounded-lg bg-bx-navy px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
                  >
                    Approve &amp; schedule
                  </button>
                  <button
                    onClick={() => setDecidingId(decidingId === review.id ? null : review.id)}
                    className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50"
                  >
                    Reject
                  </button>
                </div>

                {decidingId === review.id && (
                  <div className="mt-2 space-y-2 rounded-lg border bg-gray-50 p-2">
                    <input
                      type="text"
                      value={decisionNote}
                      onChange={(e) => setDecisionNote(e.target.value)}
                      placeholder="Reason for rejecting (optional)"
                      className="w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleDecide(review, "reject")}
                        className="rounded-md bg-red-600 px-2 py-1 text-xs font-semibold text-white"
                      >
                        Confirm reject
                      </button>
                      <button onClick={() => setDecidingId(null)} className="rounded-md border px-2 py-1 text-xs">
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
