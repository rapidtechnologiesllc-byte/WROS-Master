// S-062/HRMS-0462 -- Recruiter Intervention Queue API wrapper.
import { apiRequest } from "./client";

export const getInterventionQueue = async (status) => {
  const params = status ? `?status=${status}` : "";
  const { data } = await apiRequest(`/intervention-queue${params}`, { method: "GET" });
  return data;
};

export const getInterventionQueueSummary = async () => {
  const { data } = await apiRequest("/intervention-queue/summary", { method: "GET" });
  return data;
};

export const takeOverQueueItem = async (queueItemId) => {
  const { data } = await apiRequest(`/intervention-queue/${queueItemId}/take-over`, { method: "POST" });
  return data;
};

export const resolveQueueItem = async (queueItemId, resolutionNote) => {
  const { data } = await apiRequest(`/intervention-queue/${queueItemId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution_note: resolutionNote || null }),
  });
  return data;
};
