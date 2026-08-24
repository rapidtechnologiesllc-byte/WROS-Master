// S-070/HRMS-0470 -- Candidate Engagement Health Metrics API wrapper.
import { apiRequest } from "./client";

export const getEngagementMetrics = async (candidateId) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/engagement-metrics`, { method: "GET" });
  return data;
};
