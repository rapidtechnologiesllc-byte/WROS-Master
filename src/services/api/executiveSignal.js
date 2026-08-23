// Executive Signal & Culture Agent API wrapper.
import { apiRequest } from "./client";

export const getOrgHealth = async () => {
  const { data } = await apiRequest("/executive-signal/org-health", { method: "GET" });
  return data;
};

export const getPendingRecognition = async () => {
  const { data } = await apiRequest("/executive-signal/recognition/pending", { method: "GET" });
  return data;
};

export const generateBirthdayDrafts = async () => {
  const { data } = await apiRequest("/executive-signal/recognition/birthday-drafts", { method: "POST" });
  return data;
};

export const approveRecognition = async (draftId) => {
  const { data } = await apiRequest(`/executive-signal/recognition/${draftId}/approve`, { method: "POST" });
  return data;
};

export const rejectRecognition = async (draftId) => {
  const { data } = await apiRequest(`/executive-signal/recognition/${draftId}/reject`, { method: "POST" });
  return data;
};

export const createFeedbackCycle = async (quarterLabel) => {
  const { data } = await apiRequest("/executive-signal/feedback-cycles", { method: "POST", body: JSON.stringify({ quarter_label: quarterLabel }) });
  return data;
};

export const closeFeedbackCycle = async (cycleId) => {
  const { data } = await apiRequest(`/executive-signal/feedback-cycles/${cycleId}/close`, { method: "POST" });
  return data;
};

export const submitConcern = async (messageText) => {
  const { data } = await apiRequest("/executive-signal/concerns", { method: "POST", body: JSON.stringify({ message_text: messageText }) });
  return data;
};
