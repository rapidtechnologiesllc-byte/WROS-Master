// Offer letter API wrappers (HR and candidate).
import { apiRequest } from "./client";

// ========== HR/Recruiter Endpoints ==========

export const createOfferLetter = async (payload) => {
  const { data } = await apiRequest("/offer-letter/create", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: payload.candidateId,
      job_id: payload.jobId || null,
      hiring_manager_id: payload.hiringManagerId,
      reporting_manager_id: payload.reportingManagerId,
      position: payload.position,
      salary: String(payload.salary),
      joining_date: payload.joiningDate,
      offer_expire_date: payload.offer_expire_date,
    }),
  });
  return data;
};

export const getAllOffers = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.candidate_id) params.set("candidate_id", filters.candidate_id);
  const qs = params.toString();
  const path = qs ? `/offer-letter/all?${qs}` : "/offer-letter/all";
  const { data } = await apiRequest(path, { method: "GET" });
  return data;
};

export const getOfferById = async (offerId) => {
  const { data } = await apiRequest(`/offer-letter/${offerId}`, {
    method: "GET",
  });
  return data;
};

export const updateOfferLetter = async (offerId, payload) => {
  const body = {};
  if (payload.jobId != null) body.job_id = payload.jobId;
  if (payload.hiringManagerId != null)
    body.hiring_manager_id = payload.hiringManagerId;
  if (payload.reportingManagerId != null)
    body.reporting_manager_id = payload.reportingManagerId;
  if (payload.position != null) body.position = payload.position;
  if (payload.salary != null) body.salary = String(payload.salary);
  if (payload.joiningDate != null) body.joining_date = payload.joiningDate;

  const { data } = await apiRequest(`/offer-letter/update/${offerId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return data;
};

export const cancelOfferLetter = async (offerId, reason) => {
  const { data } = await apiRequest(`/offer-letter/cancel/${offerId}`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null }),
  });
  return data;
};

// ========== Candidate Endpoints ==========

export const getMyOffers = async () => {
  const { data } = await apiRequest("/offer-letter/my-offers", {
    method: "GET",
  });
  return data;
};

export const respondToOffer = async (payload) => {
  const { data } = await apiRequest("/offer-letter/respond", {
    method: "POST",
    body: JSON.stringify({
      offer_id: payload.offerId,
      action: payload.action,
      response_message: payload.responseMessage || null,
    }),
  });
  return data;
};

export const generateOfferDoc = async (offerId) => {
  const { data } = await apiRequest(`/offer-letter/generate/${offerId}`, {
    method: "POST",
  });
  return data;
};

export const offerLetterById = async (offerId) => {
  const { data } = await apiRequest(`/offer-letter/${offerId}`, {
    method: "GET",
  });
  return data;
};

export const approveOfferLetter = async (offerId, formData) => {
  const { data } = await apiRequest(
    `/offer-letter/approve/${offerId}?action=approve`,
    {
      method: "POST",
      body: formData,
    },
  );
  return data;
};

export const salaryStructure = async (payload) => {
  const { data } = await apiRequest(`/offer-letter/salary-structure/details`, {
    method: "POST",
    body: JSON.stringify({
      employee_name: payload.employee_name,
      annual_ctc: payload.annual_ctc,
    }),
  });
  return data;
};

export const offerLetterByJobId = async (jobId) => {
  const { data } = await apiRequest(
    `/offer-letter/pending-approval/by-job/${jobId}`,
    {
      method: "GET",
    },
  );
  return data;
};

export const releaseOfferApi = async (offerId) => {
  const { data } = await apiRequest(`/offer-letter/release/${offerId}`, {
    method: "POST",
  });
  return data;
};
