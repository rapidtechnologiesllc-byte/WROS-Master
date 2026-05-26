import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createCandidateHistoryEvent,
  HISTORY_EVENT_TYPES,
} from "../../services/api/candidateHistory";
import {
  getCandidateInterviewHistory,
  getFeedbackForInterview,
  submitInterviewFeedback,
  getPanelMembers,
  updateInterview,
  getMyInterviews,
} from "../../services/api/interviews";
const SKIP_REASON_PREFIX = "[NOT_ATTENDED]";

const recommendationOptions = [
  { value: "", label: "Select recommendation" },
  { value: "No Hire", label: "No Hire" },
  { value: "Not sure", label: "Not sure" },
  { value: "Average", label: "Average" },
  { value: "Hire", label: "Hire" },
  { value: "Must Hire", label: "Must Hire" },
];

const normalizeFeedbackList = (res) => {
  if (Array.isArray(res)) return res;
  if (Array.isArray(res?.feedback)) return res.feedback;
  if (Array.isArray(res?.data)) return res.data;
  return [];
};

const normalizeMyInterviews = (res) => {
  if (Array.isArray(res)) return res;
  if (Array.isArray(res?.interviews)) return res.interviews;
  if (Array.isArray(res?.data)) return res.data;
  return [];
};

const isSkippedFeedback = (feedback) => {
  const comments = String(feedback?.comments || "")
    .trim()
    .toLowerCase();
  return comments.startsWith(SKIP_REASON_PREFIX.toLowerCase());
};

const getInterviewId = (interview) => {
  return Number(interview?.id ?? interview?.interview_id);
};
const buildFeedbackFromLimitedInterview = (interview) => {
  const feedback = interview?.my_feedback;

  if (!feedback) return null;

  return {
    id: feedback?.feedback_id || feedback?.id,
    interview_id: getInterviewId(interview),
    interviewer_id: interview?.interviewer_id || "",
    interviewer_name: interview?.interviewer_name || "You",
    technical_score: feedback?.technical_score,
    communication_score: feedback?.communication_score,
    problem_solving_score: feedback?.problem_solving_score,
    culture_fit_score: feedback?.culture_fit_score,
    average_score: feedback?.average_score,
    comments: feedback?.comments,
    recommendation: feedback?.recommendation,
    submitted_at: feedback?.submitted_at,
  };
};
const getFeedbackBreakdown = (feedbackList = []) => {
  const submittedInterviewerIds = new Set();
  const skippedInterviewerIds = new Set();
  const feedbackByInterviewerId = new Map();

  feedbackList.forEach((feedback) => {
    const interviewerId =
      feedback?.interviewer_id ||
      feedback?.interviewer_email ||
      feedback?.interviewer_name;

    if (!interviewerId) return;
    feedbackByInterviewerId.set(interviewerId, feedback);

    if (isSkippedFeedback(feedback)) {
      skippedInterviewerIds.add(interviewerId);
    } else {
      submittedInterviewerIds.add(interviewerId);
    }
  });

  const doneInterviewerIds = new Set([
    ...submittedInterviewerIds,
    ...skippedInterviewerIds,
  ]);

  return {
    submittedInterviewerIds,
    skippedInterviewerIds,
    doneInterviewerIds,
    feedbackByInterviewerId,
  };
};

export default function FeedbackTab({
  candidateId,
  limitedMode = false,
  limitedInterview = null,
}) {
  const [historyData, setHistoryData] = useState(null);
  const [feedbackMap, setFeedbackMap] = useState({});
  const [panelMembersMap, setPanelMembersMap] = useState({});
  const [myPanelInterviewMap, setMyPanelInterviewMap] = useState(new Map());
  const [loggedInInterviewerId, setLoggedInInterviewerId] = useState("");

  const [loading, setLoading] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [error, setError] = useState("");

  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [showSkipModal, setShowSkipModal] = useState(false);
  const [selectedInterview, setSelectedInterview] = useState(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitNotice, setSubmitNotice] = useState("");
  const [submitNoticeType, setSubmitNoticeType] = useState("success");

  const [skipReason, setSkipReason] = useState("");
  const [skipError, setSkipError] = useState("");

  const fetchFeedbackData = useCallback(async () => {
    if (!candidateId) return;

    try {
      setLoading(true);
      setError("");
      setFeedbackMap({});
      setPanelMembersMap({});
      setMyPanelInterviewMap(new Map());
      setLoggedInInterviewerId("");
      if (limitedMode && limitedInterview) {
        const interviewId = getInterviewId(limitedInterview);
        const interviewerId = limitedInterview?.interviewer_id || "";
        const feedback = buildFeedbackFromLimitedInterview(limitedInterview);

        setLoggedInInterviewerId(interviewerId);

        setHistoryData({
          interviews: [limitedInterview],
        });

        setMyPanelInterviewMap(
          new Map([
            [
              interviewId,
              {
                ...limitedInterview,
                feedback_submitted: Boolean(
                  limitedInterview?.feedback_submitted,
                ),
                my_feedback: limitedInterview?.my_feedback || null,
              },
            ],
          ]),
        );

        setFeedbackMap({
          [interviewId]: feedback ? [feedback] : [],
        });

        setPanelMembersMap({
          [limitedInterview?.panel_id]: [
            {
              interviewer_id: interviewerId,
              interviewer_name: limitedInterview?.interviewer_name || "You",
            },
          ],
        });

        return;
      }

      const [candidateHistoryResult, myInterviewsResult] = await Promise.all([
        getCandidateInterviewHistory(candidateId),
        getMyInterviews(),
      ]);

      setHistoryData(candidateHistoryResult || null);

      const candidateInterviews = Array.isArray(
        candidateHistoryResult?.interviews,
      )
        ? candidateHistoryResult.interviews
        : [];

      const myInterviews = normalizeMyInterviews(myInterviewsResult);
      const currentLoggedInInterviewerId =
        myInterviewsResult?.interviewer_id || "";

      setLoggedInInterviewerId(currentLoggedInInterviewerId);

      const nextMyPanelInterviewMap = new Map();

      myInterviews
        .filter((item) => String(item?.candidate_id) === String(candidateId))
        .forEach((item) => {
          const interviewId = Number(item?.interview_id ?? item?.id);
          if (interviewId) {
            nextMyPanelInterviewMap.set(interviewId, item);
          }
        });

      setMyPanelInterviewMap(nextMyPanelInterviewMap);

      if (!candidateInterviews.length) return;

      setFeedbackLoading(true);

      const uniquePanelIds = [
        ...new Set(
          candidateInterviews
            .map((interview) => interview?.panel_id)
            .filter(Boolean),
        ),
      ];

      const [feedbackResults, panelResults] = await Promise.all([
        Promise.all(
          candidateInterviews.map(async (interview) => {
            const interviewId = getInterviewId(interview);

            try {
              const res = await getFeedbackForInterview(interviewId);

              return {
                interviewId,
                feedback: normalizeFeedbackList(res),
              };
            } catch (err) {
              console.error(
                `Failed to fetch feedback for interview ${interviewId}`,
                err,
              );

              return {
                interviewId,
                feedback: [],
              };
            }
          }),
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

              return {
                panelId,
                members,
              };
            } catch (err) {
              console.error(
                `Failed to fetch panel members for panel ${panelId}`,
                err,
              );

              return {
                panelId,
                members: [],
              };
            }
          }),
        ),
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
  }, [candidateId, limitedMode, limitedInterview]);

  useEffect(() => {
    fetchFeedbackData();
  }, [fetchFeedbackData]);

  const interviews = Array.isArray(historyData?.interviews)
    ? historyData.interviews
    : [];

  const feedbackSummary = useMemo(() => {
    const totalInterviews = interviews.length;
    const completedInterviews = interviews.filter((interview) => {
      const interviewId = getInterviewId(interview);
      const feedbackList = feedbackMap[interviewId] || [];
      const panelMembers = panelMembersMap[interview?.panel_id] || [];
      const { doneInterviewerIds } = getFeedbackBreakdown(feedbackList);

      return (
        panelMembers.length > 0 &&
        doneInterviewerIds.size >= panelMembers.length
      );
    }).length;

    let interviewsWithFeedback = 0;
    let totalFeedbackEntries = 0;
    let skippedEntries = 0;

    interviews.forEach((interview) => {
      const interviewId = getInterviewId(interview);
      const list = feedbackMap[interviewId] || [];

      if (list.length > 0) {
        interviewsWithFeedback += 1;
        totalFeedbackEntries += list.length;
        skippedEntries += list.filter(isSkippedFeedback).length;
      }
    });

    return {
      totalInterviews,
      completedInterviews,
      interviewsWithFeedback,
      interviewsWithoutFeedback: Math.max(
        totalInterviews - interviewsWithFeedback,
        0,
      ),
      totalFeedbackEntries,
      skippedEntries,
    };
  }, [interviews, feedbackMap, panelMembersMap]);

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

  const openSkipModal = (interview) => {
    setSelectedInterview(interview);
    setSkipReason("");
    setSkipError("");
    setShowSkipModal(true);
  };

  const closeSkipModal = () => {
    if (submitting) return;

    setShowSkipModal(false);
    setSelectedInterview(null);
    setSkipReason("");
    setSkipError("");
  };

  const completeInterviewIfAllPanelDone = async (
    interview,
    feedbackForm = {},
  ) => {
    const interviewId = getInterviewId(interview);
    const panelMembersRes = await getPanelMembers(interview?.panel_id);

    const panelMembers = Array.isArray(panelMembersRes)
      ? panelMembersRes
      : Array.isArray(panelMembersRes?.members)
        ? panelMembersRes.members
        : Array.isArray(panelMembersRes?.panel_members)
          ? panelMembersRes.panel_members
          : [];

    if (!interviewId || !panelMembers.length) return;

    const latestFeedbackRes = await getFeedbackForInterview(interviewId);
    const latestFeedbackList = normalizeFeedbackList(latestFeedbackRes);
    const { doneInterviewerIds } = getFeedbackBreakdown(latestFeedbackList);

    const allPanelActionsDone = doneInterviewerIds.size >= panelMembers.length;

    if (allPanelActionsDone) {
      await updateInterview(interviewId, {
        status: "Completed",
      });

      const feedbackSummary = latestFeedbackList
        .map((feedback, index) => {
          return `${index + 1}. ${
            feedback?.interviewer_name ||
            feedback?.reviewer_name ||
            feedback?.interviewer_id ||
            "Interviewer"
          }

Recommendation: ${feedback?.recommendation || "N/A"}

Comments:
${feedback?.comments?.trim?.() || "No feedback comments provided."}`;
        })
        .join("\n\n");

      const historyNote = `
Round: ${interview?.panel_round_name || interview?.round_name || "Interview"}

Panel Feedback:

${feedbackSummary}
`.trim();
      try {
        const historyResponse = await createCandidateHistoryEvent(candidateId, {
          event_type: HISTORY_EVENT_TYPES.INTERVIEW_COMPLETED,
          note: historyNote,
          interview_id: interviewId,
          event_at:
            interview?.end_time ||
            interview?.start_time ||
            new Date().toISOString(),
        });
      } catch (historyError) {
        console.error("HISTORY CREATION FAILED", historyError);
      }
    }
  };

  const handleSubmitFeedback = async (form) => {
    const interviewId = getInterviewId(selectedInterview);

    if (!interviewId) {
      setSubmitNotice("Interview is missing");
      setSubmitNoticeType("error");
      return;
    }

    if (!myPanelInterviewMap.has(interviewId)) {
      setSubmitNotice(
        "You are not assigned as a panel member for this interview",
      );
      setSubmitNoticeType("error");
      return;
    }

    try {
      setSubmitting(true);
      setSubmitNotice("");
      setSubmitNoticeType("success");

      await submitInterviewFeedback({
        interviewId,
        interviewerId: form.interviewerId,
        technicalScore: Number(form.technical_score),
        communicationScore: Number(form.communication_score),
        problemSolvingScore: Number(form.problem_solving_score),
        cultureFitScore: Number(form.culture_fit_score),
        comments: form.comments.trim(),
        recommendation: form.recommendation,
      });

      await fetchFeedbackData();
      await completeInterviewIfAllPanelDone(selectedInterview, form);
      setSubmitNotice("Feedback submitted successfully");
      setSubmitNoticeType("success");

      window.setTimeout(() => {
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

  const handleSkipFeedback = async () => {
    const interviewId = getInterviewId(selectedInterview);

    if (!interviewId) {
      setSkipError("Interview is missing");
      return;
    }

    if (!myPanelInterviewMap.has(interviewId)) {
      setSkipError("You are not assigned as a panel member for this interview");
      return;
    }

    if (!loggedInInterviewerId) {
      setSkipError("Logged-in interviewer details are missing");
      return;
    }

    if (!skipReason.trim()) {
      setSkipError("Reason is required");
      return;
    }

    try {
      setSubmitting(true);
      setSkipError("");
      await submitInterviewFeedback({
        interviewId,
        interviewerId: loggedInInterviewerId,
        technicalScore: 0,
        communicationScore: 0,
        problemSolvingScore: 0,
        cultureFitScore: 0,
        comments: `${SKIP_REASON_PREFIX} ${skipReason.trim()}`,
        recommendation: "Not sure",
      });

      await fetchFeedbackData();
      await completeInterviewIfAllPanelDone(selectedInterview);
      closeSkipModal();
    } catch (err) {
      console.error("Failed to skip feedback", err);
      setSkipError(err?.message || "Failed to mark as not attended");
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
            <Stat
              label="Total Interviews"
              value={feedbackSummary.totalInterviews}
            />
            <Stat
              label="Completed"
              value={feedbackSummary.completedInterviews}
            />
            <Stat
              label="With Feedback"
              value={feedbackSummary.interviewsWithFeedback}
            />
            <Stat
              label="Without Feedback"
              value={feedbackSummary.interviewsWithoutFeedback}
            />
            <Stat
              label="Feedback Entries"
              value={feedbackSummary.totalFeedbackEntries}
            />
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
                const interviewId = getInterviewId(interview);
                const feedbackList = feedbackMap[interviewId] || [];
                const myPanelInterview = myPanelInterviewMap.get(interviewId);

                return (
                  <InterviewFeedbackCard
                    key={interviewId}
                    interview={interview}
                    limitedMode={limitedMode}
                    feedbackList={feedbackList}
                    feedbackLoading={feedbackLoading}
                    panelMembers={panelMembersMap[interview.panel_id] || []}
                    myPanelInterview={myPanelInterview}
                    loggedInInterviewerId={loggedInInterviewerId}
                    onSubmitClick={() => openSubmitModal(interview)}
                    onSkipClick={() => openSkipModal(interview)}
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
          limitedMode={limitedMode}
          panelMembers={panelMembersMap[selectedInterview?.panel_id] || []}
          loggedInInterviewerId={loggedInInterviewerId}
          loading={submitting}
          notice={submitNotice}
          noticeType={submitNoticeType}
          onClose={closeSubmitModal}
          onSubmit={handleSubmitFeedback}
        />
      )}

      {showSkipModal && (
        <SkipFeedbackModal
          reason={skipReason}
          error={skipError}
          loading={submitting}
          onReasonChange={(value) => {
            setSkipReason(value);
            setSkipError("");
          }}
          onClose={closeSkipModal}
          onSubmit={handleSkipFeedback}
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
  limitedMode = false,
  feedbackLoading,
  panelMembers = [],
  myPanelInterview,
  loggedInInterviewerId,
  onSubmitClick,
  onSkipClick,
}) {
  const interviewId = getInterviewId(interview);
  const roundName =
    interview?.panel_round_name || interview?.round_name || "Interview Round";
  const startTime = interview?.start_time
    ? formatDateTime(interview.start_time)
    : "-";

  const {
    submittedInterviewerIds,
    skippedInterviewerIds,
    doneInterviewerIds,
    feedbackByInterviewerId,
  } = getFeedbackBreakdown(feedbackList);

  const feedbackProgress = {
    done: doneInterviewerIds.size,
    submitted: submittedInterviewerIds.size,
    skipped: skippedInterviewerIds.size,
    total: panelMembers.length,
  };

  const derivedStatus =
    feedbackProgress.total > 0 &&
    feedbackProgress.done >= feedbackProgress.total
      ? "Completed"
      : feedbackProgress.done > 0
        ? "Pending"
        : interview?.status || "Scheduled";

  const currentUserAlreadyDone =
    Boolean(myPanelInterview?.feedback_submitted) ||
    Boolean(myPanelInterview?.my_feedback) ||
    Boolean(
      loggedInInterviewerId && doneInterviewerIds.has(loggedInInterviewerId),
    );

  const canTakeAction = Boolean(myPanelInterview) && !currentUserAlreadyDone;

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/60 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-base font-semibold text-gray-900">
              {roundName}
            </div>

            <StatusBadge status={derivedStatus} />
          </div>

          <div className="text-sm text-gray-600">{startTime}</div>

          <div className="text-sm text-gray-600">
            Feedback Progress:{" "}
            <span className="font-medium text-gray-800">
              {feedbackProgress.done} / {feedbackProgress.total || 0} done
            </span>
            <span className="ml-2 text-xs text-gray-500">
              ({feedbackProgress.submitted} submitted,{" "}
              {feedbackProgress.skipped} not attended)
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!limitedMode && (
            <div className="text-sm text-gray-500">
              Interview ID: {interviewId || "-"}
            </div>
          )}
          {canTakeAction && (
            <>
              <button
                type="button"
                onClick={onSubmitClick}
                className="inline-flex items-center rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100"
              >
                Submit Feedback
              </button>

              <button
                type="button"
                onClick={onSkipClick}
                className="inline-flex items-center rounded-xl border border-orange-200 bg-orange-50 px-3 py-2 text-sm font-medium text-orange-700 transition hover:bg-orange-100"
              >
                Skip Feedback
              </button>
            </>
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
              const panelFeedback = feedbackByInterviewerId.get(interviewerId);
              const hasSubmitted = submittedInterviewerIds.has(interviewerId);
              const hasSkipped = skippedInterviewerIds.has(interviewerId);

              const statusLabel = hasSkipped
                ? "Not Attended"
                : hasSubmitted
                  ? "Submitted"
                  : "Pending";

              const statusStyles = hasSkipped
                ? "border-orange-200 bg-orange-50 text-orange-700"
                : hasSubmitted
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-yellow-200 bg-yellow-50 text-yellow-700";

              return (
                <div
                  key={`member-${interviewerId || member?.id}`}
                  className={`rounded-lg border px-3 py-2 text-sm ${statusStyles}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">
                      {member?.interviewer_name ||
                        member?.interviewer_email ||
                        "Panel Member"}
                    </span>

                    <span className="text-xs font-semibold">{statusLabel}</span>
                  </div>

                  {hasSkipped && panelFeedback?.comments && (
                    <div className="mt-1 text-xs opacity-80">
                      Reason: {panelFeedback.comments}
                    </div>
                  )}
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
                key={feedback?.id || `${interviewId}-${index}`}
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
  const skipped = isSkippedFeedback(feedback);

  const headerItems = [
    {
      label: "Feedback ID",
      value: feedback?.id,
    },
    {
      label: "Interviewer",
      value:
        feedback?.interviewer_name ||
        feedback?.reviewer_name ||
        feedback?.user_name ||
        feedback?.submitted_by ||
        feedback?.interviewer_id ||
        "-",
    },
    {
      label: "Status",
      value: skipped ? "Not Attended" : "Submitted",
    },
    {
      label: "Recommendation",
      value:
        feedback?.recommendation ||
        feedback?.decision ||
        feedback?.result ||
        "-",
    },
  ];

  const hiddenKeys = [
    "id",
    "interview_id",
    "interviewer_name",
    "reviewer_name",
    "user_name",
    "submitted_by",
    "interviewer_id",
    "recommendation",
    "decision",
    "result",
  ];

  if (skipped) {
    hiddenKeys.push(
      "technical_score",
      "communication_score",
      "problem_solving_score",
      "culture_fit_score",
    );
  }

  const detailEntries = Object.entries(feedback || {}).filter(
    ([key, value]) =>
      !hiddenKeys.includes(key) &&
      value !== null &&
      value !== undefined &&
      value !== "",
  );

  return (
    <div
      className={`rounded-xl border p-4 shadow-sm ${
        skipped ? "border-orange-200 bg-orange-50" : "border-gray-200 bg-white"
      }`}
    >
      <div className="grid gap-3 md:grid-cols-4">
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
                {skipped && key === "comments" ? "Reason" : formatLabel(key)}
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
  limitedMode = false,
  panelMembers,
  loggedInInterviewerId,
  loading,
  notice,
  noticeType,
  onClose,
  onSubmit,
}) {
  const [form, setForm] = useState({
    interviewerId: loggedInInterviewerId || "",
    technical_score: 5,
    communication_score: 5,
    problem_solving_score: 5,
    culture_fit_score: 5,
    comments: "",
    recommendation: "",
    interviewerName: "",
  });

  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (loggedInInterviewerId) {
      const selectedMember = panelMembers.find(
        (member) =>
          String(member?.interviewer_id) === String(loggedInInterviewerId),
      );

      setForm((prev) => ({
        ...prev,
        interviewerId: loggedInInterviewerId,
        interviewerName: selectedMember?.interviewer_name || "Interviewer",
      }));

      return;
    }

    if (panelMembers.length === 1) {
      setForm((prev) => ({
        ...prev,
        interviewerId: panelMembers[0]?.interviewer_id || "",
        interviewerName: panelMembers[0]?.interviewer_name || "Interviewer",
      }));
    }
  }, [loggedInInterviewerId, panelMembers]);

  const handleChange = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));

    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: "",
      }));
    }
  };

  const validate = () => {
    const nextErrors = {};

    if (!form.interviewerId.trim()) {
      nextErrors.interviewerId = "Interviewer is required";
    }

    [
      "technical_score",
      "communication_score",
      "problem_solving_score",
      "culture_fit_score",
    ].forEach((field) => {
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
            <h3 className="text-xl font-semibold text-gray-900">
              Submit Feedback
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Add interview feedback for{" "}
              {interview?.panel_round_name || "this interview"}.
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
            {!limitedMode && (
              <ReadOnlyField
                label="Interview ID"
                value={getInterviewId(interview) || "-"}
              />
            )}
            <ReadOnlyField
              label="Round Name"
              value={
                interview?.panel_round_name || interview?.round_name || "-"
              }
            />

            <SelectField
              label="Interviewer"
              value={form.interviewerId}
              onChange={(e) => {
                const selectedMember = panelMembers.find(
                  (member) =>
                    String(member?.interviewer_id) === String(e.target.value),
                );
                setForm((prev) => ({
                  ...prev,
                  interviewerId: e.target.value,
                  interviewerName:
                    selectedMember?.interviewer_name || "Interviewer",
                }));
              }}
              error={errors.interviewerId}
              disabled={Boolean(loggedInInterviewerId)}
            >
              <option value="">Select interviewer</option>
              {panelMembers.map((member) => (
                <option
                  key={`member-${member?.interviewer_id || member?.id}`}
                  value={member?.interviewer_id || ""}
                >
                  {member?.interviewer_name ||
                    member?.interviewer_email ||
                    "Interviewer"}
                </option>
              ))}
            </SelectField>

            <SelectField
              label="Recommendation"
              value={form.recommendation}
              onChange={(e) => handleChange("recommendation", e.target.value)}
              error={errors.recommendation}
            >
              {recommendationOptions.map((opt) => (
                <option
                  key={`recommendation-${opt.value || "default"}`}
                  value={opt.value}
                >
                  {opt.label}
                </option>
              ))}
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
              onChange={(e) =>
                handleChange("communication_score", e.target.value)
              }
              error={errors.communication_score}
              min="1"
              max="10"
            />

            <FormField
              label="Problem Solving Score"
              type="number"
              value={form.problem_solving_score}
              onChange={(e) =>
                handleChange("problem_solving_score", e.target.value)
              }
              error={errors.problem_solving_score}
              min="1"
              max="10"
            />

            <FormField
              label="Culture Fit Score"
              type="number"
              value={form.culture_fit_score}
              onChange={(e) =>
                handleChange("culture_fit_score", e.target.value)
              }
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

function SkipFeedbackModal({
  reason,
  error,
  loading,
  onReasonChange,
  onClose,
  onSubmit,
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-lg rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">
              Skip Feedback
            </h3>

            <p className="mt-1 text-sm text-gray-500">
              Use this only if you did not attend the interview.
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

        <div className="px-6 py-6 space-y-4">
          {error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Reason <span className="text-red-500">*</span>
            </label>

            <textarea
              rows={5}
              value={reason}
              onChange={(e) => onReasonChange(e.target.value)}
              placeholder="Example: I could not attend due to another scheduled meeting."
              className="w-full rounded-xl border border-gray-300 px-3 py-2.5 text-sm outline-none transition resize-none focus:border-gray-400"
            />
          </div>
        </div>

        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={onSubmit}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-orange-200 bg-orange-50 px-4 py-2 text-sm font-medium text-orange-700 transition hover:bg-orange-100 disabled:opacity-60"
          >
            {loading ? "Saving..." : "Mark as Not Attended"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 text-center">
      <div className="text-2xl font-semibold text-gray-900">{value ?? 0}</div>

      <div className="mt-1 text-xs text-gray-500">{label}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const normalized = String(status || "").toLowerCase();

  let styles = "bg-gray-100 text-gray-700 border-gray-200";

  if (normalized.includes("completed")) {
    styles = "bg-green-50 text-green-700 border-green-200";
  } else if (normalized.includes("pending")) {
    styles = "bg-orange-50 text-orange-700 border-orange-200";
  } else if (normalized.includes("cancel")) {
    styles = "bg-red-50 text-red-700 border-red-200";
  } else if (normalized.includes("scheduled")) {
    styles = "bg-yellow-50 text-yellow-700 border-yellow-200";
  }

  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-xs font-medium ${styles}`}
    >
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
  max,
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

function SelectField({
  label,
  error,
  value,
  onChange,
  children,
  disabled = false,
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>

      <select
        value={value}
        onChange={onChange}
        disabled={disabled}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition bg-white ${
          disabled
            ? "bg-gray-100 text-gray-500 border-gray-200 cursor-not-allowed"
            : error
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
  rows = 4,
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
    minute: "2-digit",
  });
}

function formatLabel(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
