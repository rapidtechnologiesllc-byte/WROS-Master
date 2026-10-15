// Core certification: BU Head approval of employees who meet the rules (Buddy graduated,
// 90 approved billable Staff Aug days with no escalation). Requests come from a daily job.
import { apiRequest } from "./client";

export const getCoreCertificationRequests = async (status) => {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const { data } = await apiRequest(`/core-certification/requests${query}`, { method: "GET" });
  return data;
};

export const approveCoreCertification = async (requestId) => {
  const { data } = await apiRequest(`/core-certification/requests/${requestId}/approve`, { method: "POST" });
  return data;
};

export const closeCoreCertification = async (requestId) => {
  const { data } = await apiRequest(`/core-certification/requests/${requestId}/close`, { method: "POST" });
  return data;
};

// one turn of the Flash rejection discussion; an empty message starts it
export const rejectCoreCertificationChat = async (requestId, message) => {
  const { data } = await apiRequest(`/core-certification/requests/${requestId}/reject-chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return data;
};
