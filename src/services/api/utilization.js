// S-254 (Employee Utilization Dashboard) + S-255 (Bench Cost Visibility).
import { apiRequest } from "./client";

export const getUtilizationSummary = async () => {
  const { data } = await apiRequest("/employees/utilization-summary", { method: "GET" });
  return data;
};

export const getUtilizationHistory = async (employeeId) => {
  const { data } = await apiRequest(`/employees/${employeeId}/utilization-history`, {
    method: "GET",
  });
  return data;
};

export const getBenchCostSummary = async () => {
  const { data } = await apiRequest("/employees/bench-cost-summary", { method: "GET" });
  return data;
};
