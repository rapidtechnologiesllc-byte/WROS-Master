import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://localhost:8080";

// ============================================================================
// Partner ROI Agent
// ============================================================================

export const getPartnerROIKpis = async (partnerId, yearMonth = null) => {
  try {
    const url = `/agents/partner-roi/${partnerId}/kpis${yearMonth ? `?year_month=${yearMonth}` : ""}`;
    const { data } = await axios.get(`${API_BASE}${url}`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch Partner ROI KPIs:", err);
    throw err;
  }
};

export const getPartnerROITrend = async (partnerId, monthsBack = 6) => {
  try {
    const { data } = await axios.get(
      `${API_BASE}/agents/partner-roi/${partnerId}/trend?months_back=${monthsBack}`
    );
    return data.data;
  } catch (err) {
    console.error("Failed to fetch Partner ROI trend:", err);
    throw err;
  }
};

export const getPartnerROIActions = async (partnerId) => {
  try {
    const { data } = await axios.get(`${API_BASE}/agents/partner-roi/${partnerId}/actions`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch Partner ROI actions:", err);
    throw err;
  }
};

// ============================================================================
// CFO Agent
// ============================================================================

export const getCFOFinancialSnapshot = async (yearMonth = null) => {
  try {
    const url = `/agents/cfo/financial-snapshot${yearMonth ? `?year_month=${yearMonth}` : ""}`;
    const { data } = await axios.get(`${API_BASE}${url}`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch CFO financial snapshot:", err);
    throw err;
  }
};

export const getCFOAlerts = async () => {
  try {
    const { data } = await axios.get(`${API_BASE}/agents/cfo/alerts`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch CFO alerts:", err);
    throw err;
  }
};

export const getCFOBUComparison = async (yearMonth = null) => {
  try {
    const url = `/agents/cfo/bu-comparison${yearMonth ? `?year_month=${yearMonth}` : ""}`;
    const { data } = await axios.get(`${API_BASE}${url}`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch CFO BU comparison:", err);
    throw err;
  }
};

export const getCFOExpenseBreakdown = async (yearMonth = null) => {
  try {
    const url = `/agents/cfo/expense-breakdown${yearMonth ? `?year_month=${yearMonth}` : ""}`;
    const { data } = await axios.get(`${API_BASE}${url}`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch CFO expense breakdown:", err);
    throw err;
  }
};

export const getCFOForecast = async (monthsAhead = 3) => {
  try {
    const { data } = await axios.get(`${API_BASE}/agents/cfo/forecast?months_ahead=${monthsAhead}`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch CFO forecast:", err);
    throw err;
  }
};

// ============================================================================
// CEO FY Progress
// ============================================================================

export const getCEOFYProgress = async (fyYear = 2026) => {
  try {
    const { data } = await axios.get(`${API_BASE}/agents/ceo/fy-progress?fy_year=${fyYear}`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch CEO FY progress:", err);
    throw err;
  }
};

export const getCEOFYSummary = async () => {
  try {
    const { data } = await axios.get(`${API_BASE}/agents/ceo/fy-summary`);
    return data.data;
  } catch (err) {
    console.error("Failed to fetch CEO FY summary:", err);
    throw err;
  }
};
