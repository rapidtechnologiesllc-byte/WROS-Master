import { apiRequest } from "./client";

// ============================================================================
// Partner ROI Agent
// ============================================================================

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

// ============================================================================
// CFO Agent
// ============================================================================

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

// ============================================================================
// CEO FY Progress
// ============================================================================

export const getCEOFYProgress = async (fyYear = 2026) => {
  const { data } = await apiRequest(`/agents/ceo/fy-progress?fy_year=${fyYear}`, {
    method: "GET",
  });
  return data.data;
};

export const getCEOFYSummary = async () => {
  const { data } = await apiRequest("/agents/ceo/fy-summary", { method: "GET" });
  return data.data;
};
