// HRMS-0906 (Revenue Leakage) + HRMS-0903 (Reconciliation) + HRMS-0909
// (Client Revenue Dashboard).
import { apiRequest } from "./client";

export const scanRevenueLeakage = async (projectId, periodStart, periodEnd) => {
  const { data } = await apiRequest("/revenue/leakage/scan", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, period_start: periodStart, period_end: periodEnd }),
  });
  return data;
};

export const logLeakagePartialBillingReason = async (flagId, reason) => {
  const { data } = await apiRequest(`/revenue/leakage/${flagId}/log-reason`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return data;
};

export const getActiveLeakageFlags = async () => {
  const { data } = await apiRequest("/revenue/leakage", { method: "GET" });
  return data;
};

export const scanReconciliationGaps = async () => {
  const { data } = await apiRequest("/revenue/reconciliation/scan", { method: "POST" });
  return data;
};

export const getReconciliationAlerts = async (status) => {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const { data } = await apiRequest(`/revenue/reconciliation/alerts${qs}`, { method: "GET" });
  return data;
};

export const resolveReconciliationAlert = async (alertId) => {
  const { data } = await apiRequest(`/revenue/reconciliation/alerts/${alertId}/resolve`, { method: "POST" });
  return data;
};

export const getClientRevenueDashboard = async (clientId) => {
  const { data } = await apiRequest(`/revenue/dashboard/clients/${clientId}`, { method: "GET" });
  return data;
};

// S-242 Forecast vs Actual
export const forecastVsActual = async (year, month, businessUnitId = null) => {
  const qs = businessUnitId ? `?business_unit_id=${businessUnitId}` : "";
  const { data } = await apiRequest(`/forecast-vs-actual?year=${year}&month=${month}${qs ? "&" + qs.substring(1) : ""}`, { method: "GET" });
  return data;
};

export const forecastVsActualTrend = async (year) => {
  const { data } = await apiRequest(`/forecast-vs-actual/trend?year=${year}`, { method: "GET" });
  return data;
};
