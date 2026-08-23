import { apiRequest } from "./client";

export const HISTORY_EVENT_TYPES = Object.freeze({
  APPLIED: "Applied",
  SCREENING: "Screening",
  INTERVIEW_SCHEDULED: "Interview Scheduled",
  INTERVIEW_COMPLETED: "Interview Completed",
  OFFER_RELEASED: "Offer Released",
  OFFER_ACCEPTED: "Offer Accepted",
  OFFER_REJECTED: "Offer Rejected",
  PRE_ONBOARDING: "Pre-Onboarding",
  ONBOARDED: "Onboarded",
  REJECTED: "Rejected",
  CUSTOM: "Custom",
});

export const HISTORY_EVENT_TYPE_OPTIONS = Object.values(HISTORY_EVENT_TYPES);

const buildQueryString = (params = {}) => {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.append(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
};

export const getCandidateHistory = async (
  candidateId,
  { eventType = "", skip = 0, limit = 50 } = {},
) => {
  if (!candidateId) {
    throw new Error("Candidate ID is required to fetch history.");
  }

  const queryString = buildQueryString({
    event_type: eventType,
    skip,
    limit,
  });

  const { data } = await apiRequest(
    `/history/${encodeURIComponent(candidateId)}${queryString}`,
    {
      method: "GET",
    },
  );

  return {
    candidateId: data?.candidate_id || candidateId,
    total: Number(data?.total || 0),
    events: Array.isArray(data?.events) ? data.events : [],
  };
};

export const getLatestCandidateHistory = async (candidateId, n = 10) => {
  if (!candidateId) {
    throw new Error("Candidate ID is required to fetch latest history.");
  }

  const queryString = buildQueryString({ n });

  const { data } = await apiRequest(
    `/history/${encodeURIComponent(candidateId)}/latest${queryString}`,
    {
      method: "GET",
    },
  );

  return {
    candidateId: data?.candidate_id || candidateId,
    total: Number(data?.total || 0),
    events: Array.isArray(data?.events) ? data.events : [],
  };
};

export const createCandidateHistoryEvent = async (
  candidateId,
  payload = {},
) => {
  if (!candidateId) {
    throw new Error("Candidate ID is required to create history event.");
  }

  if (!payload?.event_type) {
    throw new Error("History event type is required.");
  }

  const requestBody = {
    event_type: payload.event_type,
    note: payload?.note || "",
    ...(payload?.performed_by_id
      ? { performed_by_id: payload.performed_by_id }
      : {}),
    ...(payload?.performed_by_name
      ? { performed_by_name: payload.performed_by_name }
      : {}),
    ...(payload?.job_id ? { job_id: payload.job_id } : {}),
    ...(payload?.interview_id ? { interview_id: payload.interview_id } : {}),
    ...(payload?.offer_letter_id
      ? { offer_letter_id: payload.offer_letter_id }
      : {}),
    event_at: payload?.event_at || new Date().toISOString(),
  };

  const { data } = await apiRequest(
    `/history/${encodeURIComponent(candidateId)}`,
    {
      method: "POST",
      body: JSON.stringify(requestBody),
    },
  );

  return data;
};
