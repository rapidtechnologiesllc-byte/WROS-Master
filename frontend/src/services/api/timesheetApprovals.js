// Timesheet approval loop: the approver's side (routed approver or BU timesheet editor).
import { apiFetch, apiRequest } from "./client";

export const getMyTimesheetApprovals = async () => {
  const { data } = await apiRequest("/timesheet-approvals", { method: "GET" });
  if (!data || !Array.isArray(data.approvals)) throw new Error("Unexpected response: no approvals list.");
  return data.approvals;
};

export const getTimesheetApproval = async (timesheetId) => {
  const { data } = await apiRequest(`/timesheet-approvals/${encodeURIComponent(timesheetId)}`, { method: "GET" });
  return data;
};

export const approveTimesheetReview = async (timesheetId, { comment, addressed }) => {
  const { data } = await apiRequest(`/timesheet-approvals/${encodeURIComponent(timesheetId)}/approve`, {
    method: "POST", body: JSON.stringify({ comment: comment || null, addressed: Boolean(addressed) }),
  });
  return data;
};

export const rejectTimesheetReview = async (timesheetId, { reason, flaggedDates }) => {
  const { data } = await apiRequest(`/timesheet-approvals/${encodeURIComponent(timesheetId)}/reject`, {
    method: "POST", body: JSON.stringify({ reason, flagged_dates: flaggedDates || [] }),
  });
  return data;
};

// Client approval (clients that approve their own timesheets): send the client approver a new link
export const requestClientApproval = async (timesheetId) => {
  const { data } = await apiRequest(`/timesheet-approvals/${encodeURIComponent(timesheetId)}/client-request`, {
    method: "POST",
  });
  return data;
};

// Upload the client's approved timesheet (e.g. the VMS export): the week becomes client-approved
export const uploadClientEvidence = async (timesheetId, file, note) => {
  const body = new FormData();
  body.append("file", file);
  if (note) body.append("note", note);
  const { data } = await apiRequest(`/timesheet-approvals/${encodeURIComponent(timesheetId)}/client-evidence`, {
    method: "POST", body,
  });
  return data;
};

export const openClientEvidence = async (timesheetId) => {
  const response = await apiFetch(`/timesheet-approvals/${encodeURIComponent(timesheetId)}/client-evidence`);
  if (!response.ok) throw new Error(`Evidence download failed (HTTP ${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
};
