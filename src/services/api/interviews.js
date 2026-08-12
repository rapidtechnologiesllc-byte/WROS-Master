// Interview management API wrappers.
import { apiRequest } from "./client";

export const createInterviewPanel = async ({
  candidateId,
  roundName,
  jobId,
  rehireJustification,
}) => {
  const { data } = await apiRequest("/interviews/panels/create", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: candidateId,
      round_name: roundName,
      job_id: jobId,
      rehire_justification: rehireJustification || undefined,
    }),
  });
  return data;
};

// Rehire guard -- pending hiring-manager queue + decision.
export const getRehireReviews = async () => {
  const { data } = await apiRequest("/interviews/rehire-reviews");
  return data;
};

export const decideRehireReview = async ({ reviewId, decision, note }) => {
  const { data } = await apiRequest(
    `/interviews/rehire-reviews/${reviewId}/decide`,
    {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    },
  );
  return data;
};

export const assignPanelMember = async ({ panelId, interviewerId }) => {
  const { data } = await apiRequest("/interviews/panel-members/assign", {
    method: "POST",
    body: JSON.stringify({
      panel_id: panelId,
      interviewer_id: interviewerId,
    }),
  });
  return data;
};

export const createInterview = async ({
  panelId,
  candidateId,
  startTime,
  endTime,
  meetingLink,
  outlookEventId,
  status,
}) => {
  const { data } = await apiRequest("/interviews/create", {
    method: "POST",
    body: JSON.stringify({
      panel_id: panelId,
      candidate_id: candidateId,
      start_time: startTime,
      end_time: endTime,
      meeting_link: meetingLink || null,
      outlook_event_id: outlookEventId || null,
      status: status || "Scheduled",
    }),
  });
  return data;
};

export const updateInterview = async (interviewId, payload) => {
  const { data, response } = await apiRequest(`/interviews/${interviewId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return {data,response};
};

export const getAllInterviews = async () => {
  const { data } = await apiRequest("/interviews", {
    method: "GET",
  });
  return data;
};

export const getInterviewPanels = async () => {
  const { data } = await apiRequest("/interviews/panels", {
    method: "GET",
  });
  return data;
};

export const getInterviewPanel = async (panelId) => {
  const { data } = await apiRequest(`/interviews/panels/${panelId}`, {
    method: "GET",
  });
  return data;
};

export const getPanelMembers = async (panelId) => {
  const { data } = await apiRequest(`/interviews/panel-members/${panelId}`, {
    method: "GET",
  });
  return data;
};

export const deletePanelMember = async (memberId) => {
  const { data } = await apiRequest(`/interviews/panel-members/${memberId}`, {
    method: "DELETE",
  });
  return data;
};

export const deleteInterview = async (interviewId) => {
  const { data,response } = await apiRequest(`/interviews/${interviewId}`, {
    method: "DELETE",
  });
  return {data,response};
};

export const deleteInterviewPanel = async (panelId) => {
  const { data } = await apiRequest(`/interviews/panels/${panelId}`, {
    method: "DELETE",
  });
  return data;
};

export const getInterviewById = async (interviewId) => {
  const { data } = await apiRequest(`/interviews/${interviewId}`, {
    method: "GET",
  });
  return data;
};

export const submitInterviewFeedback = async ({
  interviewId,
  interviewerId,
  technicalScore,
  communicationScore,
  problemSolvingScore,
  cultureFitScore,
  comments,
  recommendation,
}) => {
  const { data } = await apiRequest("/interviews/feedback/submit", {
    method: "POST",
    body: JSON.stringify({
      interview_id: interviewId,
      interviewer_id: interviewerId,
      technical_score: technicalScore,
      communication_score: communicationScore,
      problem_solving_score: problemSolvingScore,
      culture_fit_score: cultureFitScore,
      comments,
      recommendation,
    }),
  });
  return data;
};

export const updateInterviewFeedback = async ({
  feedbackId,
  technicalScore,
  communicationScore,
  problemSolvingScore,
  cultureFitScore,
  comments,
  recommendation,
}) => {
  const { data } = await apiRequest(`/interviews/feedback/${feedbackId}`, {
    method: "PUT",
    body: JSON.stringify({
      technical_score: technicalScore,
      communication_score: communicationScore,
      problem_solving_score: problemSolvingScore,
      culture_fit_score: cultureFitScore,
      comments,
      recommendation,
    }),
  });
  return data;
};

export const getFeedbackForInterview = async (interviewId) => {
  const { data } = await apiRequest(
    `/interviews/feedback/interview/${interviewId}`,
    {
      method: "GET",
    },
  );
  return data;
};

export const getFeedbackById = async (feedbackId) => {
  const { data } = await apiRequest(`/interviews/feedback/${feedbackId}`, {
    method: "GET",
  });
  return data;
};

export const deleteInterviewFeedback = async (feedbackId) => {
  const { data } = await apiRequest(`/interviews/feedback/${feedbackId}`, {
    method: "DELETE",
  });
  return data;
};

export const getInterviewStatistics = async () => {
  try {
    const { data } = await apiRequest("/interviews/statistics", {
      method: "GET",
    });
    return data;
  } catch (err) {
    const { data: listData } = await apiRequest("/interviews", {
      method: "GET",
    });

    const interviews = Array.isArray(listData)
      ? listData
      : Array.isArray(listData?.interviews)
        ? listData.interviews
        : Array.isArray(listData?.records)
          ? listData.records
          : [];

    const normalize = (s) =>
      String(s || "")
        .trim()
        .toLowerCase();

    const total_interviews = interviews.length;
    const scheduled = interviews.filter((i) =>
      ["scheduled"].includes(normalize(i.status)),
    ).length;
    const completed = interviews.filter((i) =>
      ["completed"].includes(normalize(i.status)),
    ).length;
    const cancelled = interviews.filter((i) => {
      const st = normalize(i.status);
      return st === "cancelled" || st === "canceled";
    }).length;

    return {
      total_interviews,
      scheduled,
      completed,
      cancelled,
      average_feedback_score: null,
    };
  }
};

export const getCandidateInterviewHistory = async (candidateId) => {
  const { data } = await apiRequest(
    `/interviews/candidate-history/${candidateId}`,
    {
      method: "GET",
    },
  );
  return data;
};

export const getInterviewerWorkload = async (interviewerId) => {
  const { data } = await apiRequest(
    `/interviews/interviewer-workload/${interviewerId}`,
    {
      method: "GET",
    },
  );
  return data;
};

export const getMyInterviews = async (status = "") => {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const { data } = await apiRequest(`/interviews/my-interviews${query}`, {
    method: "GET",
  });
  return data;
};

export const getAssignedInterviews = async () => {
  const { data } = await apiRequest("/hr/interviews/assigned", {
    method: "GET",
  });

  return data;
};

// S-102/HRMS-P207 -- Hiring Manager Candidate Review.
// Real fix, 2026-08-05 -- no longer takes a hiring manager ID at all.
// The old version let any logged-in internal user view any OTHER
// hiring manager's candidate review by typing an arbitrary ID; the
// backend now derives "my candidates" from the authenticated caller.
export const getMyHmCandidateReview = async () => {
  const { data } = await apiRequest("/interviews/hm-review/my-candidates", {
    method: "GET",
  });
  return data;
};

// Get Flash interview analysis (AI-powered assessment from Teams transcript)
export const getFlashAnalysisForInterview = async (interviewId) => {
  try {
    const { data } = await apiRequest(`/flash/interviews/${interviewId}/analysis`, {
      method: "GET",
    });
    return data?.data || null;
  } catch (err) {
    console.warn(`Failed to load Flash analysis for interview ${interviewId}:`, err);
    return null;
  }
};
