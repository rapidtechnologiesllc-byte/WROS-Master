// S-061/HRMS-0461 -- AI Activity Feed API wrapper.
import { apiRequest } from "./client";

export const getActivityFeed = async ({ candidateId, severity, page = 1, perPage = 25 } = {}) => {
  const params = new URLSearchParams();
  if (candidateId) params.set("candidate_id", candidateId);
  if (severity) params.set("severity", severity);
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  const { data } = await apiRequest(`/activity-feed?${params.toString()}`, { method: "GET" });
  return data;
};

export const markActivityRead = async (activityId) => {
  const { data } = await apiRequest(`/activity-feed/${activityId}/read`, { method: "PATCH" });
  return data;
};

export const markAllActivityRead = async (candidateId) => {
  const params = candidateId ? `?candidate_id=${candidateId}` : "";
  const { data } = await apiRequest(`/activity-feed/read-all${params}`, { method: "PATCH" });
  return data;
};
