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

// Source of hire, each recruiter's results and open positions against hires (the caller's own scope)
export const getHiringAnalytics = async ({ dateFrom, dateTo } = {}) => {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const qs = params.toString();
  const { data } = await apiRequest(`/analytics/hiring${qs ? `?${qs}` : ""}`, { method: "GET" });
  if (!data || !data.totals || !Array.isArray(data.sources) || !Array.isArray(data.positions)) {
    throw new Error("Unexpected response: no hiring analytics.");
  }
  return data;
};
