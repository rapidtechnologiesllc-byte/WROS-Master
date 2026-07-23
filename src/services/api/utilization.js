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

// S-223/HRMS-0904 -- the compute step behind the dashboard above:
// billable hours (from approved timesheets) vs available hours for a
// given week, snapshotted per employee.
export const recordUtilization = async (employeeId, weekStartingDate) => {
  const { data } = await apiRequest(`/employees/${employeeId}/record-utilization`, {
    method: "POST",
    body: JSON.stringify({ week_starting_date: weekStartingDate }),
  });
  return data;
};
