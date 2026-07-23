// S-001/S-006/S-007/S-009/S-010 -- AI Recruiter (Thunder) agent assignment + conversation thread.
import { apiRequest } from "./client";

export const getConversationThread = async (candidateId) => {
  const { data } = await apiRequest(`/ai-agent/conversations/${candidateId}`, {
    method: "GET",
  });
  return data;
};

export const getMissingFields = async (candidateId) => {
  const { data } = await apiRequest(`/ai-agent/missing-fields/${candidateId}`, {
    method: "GET",
  });
  return data;
};

export const assignAgent = async (candidateId, body) => {
  const { data } = await apiRequest("/ai-agent/assign", {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId, ...(body || {}) }),
  });
  return data;
};

export const pollForReply = async (candidateId) => {
  const { data } = await apiRequest(`/ai-agent/poll/${candidateId}`, {
    method: "POST",
  });
  return data;
};

export const getAssignments = async (candidateId) => {
  const { data } = await apiRequest(`/ai-agent/assignments/${candidateId}`, {
    method: "GET",
  });
  return data;
};

export const deactivateAgent = async (candidateId) => {
  const { data } = await apiRequest(`/ai-agent/assign/${candidateId}`, {
    method: "DELETE",
  });
  return data;
};

export const sendManualMessage = async (conversationId, message) => {
  const { data } = await apiRequest(`/ai-agent/conversations/${conversationId}/send`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return data;
};

export const takeOverConversation = async (conversationId) => {
  const { data } = await apiRequest(`/ai-agent/conversations/${conversationId}/take-over`, {
    method: "POST",
  });
  return data;
};

export const handBackConversation = async (conversationId) => {
  const { data } = await apiRequest(`/ai-agent/conversations/${conversationId}/hand-back`, {
    method: "POST",
  });
  return data;
};
