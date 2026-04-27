import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getCandidateInterviewHistory,
  getFeedbackForInterview,
  submitInterviewFeedback,
  getPanelMembers,
  updateInterview,
  getMyInterviews
} from "../../services/api/interviews";

export default function FeedbackTab({ candidateId }) {
  const [historyData, setHistoryData] = useState(null);
  const [feedbackMap, setFeedbackMap] = useState({});
  const [panelMembersMap, setPanelMembersMap] = useState({});
  const [myPanelInterviewIds, setMyPanelInterviewIds] = useState(new Set());

  const [loading, setLoading] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [error, setError] = useState("");

  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [selectedInterview, setSelectedInterview] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitNotice, setSubmitNotice] = useState("");
  const [submitNoticeType, setSubmitNoticeType] = useState("success");

  const fetchFeedbackData = useCallback(async () => {
    if (!candidateId) return;

    try {
      setLoading(true);
      setError("");
      setFeedbackMap({});
      setPanelMembersMap({});
      setMyPanelInterviewIds(new Set());

      const [result, myInterviewsResult] = await Promise.all([
        getCandidateInterviewHistory(candidateId),
        getMyInterviews()
      ]);

      setHistoryData(result || null);

      const interviews = Array.isArray(result?.interviews)
        ? result.interviews
        : [];

      const myInterviews = Array.isArray(myInterviewsResult)
        ? myInterviewsResult
        : Array.isArray(myInterviewsResult?.interviews)
          ? myInterviewsResult.interviews
          : Array.isArray(myInterviewsResult?.data)
            ? myInterviewsResult.data
            : [];

      const allowedInterviewIds = new Set(
        myInterviews
          .filter((item) => String(item?.candidate_id) === String(candidateId))
          .map((item) => item?.interview_id || item?.id)
          .filter(Boolean)
      );

      setMyPanelInterviewIds(allowedInterviewIds);

      if (!interviews.length) return;

      setFeedbackLoading(true);

      const uniquePanelIds = [
        ...new Set(interviews.map((interview) => interview?.panel_id).filter(Boolean))
      ];

      const [feedbackResults, panelResults] = await Promise.all([
        Promise.all(
          interviews.map(async (interview) => {
            try {
              const res = await getFeedbackForInterview(interview.id);

              const list = Array.isArray(res)
                ? res
                : Array.isArray(res?.feedback)
                  ? res.feedback
                  : Array.isArray(res?.data)
                    ? res.data
                    : [];

              return {
                interviewId: interview.id,
                feedback: list
              };
            } catch (err) {
              console.error(`Failed to fetch feedback for interview ${interview.id}`, err);
              return {
                interviewId: interview.id,
                feedback: []
              };
            }
          })
        ),
        Promise.all(
          uniquePanelIds.map(async (panelId) => {
            try {
              const res = await getPanelMembers(panelId);

              const members = Array.isArray(res)
                ? res
                : Array.isArray(res?.members)
                  ? res.members
                  : Array.isArray(res?.panel_members)
                    ? res.panel_members
                    : [];

              return { panelId, members };
            } catch (err) {
              console.error(`Failed to fetch panel members for panel ${panelId}`, err);
              return { panelId, members: [] };
            }
          })
        )
      ]);

      const nextFeedbackMap = {};
      feedbackResults.forEach(({ interviewId, feedback }) => {
        nextFeedbackMap[interviewId] = feedback;
      });
      setFeedbackMap(nextFeedbackMap);

      const nextPanelMembersMap = {};
      panelResults.forEach(({ panelId, members }) => {
        nextPanelMembersMap[panelId] = members;
      });
      setPanelMembersMap(nextPanelMembersMap);
    } catch (err) {
      console.error("Failed to load feedback tab", err);
      setError(err?.message || "Failed to load feedback");
    } finally {
      setLoading(false);
      setFeedbackLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchFeedbackData();
  }, [fetchFeedbackData]);

  const interviews = Array.isArray(historyData?.interviews)
    ? historyData.interviews
    : [];

  const feedbackSummary = useMemo(() => {
    const totalInterviews = interviews.length;
    const completedInterviews = Number(historyData?.completed_interviews || 0);

    let interviewsWithFeedback = 0;
    let totalFeedbackEntries = 0;

    interviews.forEach((interview) => {
      const list = feedbackMap[interview.id] || [];
      if (list.length > 0) {
        interviewsWithFeedback += 1;
        totalFeedbackEntries += list.length;
      }
    });

    return {
      totalInterviews,
      completedInterviews,
      interviewsWithFeedback,
      interviewsWithoutFeedback: Math.max(totalInterviews - interviewsWithFeedback, 0),
      totalFeedbackEntries
    };
  }, [historyData, interviews, feedbackMap]);

  const openSubmitModal = (interview) => {
    setSelectedInterview(interview);
    setSubmitNotice("");
    setSubmitNoticeType("success");
    setShowSubmitModal(true);
  };

  const closeSubmitModal = () => {
    if (submitting) return;
    setShowSubmitModal(false);
    setSelectedInterview(null);
    setSubmitNotice("");
    setSubmitNoticeType("success");
  };

  const handleSubmitFeedback = async (form) => {
    if (!selectedInterview?.id) {
      setSubmitNotice("Interview is missing");
      setSubmitNoticeType("error");
      return;
    }

    if (!myPanelInterviewIds.has(selectedInterview.id)) {
      setSubmitNotice("You are not assigned as a panel member for this interview");
      setSubmitNoticeType("error");
      return;
    }

    try {
      setSubmitting(true);
      setSubmitNotice("");
      setSubmitNoticeType("success");

      await submitInterviewFeedback({
        interviewId: selectedInterview.id,
        interviewerId: form.interviewerId,
        technicalScore: Number(form.technical_score),
        communicationScore: Number(form.communication_score),
        problemSolvingScore: Number(form.problem_solving_score),
        cultureFitScore: Number(form.culture_fit_score),
        comments: form.comments,
        recommendation: form.recommendation
      });
const panelMembers = panelMembersMap[selectedInterview.panel_id] || [];

const latestFeedbackRes = await getFeedbackForInterview(selectedInterview.id);

const latestFeedbackList = Array.isArray(latestFeedbackRes)
  ? latestFeedbackRes
  : Array.isArray(latestFeedbackRes?.feedback)
    ? latestFeedbackRes.feedback
    : Array.isArray(latestFeedbackRes?.data)
      ? latestFeedbackRes.data
      : [];

const allPanelFeedbackSubmitted =
  panelMembers.length > 0 && latestFeedbackList.length >= panelMembers.length;

if (allPanelFeedbackSubmitted) {
  await updateInterview(selectedInterview.id, {
    status: "Completed"
  });
}

      await fetchFeedbackData();

      setSubmitNotice("Feedback submitted successfully");
      setSubmitNoticeType("success");

      setTimeout(() => {
        closeSubmitModal();
      }, 1000);
    } catch (err) {
      console.error("Failed to submit feedback", err);
      setSubmitNotice(err?.message || "Failed to submit feedback");
      setSubmitNoticeType("error");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <SectionCard title="Feedback Summary">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            {Array.from({ length: 5 }).map((_, index) => (
              <StatSkeleton key={index} />
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Interview Feedback">
          <FeedbackSkeletonCard />
          <FeedbackSkeletonCard />
        </SectionCard>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!historyData) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center text-gray-500">
        No feedback data available
      </div>
    );
  }

  return (
    <>
      <div className="space-y-6">
        <SectionCard title="Feedback Summary">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <Stat label="Total Interviews" value={feedbackSummary.totalInterviews} />
            <Stat label="Completed" value={feedbackSummary.completedInterviews} />
            <Stat label="With Feedback" value={feedbackSummary.interviewsWithFeedback} />
            <Stat label="Without Feedback" value={feedbackSummary.interviewsWithoutFeedback} />
            <Stat label="Feedback Entries" value={feedbackSummary.totalFeedbackEntries} />
          </div>
        </SectionCard>

        <SectionCard title="Interview Feedback">
          {!interviews.length ? (
            <EmptyState
              title="No interviews found"
              subtitle="Feedback will appear here once interviews are completed and feedback is submitted."
            />
          ) : (
            <div className="space-y-4">
              {interviews.map((interview) => {
                const feedbackList = feedbackMap[interview.id] || [];

                return (
                 <InterviewFeedbackCard
  key={interview.id}
  interview={interview}
  feedbackList={feedbackList}
  feedbackLoading={feedbackLoading}
  panelMembers={panelMembersMap[interview.panel_id] || []}
  canSubmitForLoggedInPanel={myPanelInterviewIds.has(Number(interview.id))}
  onSubmitClick={() => openSubmitModal(interview)}
/>
                );
              })}
            </div>
          )}
        </SectionCard>
      </div>

      {showSubmitModal && (
        <SubmitFeedbackModal
          interview={selectedInterview}
          panelMembers={panelMembersMap[selectedInterview?.panel_id] || []}
          loading={submitting}
          notice={submitNotice}
          noticeType={submitNoticeType}
          onClose={closeSubmitModal}
          onSubmit={handleSubmitFeedback}
        />
      )}
    </>
  );
}

function SectionCard({ title, children }) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-500 mb-4 uppercase tracking-wide">
        {title}
      </h3>
      {children}
    </section>
  );
}
function InterviewFeedbackCard({
  interview,
  feedbackList,
  feedbackLoading,
  panelMembers = [],
  canSubmitForLoggedInPanel,
  onSubmitClick
}) {
  const status = interview?.status || "Unknown";
  const roundName = interview?.panel_round_name || "Interview Round";
  const startTime = interview?.start_time ? formatDateTime(interview.start_time) : "-";
  const feedbackCount =
    typeof interview?.feedback_count === "number"
      ? interview.feedback_count
      : feedbackList.length;

  const submittedInterviewerIds = new Set(
  feedbackList
    .map((feedback) => feedback?.interviewer_id)
    .filter(Boolean)
);

const feedbackProgress = {
  submitted: submittedInterviewerIds.size,
  total: panelMembers.length
};

const currentUserFeedbackSubmitted =
  interview?.feedback_submitted === true || interview?.my_feedback;

const canSubmitFeedback =
  canSubmitForLoggedInPanel && !currentUserFeedbackSubmitted;

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/60 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-base font-semibold text-gray-900">
              {roundName}
            </div>
            <StatusBadge status={status} />
          </div>

          <div className="text-sm text-gray-600">{startTime}</div>

         <div className="text-sm text-gray-600">
  Feedback Progress:{" "}
  <span className="font-medium text-gray-800">
    {feedbackProgress.submitted} / {feedbackProgress.total || 0} submitted
  </span>
</div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="text-sm text-gray-500">
            Interview ID: {interview?.id ?? "-"}
          </div>

          {canSubmitFeedback && (
            <button
              type="button"
              onClick={onSubmitClick}
              className="inline-flex items-center rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100"
            >
              Submit Feedback
            </button>
          )}
        </div>
      </div>
      {panelMembers.length > 0 && (
  <div className="mt-4 rounded-xl border border-gray-200 bg-white p-3">
    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
      Panel Feedback Status
    </div>

    <div className="grid gap-2 md:grid-cols-2">
      {panelMembers.map((member) => {
        const interviewerId = member?.interviewer_id;
        const hasSubmitted = submittedInterviewerIds.has(interviewerId);

        return (
          <div
            key={interviewerId || member?.id}
            className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
              hasSubmitted
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-yellow-200 bg-yellow-50 text-yellow-700"
            }`}
          >
            <span className="font-medium">
              {member?.interviewer_name || member?.interviewer_email || "Panel Member"}
            </span>

            <span className="text-xs font-semibold">
              {hasSubmitted ? "Submitted" : "Pending"}
            </span>
          </div>
        );
      })}
    </div>
  </div>
)}

      <div className="mt-4">
        {feedbackLoading ? (
          <div className="text-sm text-gray-500">Loading feedback...</div>
        ) : feedbackList.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-500">
            No feedback submitted yet
          </div>
        ) : (
          <div className="space-y-3">
            {feedbackList.map((feedback, index) => (
              <FeedbackEntryCard
                key={feedback?.id || `${interview.id}-${index}`}
                feedback={feedback}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FeedbackEntryCard({ feedback }) {
  const headerItems = [
    {
      label: "Feedback ID",
      value: feedback?.id
    },
    {
      label: "Interviewer",
      value:
        feedback?.interviewer_name ||
        feedback?.reviewer_name ||
        feedback?.user_name ||
        feedback?.submitted_by ||
        feedback?.interviewer_id ||
        "-"
    },
    {
      label: "Recommendation",
      value:
        feedback?.recommendation ||
        feedback?.decision ||
        feedback?.result ||
        "-"
    }
  ];

  const detailEntries = Object.entries(feedback || {}).filter(
    ([key, value]) =>
      ![
        "id",
        "interview_id",
        "interviewer_name",
        "reviewer_name",
        "user_name",
        "submitted_by",
        "interviewer_id",
        "recommendation",
        "decision",
        "result"
      ].includes(key) &&
      value !== null &&
      value !== undefined &&
      value !== ""
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="grid gap-3 md:grid-cols-3">
        {headerItems.map((item) => (
          <div key={item.label}>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
              {item.label}
            </div>
            <div className="text-sm text-gray-800 break-words">
              {String(item.value ?? "-")}
            </div>
          </div>
        ))}
      </div>

      {detailEntries.length > 0 && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {detailEntries.map(([key, value]) => (
            <div key={key}>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                {formatLabel(key)}
              </div>
              <div className="text-sm text-gray-800 break-words">
                {String(value)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SubmitFeedbackModal({
  interview,
  panelMembers,
  loading,
  notice,
  noticeType,
  onClose,
  onSubmit
}) {
  const [form, setForm] = useState({
    interviewerId: "",
    technical_score: 5,
    communication_score: 5,
    problem_solving_score: 5,
    culture_fit_score: 5,
    comments: "",
    recommendation: ""
  });

  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (panelMembers.length === 1) {
      setForm((prev) => ({
        ...prev,
        interviewerId: panelMembers[0].interviewer_id || ""
      }));
    }
  }, [panelMembers]);

  const handleChange = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field]: value
    }));

    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: ""
      }));
    }
  };

  const validate = () => {
    const nextErrors = {};

    if (!form.interviewerId.trim()) {
      nextErrors.interviewerId = "Interviewer is required";
    }

    ["technical_score", "communication_score", "problem_solving_score", "culture_fit_score"].forEach((field) => {
      const value = Number(form[field]);
      if (Number.isNaN(value) || value < 1 || value > 10) {
        nextErrors[field] = "Score must be between 1 and 10";
      }
    });

    if (!form.comments.trim()) {
      nextErrors.comments = "Comments are required";
    }

    if (!form.recommendation.trim()) {
      nextErrors.recommendation = "Recommendation is required";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validate()) return;
    onSubmit(form);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-2xl rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Submit Feedback</h3>
            <p className="mt-1 text-sm text-gray-500">
              Add interview feedback for {interview?.panel_round_name || "this interview"}.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-6 space-y-5">
          {notice && (
            <div
              className={`rounded-2xl border px-4 py-3 text-sm ${
                noticeType === "error"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-green-200 bg-green-50 text-green-700"
              }`}
            >
              {notice}
            </div>
          )}

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <ReadOnlyField
              label="Interview ID"
              value={interview?.id || "-"}
            />

            <ReadOnlyField
              label="Round Name"
              value={interview?.panel_round_name || "-"}
            />

            <SelectField
              label="Interviewer"
              value={form.interviewerId}
              onChange={(e) => handleChange("interviewerId", e.target.value)}
              error={errors.interviewerId}
            >
              <option value="">Select interviewer</option>
              {panelMembers.map((member) => (
                <option
                  key={member?.interviewer_id || member?.id}
                  value={member?.interviewer_id || ""}
                >
                  {member?.interviewer_name || member?.interviewer_email || "Interviewer"}
                </option>
              ))}
            </SelectField>

            <SelectField
              label="Recommendation"
              value={form.recommendation}
              onChange={(e) => handleChange("recommendation", e.target.value)}
              error={errors.recommendation}
            >
              <option value="">Select recommendation</option>
              <option value="No Hire">No Hire</option>
              <option value="Not sure">Not sure</option>
              <option value="Average">Average</option>
              <option value="Hire">Hire</option>
              <option value="Must Hire">Must Hire</option>
            </SelectField>

            <FormField
              label="Technical Score"
              type="number"
              value={form.technical_score}
              onChange={(e) => handleChange("technical_score", e.target.value)}
              error={errors.technical_score}
              min="1"
              max="10"
            />

            <FormField
              label="Communication Score"
              type="number"
              value={form.communication_score}
              onChange={(e) => handleChange("communication_score", e.target.value)}
              error={errors.communication_score}
              min="1"
              max="10"
            />

            <FormField
              label="Problem Solving Score"
              type="number"
              value={form.problem_solving_score}
              onChange={(e) => handleChange("problem_solving_score", e.target.value)}
              error={errors.problem_solving_score}
              min="1"
              max="10"
            />

            <FormField
              label="Culture Fit Score"
              type="number"
              value={form.culture_fit_score}
              onChange={(e) => handleChange("culture_fit_score", e.target.value)}
              error={errors.culture_fit_score}
              min="1"
              max="10"
            />
          </div>

          <TextAreaField
            label="Comments"
            value={form.comments}
            onChange={(e) => handleChange("comments", e.target.value)}
            error={errors.comments}
            placeholder="Enter feedback comments"
            rows={5}
          />
        </div>

        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Close
          </button>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100 disabled:opacity-60"
          >
            {loading ? "Submitting..." : "Submit Feedback"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 text-center">
      <div className="text-2xl font-semibold text-gray-900">
        {value ?? 0}
      </div>
      <div className="mt-1 text-xs text-gray-500">{label}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const normalized = String(status || "").toLowerCase();

  let styles = "bg-gray-100 text-gray-700 border-gray-200";

  if (normalized.includes("completed")) {
    styles = "bg-green-50 text-green-700 border-green-200";
  } else if (normalized.includes("cancel")) {
    styles = "bg-red-50 text-red-700 border-red-200";
  } else if (normalized.includes("scheduled")) {
    styles = "bg-yellow-50 text-yellow-700 border-yellow-200";
  }

  return (
    <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${styles}`}>
      {status}
    </span>
  );
}

function EmptyState({ title, subtitle }) {
  return (
    <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center">
      <div className="text-sm font-semibold text-gray-900">{title}</div>
      <div className="mt-1 text-sm text-gray-500">{subtitle}</div>
    </div>
  );
}

function StatSkeleton() {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4">
      <div className="animate-pulse space-y-3">
        <div className="mx-auto h-6 w-10 rounded bg-gray-200" />
        <div className="mx-auto h-3 w-20 rounded bg-gray-100" />
      </div>
    </div>
  );
}

function FeedbackSkeletonCard() {
  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/60 p-4">
      <div className="animate-pulse space-y-3">
        <div className="h-4 w-40 rounded bg-gray-200" />
        <div className="h-3 w-52 rounded bg-gray-100" />
        <div className="h-3 w-28 rounded bg-gray-100" />
      </div>
    </div>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <div className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-700">
        {value}
      </div>
    </div>
  );
}

function FormField({
  label,
  error,
  type = "text",
  value,
  onChange,
  placeholder,
  min,
  max
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        min={min}
        max={max}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition ${
          error
            ? "border-red-300 focus:border-red-400"
            : "border-gray-300 focus:border-gray-400"
        }`}
      />
      {error ? <p className="mt-1 text-xs text-red-500">{error}</p> : null}
    </div>
  );
}

function SelectField({ label, error, value, onChange, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <select
        value={value}
        onChange={onChange}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition bg-white ${
          error
            ? "border-red-300 focus:border-red-400"
            : "border-gray-300 focus:border-gray-400"
        }`}
      >
        {children}
      </select>
      {error ? <p className="mt-1 text-xs text-red-500">{error}</p> : null}
    </div>
  );
}

function TextAreaField({
  label,
  error,
  value,
  onChange,
  placeholder,
  rows = 4
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <textarea
        rows={rows}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition resize-none ${
          error
            ? "border-red-300 focus:border-red-400"
            : "border-gray-300 focus:border-gray-400"
        }`}
      />
      {error ? <p className="mt-1 text-xs text-red-500">{error}</p> : null}
    </div>
  );
}

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatLabel(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}