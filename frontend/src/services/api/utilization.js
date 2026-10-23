// S-254 (Employee Utilization Dashboard) + S-255 (Bench Cost Visibility).
import { apiRequest } from "./client";

export const getUtilizationSummary = async () => {
  const { data } = await apiRequest("/employees/utilization-summary", { method: "GET" });
  return data;
};



export const getBenchCostSummary = async () => {
  const { data } = await apiRequest("/employees/bench-cost-summary", { method: "GET" });
  return data;
};

// S-223/HRMS-0904 -- the compute step behind the dashboard above: billable hours (approved
// timesheets) vs available hours per week. The weekly utilization_snapshot job runs it for every
// billable employee; this recomputes the recent weeks now for the employees the caller can see.
export const recomputeUtilization = async () => {
  const { data } = await apiRequest("/employees/utilization/recompute", { method: "POST" });
  return data;
};
