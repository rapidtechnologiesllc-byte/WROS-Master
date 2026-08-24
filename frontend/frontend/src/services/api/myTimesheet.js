// Employee self-service timesheet API wrapper.
import { apiRequest } from "./client";

export const getMyAllocations = async () => {
  const { data } = await apiRequest("/my/allocations", { method: "GET" });
  return data;
};

export const getMyCurrentTimesheet = async (allocationId) => {
  const { data } = await apiRequest(`/my/timesheet/current?allocation_id=${encodeURIComponent(allocationId)}`, { method: "GET" });
  return data;
};

export const logMyHours = async (timesheetId, entries) => {
  const { data } = await apiRequest(`/my/timesheet/${timesheetId}/entries`, { method: "PUT", body: JSON.stringify({ entries }) });
  return data;
};

export const submitMyTimesheet = async (timesheetId) => {
  const { data } = await apiRequest(`/my/timesheet/${timesheetId}/submit`, { method: "POST" });
  return data;
};

export const getMyTimesheetHistory = async () => {
  const { data } = await apiRequest("/my/timesheet/history", { method: "GET" });
  return data;
};
