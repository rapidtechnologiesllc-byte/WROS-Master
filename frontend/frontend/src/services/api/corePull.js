// S-353 (HRMS-0514) Core-Pull Engine + S-373 (HRMS-0529) Specialty Pool
// Minimum 40 Guard.
import { apiRequest } from "./client";

export const getSpecialtyPoolStatus = async () => {
  const { data } = await apiRequest("/core-pull/specialty-pool-status", {
    method: "GET",
  });
  return data;
};

export const getPendingCorePullEvents = async () => {
  const { data } = await apiRequest("/core-pull/events", { method: "GET" });
  return data;
};

export const executeCorePullEvent = async (eventId) => {
  const { data } = await apiRequest(`/core-pull/events/${eventId}/execute`, {
    method: "POST",
  });
  return data;
};

export const overrideCorePullEvent = async (eventId, justification) => {
  const { data } = await apiRequest(`/core-pull/events/${eventId}/override`, {
    method: "POST",
    body: JSON.stringify({ justification }),
  });
  return data;
};

export const submitReplacementPlan = async ({
  employeeId,
  replacementStrategy,
  expectedReplacementDate,
}) => {
  const { data } = await apiRequest("/core-pull/replacement-plans", {
    method: "POST",
    body: JSON.stringify({
      employee_id: employeeId,
      replacement_strategy: replacementStrategy,
      expected_replacement_date: expectedReplacementDate,
    }),
  });
  return data;
};
