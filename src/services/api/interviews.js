// Interview management API wrappers.
import { apiRequest } from "./client";

export const createInterviewPanel = async ({ candidateId, roundName }) => {
  // Create a panel for a candidate and round.
  const { data } = await apiRequest("/interviews/panels/create", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: candidateId,
      round_name: roundName
    })
  });
  return data;
};

export const assignPanelMember = async ({ panelId, interviewerId }) => {
  // Assign an interviewer to the panel.
  const { data } = await apiRequest("/interviews/panel-members/assign", {
    method: "POST",
    body: JSON.stringify({
      panel_id: panelId,
      interviewer_id: interviewerId
    })
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
  status
}) => {
  // Create interview entry after panel + meeting are ready.
  const { data } = await apiRequest("/interviews/create", {
    method: "POST",
    body: JSON.stringify({
      panel_id: panelId,
      candidate_id: candidateId,
      start_time: startTime,
      end_time: endTime,
      meeting_link: meetingLink || null,
      outlook_event_id: outlookEventId || null,
      status: status || "Scheduled"
    })
  });
  return data;
};

export const updateInterview = async ({
  interviewId,
  startTime,
  endTime,
  meetingLink,
  outlookEventId,
  status
}) => {
  // Update interview timings/status.
  const { data } = await apiRequest(`/interviews/${interviewId}`, {
    method: "PUT",
    body: JSON.stringify({
      start_time: startTime,
      end_time: endTime,
      meeting_link: meetingLink,
      outlook_event_id: outlookEventId,
      status
    })
  });
  return data;
};

export const getAllInterviews = async () => {
  // Fetch all interviews for HR/Admin dashboards.
  const { data } = await apiRequest("/interviews", {
    method: "GET"
  });
  return data;
};

export const getInterviewPanels = async () => {
  // Fetch all panels (used for status view).
  const { data } = await apiRequest("/interviews/panels", {
    method: "GET"
  });
  return data;
};

export const getInterviewPanel = async (panelId) => {
  // Fetch a single panel by ID.
  const { data } = await apiRequest(`/interviews/panels/${panelId}`, {
    method: "GET"
  });
  return data;
};

export const getPanelMembers = async (panelId) => {
  // List members of a panel.
  const { data } = await apiRequest(`/interviews/panel-members/${panelId}`, {
    method: "GET"
  });
  return data;
};

export const deletePanelMember = async (memberId) => {
  // Remove interviewer from a panel.
  const { data } = await apiRequest(`/interviews/panel-members/${memberId}`, {
    method: "DELETE"
  });
  return data;
};

export const deleteInterview = async (interviewId) => {
  // Delete interview record.
  const { data } = await apiRequest(`/interviews/${interviewId}`, {
    method: "DELETE"
  });
  return data;
};

export const deleteInterviewPanel = async (panelId) => {
  // Delete panel and related interviews/feedback.
  const { data } = await apiRequest(`/interviews/panels/${panelId}`, {
    method: "DELETE"
  });
  return data;
};

export const getInterviewById = async (interviewId) => {
  // Fetch a single interview with details.
  const { data } = await apiRequest(`/interviews/${interviewId}`, {
    method: "GET"
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
  recommendation
}) => {
  // Create feedback for an interview.
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
      recommendation
    })
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
  recommendation
}) => {
  // Update feedback by ID.
  const { data } = await apiRequest(`/interviews/feedback/${feedbackId}`, {
    method: "PUT",
    body: JSON.stringify({
      technical_score: technicalScore,
      communication_score: communicationScore,
      problem_solving_score: problemSolvingScore,
      culture_fit_score: cultureFitScore,
      comments,
      recommendation
    })
  });
  return data;
};

export const getFeedbackForInterview = async (interviewId) => {
  // List feedback entries for a specific interview.
  const { data } = await apiRequest(`/interviews/feedback/interview/${interviewId}`, {
    method: "GET"
  });
  return data;
};

export const getFeedbackById = async (feedbackId) => {
  // Fetch a single feedback record.
  const { data } = await apiRequest(`/interviews/feedback/${feedbackId}`, {
    method: "GET"
  });
  return data;
};

export const deleteInterviewFeedback = async (feedbackId) => {
  // Delete feedback entry.
  const { data } = await apiRequest(`/interviews/feedback/${feedbackId}`, {
    method: "DELETE"
  });
  return data;
};

export const getInterviewStatistics = async () => {
  // High-level interview metrics for dashboards.
  const { data } = await apiRequest("/interviews/statistics", {
    method: "GET"
  });
  return data;
};

export const getCandidateInterviewHistory = async (candidateId) => {
  // Full interview history for a candidate.
  const { data } = await apiRequest(`/interviews/candidate-history/${candidateId}`, {
    method: "GET"
  });
  return data;
};

export const getInterviewerWorkload = async (interviewerId) => {
  // Workload summary for a given interviewer.
  const { data } = await apiRequest(`/interviews/interviewer-workload/${interviewerId}`, {
    method: "GET"
  });
  return data;
};
