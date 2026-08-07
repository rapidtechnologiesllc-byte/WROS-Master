// Merged "Interviews" tab -- 2026-08-05, replacing the previous separate
// Feedback and Interview (Activity) tabs on CandidateDetailsScreen. Avinash's
// direct feedback: a candidate can interview for N jobs, each with N rounds,
// and the schedule (date/time/status/reschedule/cancel) for a round belongs
// together with that same round's outcome (feedback/recommendation) -- not
// two separately-navigated tabs. Grouped by job (2026-08-05's earlier
// regrouping work), each round now renders as ONE card with both blocks.
//
// FeedbackTab.js is kept unchanged and still used standalone for the
// Hiring-Manager limitedMode single-interview review card (a different,
// narrower context this merge doesn't touch).
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
  deleteInterview,
  getInterviewById,
  getMyInterviews,
} from "../../services/api/interviews";
import {
  deleteInterviewMail,
  sendInterviewInvite,
} from "../../services/api/email";
import { toast } from "react-toastify";

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
  const comments = String(feedback?.comments || "").trim().toLowerCase();
  return comments.startsWith(SKIP_REASON_PREFIX.toLowerCase());
};

const getInterviewId = (interview) => Number(interview?.id ?? interview?.interview_id);

const getFeedbackBreakdown = (feedbackList = []) => {
  const submittedInterviewerIds = new Set();
  const skippedInterviewerIds = new Set();
  const feedbackByInterviewerId = new Map();

  feedbackList.forEach((feedback) => {
    const interviewerId =
      feedback?.interviewer_id || feedback?.interviewer_email || feedback?.interviewer_name;
    if (!interviewerId) return;
    feedbackByInterviewerId.set(interviewerId, feedback);
    if (isSkippedFeedback(feedback)) {
      skippedInterviewerIds.add(interviewerId);
    } else {
      submittedInterviewerIds.add(interviewerId);
    }
  });

  const doneInterviewerIds = new Set([...submittedInterviewerIds, ...skippedInterviewerIds]);
  return { submittedInterviewerIds, skippedInterviewerIds, doneInterviewerIds, feedbackByInterviewerId };
};

export default function InterviewsTab({ candidateId }) {
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

  const [selectedInterviewId, setSelectedInterviewId] = useState(null);
  const [selectedInterviewDetails, setSelectedInterviewDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");

  const [showRescheduleModal, setShowRescheduleModal] = useState(false);
  const [selectedInterviewIdForEdit, setSelectedInterviewIdForEdit] = useState(null);
  const [rescheduleForm, setRescheduleForm] = useState({
    interviewDate: "", startTime: "", endTime: "", durationMinutes: "60", status: "Scheduled", reason: "",
  });
  const [rescheduleErrors, setRescheduleErrors] = useState({});
  const [rescheduling, setRescheduling] = useState(false);
  const [rescheduleNotice, setRescheduleNotice] = useState("");
  const [rescheduleNoticeType, setRescheduleNoticeType] = useState("success");

  const [showCancelModal, setShowCancelModal] = useState(false);
  const [selectedInterviewForCancel, setSelectedInterviewForCancel] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelNotice, setCancelNotice] = useState("");
  const [cancelNoticeType, setCancelNoticeType] = useState("success");

  const fetchData = useCallback(async () => {
    if (!candidateId) return;
    try {
      setLoading(true);
      setError("");
      setFeedbackMap({});
      setPanelMembersMap({});
      setMyPanelInterviewMap(new Map());
      setLoggedInInterviewerId("");

      const [candidateHistoryResult, myInterviewsResult] = await Promise.all([
        getCandidateInterviewHistory(candidateId),
        getMyInterviews(),
      ]);

      setHistoryData(candidateHistoryResult || null);

      const candidateInterviews = Array.isArray(candidateHistoryResult?.interviews)
        ? candidateHistoryResult.interviews
        : [];

      const myInterviews = normalizeMyInterviews(myInterviewsResult);
      const currentLoggedInInterviewerId = myInterviewsResult?.interviewer_id || "";
      setLoggedInInterviewerId(currentLoggedInInterviewerId);

      const nextMyPanelInterviewMap = new Map();
      myInterviews
        .filter((item) => String(item?.candidate_id) === String(candidateId))
        .forEach((item) => {
          const interviewId = Number(item?.interview_id ?? item?.id);
          if (interviewId) nextMyPanelInterviewMap.set(interviewId, item);
        });
      setMyPanelInterviewMap(nextMyPanelInterviewMap);

      if (!candidateInterviews.length) return;

      setFeedbackLoading(true);
      const uniquePanelIds = [...new Set(candidateInterviews.map((i) => i?.panel_id).filter(Boolean))];

      const [feedbackResults, panelResults] = await Promise.all([
        Promise.all(
          candidateInterviews.map(async (interview) => {
            const interviewId = getInterviewId(interview);
            try {
              const res = await getFeedbackForInterview(interviewId);
              return { interviewId, feedback: normalizeFeedbackList(res) };
            } catch (err) {
              console.error(`Failed to fetch feedback for interview ${interviewId}`, err);
              return { interviewId, feedback: [] };
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
              return { panelId, members };
            } catch (err) {
              console.error(`Failed to fetch panel members for panel ${panelId}`, err);
              return { panelId, members: [] };
            }
          }),
        ),
      ]);

      const nextFeedbackMap = {};
      feedbackResults.forEach(({ interviewId, feedback }) => { nextFeedbackMap[interviewId] = feedback; });
      setFeedbackMap(nextFeedbackMap);

      const nextPanelMembersMap = {};
      panelResults.forEach(({ panelId, members }) => { nextPanelMembersMap[panelId] = members; });
      setPanelMembersMap(nextPanelMembersMap);
    } catch (err) {
      console.error("Failed to load interviews tab", err);
      setError(err?.message || "Failed to load interviews");
    } finally {
      setLoading(false);
      setFeedbackLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const interviews = Array.isArray(historyData?.interviews) ? historyData.interviews : [];

  // Grouped by job -- a candidate can interview for more than one job over
  // time; ordered by each job's earliest round so the most recent job
  // pipeline surfaces first, rounds within a job chronological (start_time
  // isn't a reliable ordinal across differently-named rounds).
  const jobGroups = useMemo(() => {
    const byJob = new Map();
    interviews.forEach((interview) => {
      const key = interview?.job_id || "unassigned";
      if (!byJob.has(key)) {
        byJob.set(key, {
          jobId: interview?.job_id || null,
          jobTitle: interview?.job_title || "No job linked",
          rounds: [],
          earliest: interview?.start_time || null,
        });
      }
      const group = byJob.get(key);
      group.rounds.push(interview);
      if (interview?.start_time && (!group.earliest || interview.start_time < group.earliest)) {
        group.earliest = interview.start_time;
      }
    });
    byJob.forEach((group) => {
      group.rounds.sort((a, b) => new Date(a?.start_time || 0) - new Date(b?.start_time || 0));
    });
    return [...byJob.values()].sort((a, b) => new Date(b.earliest || 0) - new Date(a.earliest || 0));
  }, [interviews]);

  const summary = useMemo(() => {
    const totalInterviews = interviews.length;
    const scheduled = interviews.filter((i) => String(i?.status || "").toLowerCase() === "scheduled").length;
    const cancelled = interviews.filter((i) => String(i?.status || "").toLowerCase().includes("cancel")).length;

    const completedInterviews = interviews.filter((interview) => {
      const interviewId = getInterviewId(interview);
      const feedbackList = feedbackMap[interviewId] || [];
      const panelMembers = panelMembersMap[interview?.panel_id] || [];
      const { doneInterviewerIds } = getFeedbackBreakdown(feedbackList);
      return panelMembers.length > 0 && doneInterviewerIds.size >= panelMembers.length;
    }).length;

    let interviewsWithFeedback = 0;
    interviews.forEach((interview) => {
      const interviewId = getInterviewId(interview);
      if ((feedbackMap[interviewId] || []).length > 0) interviewsWithFeedback += 1;
    });

    return {
      totalInterviews, scheduled, cancelled, completedInterviews,
      interviewsWithFeedback,
      interviewsWithoutFeedback: Math.max(totalInterviews - interviewsWithFeedback, 0),
    };
  }, [interviews, feedbackMap, panelMembersMap]);

  // -- Feedback actions --------------------------------------------------
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

  const completeInterviewIfAllPanelDone = async (interview) => {
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

    if (doneInterviewerIds.size >= panelMembers.length) {
      await updateInterview(interviewId, { status: "Completed" });

      const feedbackSummary = latestFeedbackList
        .map((feedback, index) => `${index + 1}. ${
          feedback?.interviewer_name || feedback?.reviewer_name || feedback?.interviewer_id || "Interviewer"
        }\n\nRecommendation: ${feedback?.recommendation || "N/A"}\n\nComments:\n${feedback?.comments?.trim?.() || "No feedback comments provided."}`)
        .join("\n\n");

      const historyNote = `Round: ${interview?.panel_round_name || interview?.round_name || "Interview"}\n\nPanel Feedback:\n\n${feedbackSummary}`.trim();
      try {
        await createCandidateHistoryEvent(candidateId, {
          event_type: HISTORY_EVENT_TYPES.INTERVIEW_COMPLETED,
          note: historyNote,
          interview_id: interviewId,
          event_at: interview?.end_time || interview?.start_time || new Date().toISOString(),
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
      setSubmitNotice("You are not assigned as a panel member for this interview");
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
      await fetchData();
      await completeInterviewIfAllPanelDone(selectedInterview);
      setSubmitNotice("Feedback submitted successfully");
      setSubmitNoticeType("success");
      window.setTimeout(() => closeSubmitModal(), 1000);
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
      await fetchData();
      await completeInterviewIfAllPanelDone(selectedInterview);
      closeSkipModal();
    } catch (err) {
      console.error("Failed to skip feedback", err);
      setSkipError(err?.message || "Failed to mark as not attended");
    } finally {
      setSubmitting(false);
    }
  };

  // -- Schedule actions ----------------------------------------------------
  const openDetailsModal = async (interviewId) => {
    setSelectedInterviewId(interviewId);
    setDetailsError("");
    setDetailsLoading(true);
    setSelectedInterviewDetails(null);
    try {
      const res = await getInterviewById(interviewId);
      setSelectedInterviewDetails(res);
    } catch (err) {
      console.error("Failed to fetch interview details", err);
      setDetailsError("Failed to load interview details");
    } finally {
      setDetailsLoading(false);
    }
  };
  const closeDetailsModal = () => {
    setSelectedInterviewId(null);
    setSelectedInterviewDetails(null);
    setDetailsError("");
  };

  const openRescheduleModal = (interview) => {
    const start = safeDate(interview?.start_time);
    const end = safeDate(interview?.end_time);
    setSelectedInterview(interview);
    setSelectedInterviewIdForEdit(interview?.id ?? null);
    setRescheduleErrors({});
    setRescheduleNotice("");
    setRescheduleNoticeType("success");
    setRescheduleForm({
      interviewDate: start ? formatDateInput(start) : "",
      startTime: start ? formatTimeInput(start) : "",
      endTime: end ? formatTimeInput(end) : "",
      durationMinutes: getDurationMinutes(interview?.start_time, interview?.end_time),
      status: interview?.status || "Scheduled",
      reason: "",
    });
    setShowRescheduleModal(true);
  };
  const closeRescheduleModal = () => {
    if (rescheduling) return;
    setShowRescheduleModal(false);
    setSelectedInterview(null);
    setSelectedInterviewIdForEdit(null);
    setRescheduleForm({ interviewDate: "", startTime: "", endTime: "", durationMinutes: "60", status: "Scheduled", reason: "" });
    setRescheduleErrors({});
    setRescheduleNotice("");
    setRescheduleNoticeType("success");
  };

  useEffect(() => {
    if (!showRescheduleModal) return;
    if (!rescheduleForm.startTime || !rescheduleForm.durationMinutes) return;
    const calculatedEndTime = addMinutesToTime(rescheduleForm.startTime, Number(rescheduleForm.durationMinutes));
    setRescheduleForm((prev) => (prev.endTime === calculatedEndTime ? prev : { ...prev, endTime: calculatedEndTime }));
  }, [showRescheduleModal, rescheduleForm.startTime, rescheduleForm.durationMinutes]);

  const handleRescheduleInputChange = (field, value) => {
    setRescheduleForm((prev) => {
      const updated = { ...prev, [field]: value };
      if (field === "interviewDate" || field === "startTime" || field === "durationMinutes") {
        updated.endTime = addMinutesToTime(
          field === "startTime" ? value : updated.startTime,
          Number(field === "durationMinutes" ? value : updated.durationMinutes),
        );
      }
      return updated;
    });
    if (rescheduleErrors[field]) setRescheduleErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const validateRescheduleForm = () => {
    const errors = {};
    if (!rescheduleForm.interviewDate) errors.interviewDate = "Interview date is required";
    if (!rescheduleForm.startTime) errors.startTime = "Start time is required";
    if (!rescheduleForm.endTime) errors.endTime = "End time is required";
    if (!rescheduleForm.status) errors.status = "Status is required";
    const start = new Date(`${rescheduleForm.interviewDate}T${rescheduleForm.startTime}`);
    const end = new Date(`${rescheduleForm.interviewDate}T${rescheduleForm.endTime}`);
    if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && end.getTime() <= start.getTime()) {
      end.setDate(end.getDate() + 1);
    }
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      errors.startTime = "Please provide valid interview timing";
    }
    setRescheduleErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleRescheduleInterview = async () => {
    if (!selectedInterviewIdForEdit) {
      setRescheduleNotice("Interview ID is missing");
      setRescheduleNoticeType("error");
      return;
    }
    if (!selectedInterview?.panel_id || !selectedInterview?.candidate_id) {
      setRescheduleNotice("Interview data is incomplete");
      setRescheduleNoticeType("error");
      return;
    }
    if (!validateRescheduleForm()) return;
    try {
      setRescheduling(true);
      setRescheduleNotice("");
      setRescheduleNoticeType("success");
      await deleteInterviewMail(selectedInterviewIdForEdit, rescheduleForm?.reason);

      const end = new Date(`${rescheduleForm.interviewDate}T${rescheduleForm.endTime}`);
      const start = new Date(`${rescheduleForm.interviewDate}T${rescheduleForm.startTime}`);
      if (end.getTime() <= start.getTime()) end.setDate(end.getDate() + 1);
      const updatedStart = `${rescheduleForm.interviewDate}T${rescheduleForm.startTime}:00`;
      const endDate = [end.getFullYear(), String(end.getMonth() + 1).padStart(2, "0"), String(end.getDate()).padStart(2, "0")].join("-");
      const updatedEnd = `${endDate}T${rescheduleForm.endTime}:00`;

      const payload = {
        panel_id: selectedInterview.panel_id,
        candidate_id: selectedInterview.candidate_id,
        start_time: updatedStart,
        end_time: updatedEnd,
        meeting_link: selectedInterview.meeting_link || "",
        outlook_event_id: selectedInterview.outlook_event_id || "",
        status: rescheduleForm.status,
      };
      const updatedInterviewApi = await updateInterview(selectedInterviewIdForEdit, payload);
      if (updatedInterviewApi?.response?.status === 200) {
        const sendInvite = await sendInterviewInvite({ interviewId: selectedInterviewIdForEdit });
        if (sendInvite?.status === "success") {
          toast.success("Interview rescheduled successfully");
          await fetchData();
        }
      }
      setRescheduling(false);
      closeRescheduleModal();
    } catch (err) {
      console.error("Failed to reschedule interview", err);
      toast.error("Failed to reschedule interview");
      setRescheduleNoticeType("error");
      setRescheduling(false);
    }
  };

  const openCancelModal = (interview) => {
    setSelectedInterviewForCancel(interview);
    setCancelNotice("");
    setCancelNoticeType("success");
    setShowCancelModal(true);
  };
  const closeCancelModal = () => {
    if (cancelling) return;
    setShowCancelModal(false);
    setSelectedInterviewForCancel(null);
    setCancelNotice("");
    setCancelNoticeType("success");
  };
  const handleCancelInterview = async () => {
    if (!selectedInterviewForCancel?.id) {
      setCancelNotice("Interview ID is missing");
      setCancelNoticeType("error");
      return;
    }
    try {
      setCancelling(true);
      setCancelNotice("");
      setCancelNoticeType("success");
      const deleteMail = await deleteInterviewMail(selectedInterviewForCancel.id, rescheduleForm?.reason);
      if (deleteMail?.status === "success") {
        await deleteInterview(selectedInterviewForCancel.id);
      }
      await fetchData();
      toast.success("Interview cancelled successfully");
      setCancelNoticeType("success");
      setCancelling(false);
      closeCancelModal();
    } catch (err) {
      console.error("Failed to cancel interview", err);
      toast.error("Failed to cancel interview");
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <SectionCard title="Summary">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
            {Array.from({ length: 6 }).map((_, index) => <StatSkeleton key={index} />)}
          </div>
        </SectionCard>
        <SectionCard title="Interviews">
          <RoundSkeletonCard />
          <RoundSkeletonCard />
        </SectionCard>
      </div>
    );
  }

  if (error) {
    return <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">{error}</div>;
  }

  if (!historyData) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center text-gray-500">
        No interview data available
      </div>
    );
  }

  return (
    <>
      <div className="space-y-6">
        <SectionCard title="Summary">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-6">
            <Stat label="Total Interviews" value={summary.totalInterviews} />
            <Stat label="Scheduled" value={summary.scheduled} />
            <Stat label="Completed" value={summary.completedInterviews} />
            <Stat label="Cancelled" value={summary.cancelled} />
            <Stat label="With Feedback" value={summary.interviewsWithFeedback} />
            <Stat label="Without Feedback" value={summary.interviewsWithoutFeedback} />
          </div>
        </SectionCard>

        <SectionCard title="Interviews by Job">
          {!interviews.length ? (
            <EmptyState
              title="No interview activity yet"
              subtitle="Once an interview is scheduled for this candidate, its schedule and feedback will appear here together."
            />
          ) : (
            <div className="space-y-6">
              {jobGroups.map((group) => (
                <div key={group.jobId || "unassigned"}>
                  <div className="mb-2 flex items-center gap-2">
                    <div className="text-sm font-bold text-bx-navy">{group.jobTitle}</div>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
                      {group.rounds.length} round{group.rounds.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="space-y-4 border-l-2 border-gray-100 pl-4">
                    {group.rounds.map((interview) => {
                      const interviewId = getInterviewId(interview);
                      return (
                        <InterviewRoundCard
                          key={interviewId}
                          interview={interview}
                          feedbackList={feedbackMap[interviewId] || []}
                          feedbackLoading={feedbackLoading}
                          panelMembers={panelMembersMap[interview.panel_id] || []}
                          myPanelInterview={myPanelInterviewMap.get(interviewId)}
                          loggedInInterviewerId={loggedInInterviewerId}
                          onSubmitClick={() => openSubmitModal(interview)}
                          onSkipClick={() => openSkipModal(interview)}
                          onViewDetails={() => openDetailsModal(interviewId)}
                          onReschedule={() => openRescheduleModal(interview)}
                          onCancel={() => openCancelModal(interview)}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      {showSubmitModal && (
        <SubmitFeedbackModal
          interview={selectedInterview}
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
          onReasonChange={(value) => { setSkipReason(value); setSkipError(""); }}
          onClose={closeSkipModal}
          onSubmit={handleSkipFeedback}
        />
      )}

      {selectedInterviewId && (
        <InterviewDetailsModal
          open={!!selectedInterviewId}
          onClose={closeDetailsModal}
          loading={detailsLoading}
          error={detailsError}
          interview={selectedInterviewDetails}
          panelMembers={
            panelMembersMap[selectedInterviewDetails?.panel_id]
            || panelMembersMap[interviews.find((item) => item.id === selectedInterviewId)?.panel_id]
            || []
          }
        />
      )}

      {showRescheduleModal && (
        <RescheduleModal
          interview={selectedInterview}
          form={rescheduleForm}
          errors={rescheduleErrors}
          notice={rescheduleNotice}
          noticeType={rescheduleNoticeType}
          loading={rescheduling}
          onChange={handleRescheduleInputChange}
          onClose={closeRescheduleModal}
          onSubmit={handleRescheduleInterview}
        />
      )}

      {showCancelModal && (
        <CancelInterviewModal
          interview={selectedInterviewForCancel}
          notice={cancelNotice}
          noticeType={cancelNoticeType}
          loading={cancelling}
          onClose={closeCancelModal}
          onConfirm={handleCancelInterview}
        />
      )}
    </>
  );
}

function SectionCard({ title, children }) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-500 mb-4 uppercase tracking-wide">{title}</h3>
      {children}
    </section>
  );
}

function InterviewRoundCard({
  interview,
  feedbackList,
  feedbackLoading,
  panelMembers = [],
  myPanelInterview,
  loggedInInterviewerId,
  onSubmitClick,
  onSkipClick,
  onViewDetails,
  onReschedule,
  onCancel,
}) {
  const interviewId = getInterviewId(interview);
  const roundName = interview?.panel_round_name || interview?.round_name || "Interview Round";
  const dateLabel = formatDate(interview?.start_time);
  const startLabel = formatTime(interview?.start_time);
  const endLabel = formatTime(interview?.end_time);
  const meetingLink = interview?.meeting_link || "";
  const isOnline = Boolean(meetingLink);

  const { submittedInterviewerIds, skippedInterviewerIds, doneInterviewerIds, feedbackByInterviewerId } =
    getFeedbackBreakdown(feedbackList);

  const feedbackProgress = {
    done: doneInterviewerIds.size,
    submitted: submittedInterviewerIds.size,
    skipped: skippedInterviewerIds.size,
    total: panelMembers.length,
  };

  const derivedStatus =
    feedbackProgress.total > 0 && feedbackProgress.done >= feedbackProgress.total
      ? "Completed"
      : interview?.status || "Scheduled";

  const currentUserAlreadyDone =
    Boolean(myPanelInterview?.feedback_submitted) ||
    Boolean(myPanelInterview?.my_feedback) ||
    Boolean(loggedInInterviewerId && doneInterviewerIds.has(loggedInInterviewerId));
  const canTakeAction = Boolean(myPanelInterview) && !currentUserAlreadyDone;

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/60 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-base font-semibold text-gray-900">{roundName}</div>
            <StatusBadge status={derivedStatus} />
          </div>
          <div className="grid gap-1 text-sm text-gray-600 sm:grid-cols-2">
            <div><span className="font-medium text-gray-800">Date:</span> {dateLabel}</div>
            <div><span className="font-medium text-gray-800">Time:</span> {startLabel} - {endLabel}</div>
            <div><span className="font-medium text-gray-800">Duration:</span> {calculateDuration(interview?.start_time, interview?.end_time)}</div>
            <div><span className="font-medium text-gray-800">Mode:</span> {isOnline ? "Online Interview" : "Offline / TBD"}</div>
          </div>
          <div className="text-sm text-gray-600">
            Feedback Progress: <span className="font-medium text-gray-800">{feedbackProgress.done} / {feedbackProgress.total || 0} done</span>
            <span className="ml-2 text-xs text-gray-500">({feedbackProgress.submitted} submitted, {feedbackProgress.skipped} not attended)</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={onViewDetails} className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">
            View Details
          </button>
          <button type="button" onClick={onReschedule} className="inline-flex items-center rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100">
            Reschedule
          </button>
          <button type="button" onClick={onCancel} className="inline-flex items-center rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100">
            Cancel
          </button>
          {meetingLink ? (
            <a href={meetingLink} target="_blank" rel="noreferrer" className="inline-flex items-center rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100">
              Join Meeting
            </a>
          ) : null}
          {canTakeAction && (
            <>
              <button type="button" onClick={onSubmitClick} className="inline-flex items-center rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100">
                Submit Feedback
              </button>
              <button type="button" onClick={onSkipClick} className="inline-flex items-center rounded-xl border border-orange-200 bg-orange-50 px-3 py-2 text-sm font-medium text-orange-700 transition hover:bg-orange-100">
                Skip Feedback
              </button>
            </>
          )}
        </div>
      </div>

      {panelMembers.length > 0 && (
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Panel Feedback Status</div>
          <div className="grid gap-2 md:grid-cols-2">
            {panelMembers.map((member) => {
              const interviewerId = member?.interviewer_id;
              const panelFeedback = feedbackByInterviewerId.get(interviewerId);
              const hasSubmitted = submittedInterviewerIds.has(interviewerId);
              const hasSkipped = skippedInterviewerIds.has(interviewerId);
              const statusLabel = hasSkipped ? "Not Attended" : hasSubmitted ? "Submitted" : "Pending";
              const statusStyles = hasSkipped
                ? "border-orange-200 bg-orange-50 text-orange-700"
                : hasSubmitted
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-yellow-200 bg-yellow-50 text-yellow-700";
              const roleAndBU = [member?.interviewer_role, member?.business_unit_name]
                .filter(Boolean)
                .join(" • ") || "";
              return (
                <div key={`member-${interviewerId || member?.id}`} className={`rounded-lg border px-3 py-2 text-sm ${statusStyles}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{member?.interviewer_name || member?.interviewer_email || "Panel Member"}</div>
                      {roleAndBU && <div className="text-xs opacity-75">{roleAndBU}</div>}
                    </div>
                    <span className="text-xs font-semibold">{statusLabel}</span>
                  </div>
                  {hasSkipped && panelFeedback?.comments && (
                    <div className="mt-1 text-xs opacity-80">Reason: {panelFeedback.comments}</div>
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
              <FeedbackEntryCard key={feedback?.id || `${interviewId}-${index}`} feedback={feedback} />
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
    { label: "Feedback ID", value: feedback?.id },
    { label: "Interviewer", value: feedback?.interviewer_name || feedback?.reviewer_name || feedback?.user_name || feedback?.submitted_by || feedback?.interviewer_id || "-" },
    { label: "Status", value: skipped ? "Not Attended" : "Submitted" },
    { label: "Recommendation", value: feedback?.recommendation || feedback?.decision || feedback?.result || "-" },
  ];
  const hiddenKeys = ["id", "interview_id", "interviewer_name", "reviewer_name", "user_name", "submitted_by", "interviewer_id", "recommendation", "decision", "result"];
  if (skipped) hiddenKeys.push("technical_score", "communication_score", "problem_solving_score", "culture_fit_score");
  const detailEntries = Object.entries(feedback || {}).filter(([key, value]) => !hiddenKeys.includes(key) && value !== null && value !== undefined && value !== "");

  return (
    <div className={`rounded-xl border p-4 shadow-sm ${skipped ? "border-orange-200 bg-orange-50" : "border-gray-200 bg-white"}`}>
      <div className="grid gap-3 md:grid-cols-4">
        {headerItems.map((item) => (
          <div key={item.label}>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{item.label}</div>
            <div className="text-sm text-gray-800 break-words">{String(item.value ?? "-")}</div>
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
              <div className="text-sm text-gray-800 break-words">{String(value)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PanelMembers({ members }) {
  if (!members?.length) {
    return (
      <div className="mt-3">
        <div className="text-xs font-semibold text-gray-500 mb-2">Panel Members</div>
        <div className="text-sm text-gray-500">No panel members available</div>
      </div>
    );
  }
  return (
    <div className="mt-3">
      <div className="text-xs font-semibold text-gray-500 mb-2">Panel Members</div>
      <div className="flex flex-wrap gap-2">
        {members.map((member, index) => {
          const label = member?.interviewer_name || member?.user_name || member?.name || `Member ${index + 1}`;
          const roleAndBU = [member?.interviewer_role, member?.business_unit_name]
            .filter(Boolean)
            .join(" • ") || "";
          const fullLabel = roleAndBU ? `${label} (${roleAndBU})` : label;
          return (
            <span key={member?.id || member?.interviewer_id || `${label}-${index}`} className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">
              {fullLabel}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function InterviewDetailsModal({ open, onClose, loading, error, interview, panelMembers }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-3xl rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Interview Details</h3>
            <p className="mt-1 text-sm text-gray-500">View complete interview information for this candidate.</p>
          </div>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        <div className="max-h-[75vh] overflow-y-auto px-6 py-6">
          {loading && <div className="space-y-4"><RoundSkeletonCard /><RoundSkeletonCard /></div>}
          {!loading && error && <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          {!loading && !error && interview && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-lg font-semibold text-gray-900">{interview?.panel_round_name || "Interview"}</h4>
                  <StatusBadge status={interview?.status || "Scheduled"} />
                </div>
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <DetailRow label="Interview ID" value={interview?.id} />
                  <DetailRow label="Panel ID" value={interview?.panel_id} />
                  <DetailRow label="Candidate Name" value={interview?.candidate_name} />
                  <DetailRow label="Candidate Email" value={interview?.candidate_email} />
                  <DetailRow label="Date" value={formatDate(interview?.start_time)} />
                  <DetailRow label="Time" value={`${formatTime(interview?.start_time)} - ${formatTime(interview?.end_time)}`} />
                  <DetailRow label="Feedback Count" value={interview?.feedback_count ?? 0} />
                  <DetailRow label="Mode" value={interview?.meeting_link ? "Online Interview" : "Offline / TBD"} />
                </div>
              </div>
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <div className="text-sm font-semibold text-gray-900 mb-3">Panel Members</div>
                <PanelMembers members={panelMembers} />
              </div>
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
                <div className="text-sm font-semibold text-gray-900">Meeting Information</div>
                <DetailRow
                  label="Meeting Link"
                  value={interview?.meeting_link ? (
                    <a href={interview.meeting_link} target="_blank" rel="noreferrer" className="text-blue-600 underline break-all">{interview.meeting_link}</a>
                  ) : "Not available"}
                />
                <DetailRow label="Outlook Event ID" value={interview?.outlook_event_id || "Not available"} />
              </div>
            </div>
          )}
        </div>
        <div className="border-t bg-white px-6 py-4 flex justify-end">
          <button type="button" onClick={onClose} className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">Close</button>
        </div>
      </div>
    </div>
  );
}

function RescheduleModal({ interview, form, errors, notice, noticeType, loading, onChange, onClose, onSubmit }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-2xl rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Reschedule Interview</h3>
            <p className="mt-1 text-sm text-gray-500">Update interview timing for {interview?.panel_round_name || "this interview"}.</p>
          </div>
          <button type="button" onClick={onClose} disabled={loading} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        <div className="px-6 py-6 space-y-5">
          {notice && (
            <div className={`rounded-2xl border px-4 py-3 text-sm ${noticeType === "error" ? "border-red-200 bg-red-50 text-red-700" : "border-green-200 bg-green-50 text-green-700"}`}>{notice}</div>
          )}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <ReadOnlyField label="Interview ID" value={interview?.id || "-"} />
            <ReadOnlyField label="Round Name" value={interview?.panel_round_name || "-"} />
            <FormField label="Interview Date" type="date" value={form.interviewDate} onChange={(e) => onChange("interviewDate", e.target.value)} error={errors.interviewDate} />
            <ReadOnlyField label="Status" value={form.status || "-"} />
            <SelectField label="Duration" value={form.durationMinutes} onChange={(e) => onChange("durationMinutes", e.target.value)}>
              {[30, 45, 60, 90, 120].map((minutes) => <option key={minutes} value={String(minutes)}>{formatDurationLabel(minutes)}</option>)}
            </SelectField>
            <FormField label="Start Time" type="time" value={form.startTime} onChange={(e) => onChange("startTime", e.target.value)} error={errors.startTime} />
            <FormField label="End Time" type="time" value={form.endTime} readOnly error={errors.endTime} />
            <FormField label="Add reason" type="textarea" value={form.reason} onChange={(e) => onChange("reason", e?.target?.value)} error={errors.reason} />
          </div>
        </div>
        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={loading} className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">Close</button>
          <button type="button" onClick={onSubmit} disabled={loading} className="inline-flex items-center rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100 disabled:opacity-60">
            {loading ? "Updating..." : "Update Interview"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CancelInterviewModal({ interview, notice, noticeType, loading, onClose, onConfirm }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-lg rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Cancel Interview</h3>
            <p className="mt-1 text-sm text-gray-500">This will remove the interview from the current interview flow.</p>
          </div>
          <button type="button" onClick={onClose} disabled={loading} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        <div className="px-6 py-6 space-y-5">
          {notice && (
            <div className={`rounded-2xl border px-4 py-3 text-sm ${noticeType === "error" ? "border-red-200 bg-red-50 text-red-700" : "border-green-200 bg-green-50 text-green-700"}`}>{notice}</div>
          )}
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
            <div className="text-sm text-gray-700">Are you sure you want to cancel this interview?</div>
            <div className="mt-4 grid gap-3">
              <DetailRow label="Interview ID" value={interview?.id || "-"} />
              <DetailRow label="Round Name" value={interview?.panel_round_name || "-"} />
              <DetailRow label="Date" value={formatDate(interview?.start_time)} />
              <DetailRow label="Time" value={`${formatTime(interview?.start_time)} - ${formatTime(interview?.end_time)}`} />
            </div>
          </div>
        </div>
        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={loading} className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">Close</button>
          <button type="button" onClick={onConfirm} disabled={loading} className="inline-flex items-center rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:opacity-60">
            {loading ? "Cancelling..." : "Confirm Cancel"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SubmitFeedbackModal({ interview, panelMembers, loggedInInterviewerId, loading, notice, noticeType, onClose, onSubmit }) {
  const [form, setForm] = useState({
    interviewerId: loggedInInterviewerId || "",
    technical_score: 5, communication_score: 5, problem_solving_score: 5, culture_fit_score: 5,
    comments: "", recommendation: "", interviewerName: "",
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (loggedInInterviewerId) {
      const selectedMember = panelMembers.find((member) => String(member?.interviewer_id) === String(loggedInInterviewerId));
      setForm((prev) => ({ ...prev, interviewerId: loggedInInterviewerId, interviewerName: selectedMember?.interviewer_name || "Interviewer" }));
      return;
    }
    if (panelMembers.length === 1) {
      setForm((prev) => ({ ...prev, interviewerId: panelMembers[0]?.interviewer_id || "", interviewerName: panelMembers[0]?.interviewer_name || "Interviewer" }));
    }
  }, [loggedInInterviewerId, panelMembers]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const validate = () => {
    const nextErrors = {};
    if (!form.interviewerId.trim()) nextErrors.interviewerId = "Interviewer is required";
    ["technical_score", "communication_score", "problem_solving_score", "culture_fit_score"].forEach((field) => {
      const value = Number(form[field]);
      if (Number.isNaN(value) || value < 1 || value > 10) nextErrors[field] = "Score must be between 1 and 10";
    });
    if (!form.comments.trim()) nextErrors.comments = "Comments are required";
    if (!form.recommendation.trim()) nextErrors.recommendation = "Recommendation is required";
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
            <p className="mt-1 text-sm text-gray-500">Add interview feedback for {interview?.panel_round_name || "this interview"}.</p>
          </div>
          <button type="button" onClick={onClose} disabled={loading} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        <div className="px-6 py-6 space-y-5">
          {notice && (
            <div className={`rounded-2xl border px-4 py-3 text-sm ${noticeType === "error" ? "border-red-200 bg-red-50 text-red-700" : "border-green-200 bg-green-50 text-green-700"}`}>{notice}</div>
          )}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <ReadOnlyField label="Interview ID" value={getInterviewId(interview) || "-"} />
            <ReadOnlyField label="Round Name" value={interview?.panel_round_name || interview?.round_name || "-"} />
            <SelectField
              label="Interviewer"
              value={form.interviewerId}
              onChange={(e) => {
                const selectedMember = panelMembers.find((member) => String(member?.interviewer_id) === String(e.target.value));
                setForm((prev) => ({ ...prev, interviewerId: e.target.value, interviewerName: selectedMember?.interviewer_name || "Interviewer" }));
              }}
              error={errors.interviewerId}
              disabled={Boolean(loggedInInterviewerId)}
            >
              <option value="">Select interviewer</option>
              {panelMembers.map((member) => (
                <option key={`member-${member?.interviewer_id || member?.id}`} value={member?.interviewer_id || ""}>
                  {member?.interviewer_name || member?.interviewer_email || "Interviewer"}
                </option>
              ))}
            </SelectField>
            <SelectField label="Recommendation" value={form.recommendation} onChange={(e) => handleChange("recommendation", e.target.value)} error={errors.recommendation}>
              {recommendationOptions.map((opt) => <option key={`recommendation-${opt.value || "default"}`} value={opt.value}>{opt.label}</option>)}
            </SelectField>
            <FormField label="Technical Score" type="number" value={form.technical_score} onChange={(e) => handleChange("technical_score", e.target.value)} error={errors.technical_score} min="1" max="10" />
            <FormField label="Communication Score" type="number" value={form.communication_score} onChange={(e) => handleChange("communication_score", e.target.value)} error={errors.communication_score} min="1" max="10" />
            <FormField label="Problem Solving Score" type="number" value={form.problem_solving_score} onChange={(e) => handleChange("problem_solving_score", e.target.value)} error={errors.problem_solving_score} min="1" max="10" />
            <FormField label="Culture Fit Score" type="number" value={form.culture_fit_score} onChange={(e) => handleChange("culture_fit_score", e.target.value)} error={errors.culture_fit_score} min="1" max="10" />
          </div>
          <TextAreaField label="Comments" value={form.comments} onChange={(e) => handleChange("comments", e.target.value)} error={errors.comments} placeholder="Enter feedback comments" rows={5} />
        </div>
        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={loading} className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">Close</button>
          <button type="button" onClick={handleSubmit} disabled={loading} className="inline-flex items-center rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100 disabled:opacity-60">
            {loading ? "Submitting..." : "Submit Feedback"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SkipFeedbackModal({ reason, error, loading, onReasonChange, onClose, onSubmit }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-lg rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Skip Feedback</h3>
            <p className="mt-1 text-sm text-gray-500">Use this only if you did not attend the interview.</p>
          </div>
          <button type="button" onClick={onClose} disabled={loading} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>
        <div className="px-6 py-6 space-y-4">
          {error && <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Reason <span className="text-red-500">*</span></label>
            <textarea rows={5} value={reason} onChange={(e) => onReasonChange(e.target.value)} placeholder="Example: I could not attend due to another scheduled meeting." className="w-full rounded-xl border border-gray-300 px-3 py-2.5 text-sm outline-none transition resize-none focus:border-gray-400" />
          </div>
        </div>
        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={loading} className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">Cancel</button>
          <button type="button" onClick={onSubmit} disabled={loading} className="inline-flex items-center rounded-xl border border-orange-200 bg-orange-50 px-4 py-2 text-sm font-medium text-orange-700 transition hover:bg-orange-100 disabled:opacity-60">
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
  if (normalized.includes("completed")) styles = "bg-green-50 text-green-700 border-green-200";
  else if (normalized.includes("pending")) styles = "bg-orange-50 text-orange-700 border-orange-200";
  else if (normalized.includes("cancel")) styles = "bg-red-50 text-red-700 border-red-200";
  else if (normalized.includes("resched")) styles = "bg-amber-50 text-amber-700 border-amber-200";
  else if (normalized.includes("scheduled")) styles = "bg-yellow-50 text-yellow-700 border-yellow-200";
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${styles}`}>{status}</span>;
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

function RoundSkeletonCard() {
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
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <div className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-700">{value}</div>
    </div>
  );
}

function FormField({ label, error, type = "text", value, onChange, placeholder, min, max, readOnly }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        min={min}
        max={max}
        readOnly={readOnly}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition ${error ? "border-red-300 focus:border-red-400" : "border-gray-300 focus:border-gray-400"}`}
      />
      {error ? <p className="mt-1 text-xs text-red-500">{error}</p> : null}
    </div>
  );
}

function SelectField({ label, error, value, onChange, children, disabled = false }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <select
        value={value}
        onChange={onChange}
        disabled={disabled}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition bg-white ${
          disabled ? "bg-gray-100 text-gray-500 border-gray-200 cursor-not-allowed" : error ? "border-red-300 focus:border-red-400" : "border-gray-300 focus:border-gray-400"
        }`}
      >
        {children}
      </select>
      {error ? <p className="mt-1 text-xs text-red-500">{error}</p> : null}
    </div>
  );
}

function TextAreaField({ label, error, value, onChange, placeholder, rows = 4 }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <textarea
        rows={rows}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition resize-none ${error ? "border-red-300 focus:border-red-400" : "border-gray-300 focus:border-gray-400"}`}
      />
      {error ? <p className="mt-1 text-xs text-red-500">{error}</p> : null}
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{label}</div>
      <div className="text-sm text-gray-800 break-words">{value || "-"}</div>
    </div>
  );
}

function safeDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function formatDateInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatTimeInput(date) {
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}

function addMinutesToTime(timeValue, minutesToAdd) {
  if (!timeValue || !Number.isFinite(Number(minutesToAdd))) return "";
  const [hours, minutes] = String(timeValue).split(":").map(Number);
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return "";
  const totalMinutes = hours * 60 + minutes + Number(minutesToAdd);
  const normalizedMinutes = ((totalMinutes % 1440) + 1440) % 1440;
  const nextHours = Math.floor(normalizedMinutes / 60);
  const nextMinutes = normalizedMinutes % 60;
  return `${String(nextHours).padStart(2, "0")}:${String(nextMinutes).padStart(2, "0")}`;
}

function getDurationMinutes(startValue, endValue) {
  const start = safeDate(startValue);
  const end = safeDate(endValue);
  if (!start || !end) return "60";
  const diff = Math.round((end.getTime() - start.getTime()) / 60000);
  return String(diff > 0 ? diff : 60);
}

function formatDurationLabel(value) {
  const map = { 30: "30 min", 45: "45 min", 60: "1 hour", 90: "1.5 hour", 120: "2 hour" };
  return map[value] || `${value} min`;
}

function calculateDuration(start, end) {
  if (!start || !end) return "-";
  const s = new Date(start);
  const e = new Date(end);
  const diff = Math.round((e - s) / 60000);
  if (diff === 30) return "30 min";
  if (diff === 45) return "45 min";
  if (diff === 60) return "1 hour";
  if (diff === 90) return "1.5 hour";
  if (diff === 120) return "2 hour";
  return `${diff} min`;
}

function formatLabel(key) {
  return String(key).replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
