// Employee self-service timesheet API wrapper. The backend wraps lists in an object
// ({allocations}, {timesheets}, {weeks}); these helpers return the list itself and fail loudly
// when the shape is not what the screen needs.
import { apiRequest } from "./client";

const listFrom = (data, key) => {
  if (!data || !Array.isArray(data[key])) {
    throw new Error(`Unexpected response: no ${key} list.`);
  }
  return data[key];
};

export const getMyAllocations = async () => {
  const { data } = await apiRequest("/my/allocations", { method: "GET" });
  return listFrom(data, "allocations");
};

export const getMyTimesheetWeeks = async () => {
  const { data } = await apiRequest("/my/timesheet/weeks", { method: "GET" });
  return listFrom(data, "weeks");
};

export const getMyTimesheetForWeek = async (allocationId, weekStarting) => {
  const params = new URLSearchParams({ allocation_id: allocationId });
  if (weekStarting) params.set("week_starting", weekStarting);
  const { data } = await apiRequest(`/my/timesheet/current?${params.toString()}`, { method: "GET" });
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
  return listFrom(data, "timesheets");
};
