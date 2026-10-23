// Core certification: BU Head approval of employees who meet the rules (Buddy graduated,
// 90 approved billable Staff Aug days with no escalation). Requests come from a daily job.
// Approving or rejecting happens in the Flash bubble (?flash=core_cert:<id>).
import { apiRequest } from "./client";

export const getCoreCertificationRequests = async (status) => {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const { data } = await apiRequest(`/core-certification/requests${query}`, { method: "GET" });
  return data;
};

export const closeCoreCertification = async (requestId) => {
  const { data } = await apiRequest(`/core-certification/requests/${requestId}/close`, { method: "POST" });
  return data;
};
