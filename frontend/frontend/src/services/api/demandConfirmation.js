// S-372 (HRMS-0528) Confirmed vs Potential Demand Workflow.
import { apiRequest } from "./client";

export const confirmDemandWithSOW = async (demandId, { sowReference, sowReceivedDate }) => {
  const { data } = await apiRequest(`/demand-confirmation/demands/${demandId}/confirm-sow`, {
    method: "POST",
    body: JSON.stringify({
      sow_reference: sowReference,
      sow_received_date: sowReceivedDate || undefined,
    }),
  });
  return data;
};

export const scheduleAlignmentCall = async (demandId, employeeId, { curtisUserId, buHeadUserId } = {}) => {
  const { data } = await apiRequest(
    `/demand-confirmation/demands/${demandId}/employees/${employeeId}/schedule-call`,
    {
      method: "POST",
      body: JSON.stringify({
        curtis_user_id: curtisUserId || undefined,
        bu_head_user_id: buHeadUserId || undefined,
      }),
    },
  );
  return data;
};

export const getCallsForDemand = async (demandId) => {
  const { data } = await apiRequest(`/demand-confirmation/demands/${demandId}/calls`, {
    method: "GET",
  });
  return data;
};

export const confirmFit = async (callId, { participant, confirmed, notes }) => {
  const { data } = await apiRequest(`/demand-confirmation/calls/${callId}/confirm-fit`, {
    method: "POST",
    body: JSON.stringify({ participant, confirmed, notes: notes || undefined }),
  });
  return data;
};

export const triggerRelease = async (callId) => {
  const { data } = await apiRequest(`/demand-confirmation/calls/${callId}/trigger-release`, {
    method: "POST",
  });
  return data;
};
