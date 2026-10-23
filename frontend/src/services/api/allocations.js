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
  billingRateUsdCents,
  billable,
  timesheetApproverEmail,
  workOrderId,
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
      billing_rate_usd_cents: billingRateUsdCents || undefined,
      // undefined = the project's (client projects billable, internal projects not)
      billable: typeof billable === "boolean" ? billable : undefined,
      timesheet_approver_email: timesheetApproverEmail || undefined,
      work_order_id: workOrderId || undefined,
    }),
  });
  return data;
};

export const getAllocations = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.employeeId) params.set("employee_id", filters.employeeId);
  if (filters.demandId) params.set("demand_id", filters.demandId);
  if (filters.clientId) params.set("client_id", filters.clientId);
  const qs = params.toString();
  const { data } = await apiRequest(`/allocations${qs ? `?${qs}` : ""}`, { method: "GET" });
  // the API wraps the list ({allocations: [...]}); callers get the list
  if (!data || !Array.isArray(data.allocations)) throw new Error("Unexpected response: no allocations list.");
  return data.allocations;
};

export const endAllocation = async (allocationId, endDate) => {
  const { data } = await apiRequest(`/allocations/${allocationId}/end`, {
    method: "POST",
    body: JSON.stringify({ end_date: endDate || undefined }),
  });
  return data;
};

export const getAllocationDropdowns = async () => {
  const { data } = await apiRequest(`/allocations/dropdowns/for-create`, { method: "GET" });
  return data;
};

// Edit / extend (CEO 2026-10-23): only the fields given change; a reason is required and kept in
// the history. Below the margin floor the change waits for approval (change.status PENDING_APPROVAL).
export const updateAllocation = async (allocationId, { reason, effectiveFrom, ...fields }) => {
  const body = { reason };
  ["end_date", "billing_rate_usd_cents", "utilization_pct", "billable"].forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(fields, key)) body[key] = fields[key];
  });
  if (effectiveFrom) body.effective_from = effectiveFrom;
  const { data } = await apiRequest(`/allocations/${allocationId}`, { method: "PATCH", body: JSON.stringify(body) });
  return data;
};

export const getAllocationHistory = async (allocationId) => {
  const { data } = await apiRequest(`/allocations/${allocationId}/history`, { method: "GET" });
  if (!data || !Array.isArray(data.changes)) throw new Error("Unexpected response: no history.");
  return data.changes;
};

// The margin guard's verdict on the terms in a form: a new placement (employeeId + demandId) or
// an existing allocation's proposed terms (allocationId).
export const previewMargin = async ({ employeeId, demandId, projectId, allocationId, billingRateUsdCents,
  billable, startDate, role }) => {
  const { data } = await apiRequest("/allocations/margin-preview", {
    method: "POST",
    body: JSON.stringify({
      employee_id: employeeId || undefined,
      demand_id: demandId || undefined,
      project_id: projectId || undefined,
      allocation_id: allocationId || undefined,
      billing_rate_usd_cents: billingRateUsdCents || undefined,
      billable: typeof billable === "boolean" ? billable : undefined,
      start_date: startDate || undefined,
      role: role || undefined,
    }),
  });
  return data;
};

export const listMarginApprovals = async () => {
  const { data } = await apiRequest("/allocations/margin-approvals", { method: "GET" });
  if (!data || !Array.isArray(data.approvals)) throw new Error("Unexpected response: no approvals list.");
  return data.approvals;
};

export const decideMarginChange = async (changeId, approve, reason) => {
  const { data } = await apiRequest(`/allocations/changes/${changeId}/${approve ? "approve" : "reject"}`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return data;
};

// Renewal pipeline (Demand vs Bench > Renewals)
export const getRenewals = async (days) => {
  const { data } = await apiRequest(`/allocations/renewals${days ? `?days=${days}` : ""}`, { method: "GET" });
  if (!data || !Array.isArray(data.renewals)) throw new Error("Unexpected response: no renewals list.");
  return data;
};

// ownerUserId "" puts the owner back to the default (account manager, else BU Head)
export const updateRenewal = async (allocationId, { renewalStatus, ownerUserId, note, reason }) => {
  const { data } = await apiRequest(`/allocations/${allocationId}/renewal`, {
    method: "PUT",
    body: JSON.stringify({ renewal_status: renewalStatus, owner_user_id: ownerUserId, note, reason }),
  });
  return data;
};

// The placement's client timesheet approver and client PO (work order); "" clears a field
export const setPlacementBilling = async (allocationId, { timesheetApproverEmail, workOrderId }) => {
  const body = {};
  if (timesheetApproverEmail !== undefined) body.timesheet_approver_email = timesheetApproverEmail;
  if (workOrderId !== undefined) body.work_order_id = workOrderId;
  const { data } = await apiRequest(`/allocations/${encodeURIComponent(allocationId)}/client-billing`, {
    method: "PUT", body: JSON.stringify(body),
  });
  return data;
};
