// S-071/HRMS-0471 -- AI Recruiter Performance Analytics API wrapper.
import { apiRequest } from "./client";

export const getThunderAnalytics = async ({ dateFrom, dateTo } = {}) => {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const qs = params.toString();
  const { data } = await apiRequest(`/analytics/thunder${qs ? `?${qs}` : ""}`, { method: "GET" });
  return data;
};
