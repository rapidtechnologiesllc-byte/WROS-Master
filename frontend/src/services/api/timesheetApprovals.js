// Timesheet approval loop: the approver's side (routed approver or BU timesheet editor).
import { apiRequest } from "./client";

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
