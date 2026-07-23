// S-251 (Allocate Employee to Project) + S-252 (Allocation Conflict
// Detection -- surfaced as a 409 from the existing allocate gate, not a
// separate check).
import { apiRequest } from "./client";

export const createAllocation = async ({
  employeeId,
  demandId,
  projectId,
  startDate,
  endDate,
  utilizationPct,
  role,
  allowConcurrent,
}) => {
  const { data } = await apiRequest("/allocations", {
    method: "POST",
    body: JSON.stringify({
      employee_id: employeeId,
      demand_id: demandId,
      project_id: projectId || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      utilization_pct: utilizationPct != null ? Number(utilizationPct) : undefined,
      role: role || undefined,
      allow_concurrent: !!allowConcurrent,
    }),
  });
  return data;
};

export const getAllocations = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.employeeId) params.set("employee_id", filters.employeeId);
  if (filters.demandId) params.set("demand_id", filters.demandId);
  const qs = params.toString();
  const { data } = await apiRequest(`/allocations${qs ? `?${qs}` : ""}`, { method: "GET" });
  return data;
};

export const endAllocation = async (allocationId, endDate) => {
  const { data } = await apiRequest(`/allocations/${allocationId}/end`, {
    method: "POST",
    body: JSON.stringify({ end_date: endDate || undefined }),
  });
  return data;
};
