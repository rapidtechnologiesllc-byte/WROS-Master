import { apiRequest } from "./client";

// Partner ROI Agent

export const getPartnerROIKpis = async (partnerId, yearMonth = null) => {
  const url = `/agents/partner-roi/${partnerId}/kpis${yearMonth ? `?year_month=${yearMonth}` : ""}`;
  const { data } = await apiRequest(url, { method: "GET" });
  return data.data;
};

export const getPartnerROITrend = async (partnerId, monthsBack = 6) => {
  const { data } = await apiRequest(
    `/agents/partner-roi/${partnerId}/trend?months_back=${monthsBack}`,
    { method: "GET" }
  );
  return data.data;
};

export const getPartnerROIActions = async (partnerId) => {
  const { data } = await apiRequest(`/agents/partner-roi/${partnerId}/actions`, {
    method: "GET",
  });
  return data.data;
};

// CFO Agent

export const getCFOFinancialSnapshot = async (yearMonth = null) => {
  const url = `/agents/cfo/financial-snapshot${yearMonth ? `?year_month=${yearMonth}` : ""}`;
  const { data } = await apiRequest(url, { method: "GET" });
  return data.data;
};

export const getCFOAlerts = async () => {
  const { data } = await apiRequest("/agents/cfo/alerts", { method: "GET" });
  return data.data;
};

export const getCFOBUComparison = async (yearMonth = null) => {
  const url = `/agents/cfo/bu-comparison${yearMonth ? `?year_month=${yearMonth}` : ""}`;
  const { data } = await apiRequest(url, { method: "GET" });
  return data.data;
};

export const getCFOExpenseBreakdown = async (yearMonth = null) => {
  const url = `/agents/cfo/expense-breakdown${yearMonth ? `?year_month=${yearMonth}` : ""}`;
  const { data } = await apiRequest(url, { method: "GET" });
  return data.data;
};

export const getCFOForecast = async (monthsAhead = 3) => {
  const { data } = await apiRequest(`/agents/cfo/forecast?months_ahead=${monthsAhead}`, {
    method: "GET",
  });
  return data.data;
};

// CEO FY Progress

// fyYear omitted = the current fiscal year (per the FY start-month setting)
export const getCEOFYProgress = async (fyYear) => {
  const query = fyYear ? `?fy_year=${fyYear}` : "";
  const { data } = await apiRequest(`/agents/ceo/fy-progress${query}`, {
    method: "GET",
  });
  return data.data;
};

export const getCEOFYSummary = async () => {
  const { data } = await apiRequest("/agents/ceo/fy-summary", { method: "GET" });
  return data.data;
};

// CEO FY targets (one per dashboard metric); null target = not set
export const setFYTarget = async (metric, target, fyYear) => {
  const { data } = await apiRequest(`/goals/fy-targets/${metric}?year=${fyYear}`, {
    method: "PUT",
    body: JSON.stringify({ target }),
  });
  return data;
};

export const getFYSettings = async () => {
  const { data } = await apiRequest("/goals/fy-settings", { method: "GET" });
  return data;
};

export const setFYStartMonth = async (startMonth) => {
  const { data } = await apiRequest("/goals/fy-settings", {
    method: "PUT",
    body: JSON.stringify({ start_month: startMonth }),
  });
  return data;
};
