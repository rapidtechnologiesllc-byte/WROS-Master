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

// The bench work items I may log time against (accelerators, certifications, BU-head-approved work)
export const getMyWorkItems = async () => {
  const { data } = await apiRequest("/my/work-items", { method: "GET" });
  return listFrom(data, "work_items");
};

// source: { allocationId } for client or project work, { workItemId } for bench work
export const getMyTimesheetForWeek = async (source, weekStarting) => {
  const params = new URLSearchParams(
    source.workItemId ? { work_item_id: source.workItemId } : { allocation_id: source.allocationId },
  );
  if (weekStarting) params.set("week_starting", weekStarting);
  const { data } = await apiRequest(`/my/timesheet/current?${params.toString()}`, { method: "GET" });
  return data;
};

export const logMyHours = async (timesheetId, entries) => {
  const { data } = await apiRequest(`/my/timesheet/${timesheetId}/entries`, { method: "PUT", body: JSON.stringify({ entries }) });
  return data;
};

// response: the employee's answer to a rejection (required when the entries did not change)
export const submitMyTimesheet = async (timesheetId, response) => {
  const { data } = await apiRequest(`/my/timesheet/${timesheetId}/submit`, {
    method: "POST", body: JSON.stringify({ response: response || null }),
  });
  return data;
};

// My recent timesheets; with weekStarting, every one of that week (the rows of the week's time card)
export const getMyTimesheetHistory = async (weekStarting) => {
  const query = weekStarting ? `?week_starting=${weekStarting}` : "";
  const { data } = await apiRequest(`/my/timesheet/history${query}`, { method: "GET" });
  return listFrom(data, "timesheets");
};
