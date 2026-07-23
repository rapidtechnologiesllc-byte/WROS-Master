// S-220 (Create Weekly Timesheet) + S-221 (Validation & Submission
// Lock) + S-222 (Manager Approval). Also the "time tracking" link in
// the MVP chain.
import { apiRequest } from "./client";

export const createWeeklyDraft = async (allocationId, weekStartingDate) => {
  const { data } = await apiRequest("/timesheets/weekly-draft", {
    method: "POST",
    body: JSON.stringify({ allocation_id: allocationId, week_starting_date: weekStartingDate }),
  });
  return data;
};

export const upsertTimesheetEntries = async (timesheetId, entries) => {
  const { data } = await apiRequest(`/timesheets/${timesheetId}/entries`, {
    method: "PUT",
    body: JSON.stringify({ entries }),
  });
  return data;
};

export const submitTimesheet = async (timesheetId) => {
  const { data } = await apiRequest(`/timesheets/${timesheetId}/submit`, { method: "POST" });
  return data;
};

export const approveTimesheet = async (timesheetId) => {
  const { data } = await apiRequest(`/timesheets/${timesheetId}/approve`, { method: "POST" });
  return data;
};

export const rejectTimesheet = async (timesheetId, reason) => {
  const { data } = await apiRequest(`/timesheets/${timesheetId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return data;
};

export const reopenTimesheet = async (timesheetId) => {
  const { data } = await apiRequest(`/timesheets/${timesheetId}/reopen`, { method: "POST" });
  return data;
};

export const getTimesheets = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.employeeId) params.set("employee_id", filters.employeeId);
  if (filters.status) params.set("status", filters.status);
  const qs = params.toString();
  const { data } = await apiRequest(`/timesheets${qs ? `?${qs}` : ""}`, { method: "GET" });
  return data;
};
