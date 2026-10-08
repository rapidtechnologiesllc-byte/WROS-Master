// Candidate onboarding API wrappers.
import { apiRequest } from "./client";

export const createCandidate = async (payload) => {
  const { data } = await apiRequest("/candidates/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getAllCandidates = async () => {
  const { data } = await apiRequest("/candidates/all", {
    method: "GET",
  });
  return data;
};

export const updateCandidateThunderEnabled = async (candidateId, enabled) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/thunder-config`, {
    method: "PATCH",
    body: JSON.stringify({ thunder_enabled: enabled }),
  });
  return data;
};

export const getCandidateById = async (candidateId) => {
  const { data } = await apiRequest(`/candidates/${candidateId}`, {
    method: "GET",
  });
  return data;
};

export const createCandidateAssignment = async ({
  candidateId,
  hiringManagerId,
  reportingManagerId,
}) => {
  const { data } = await apiRequest("/hr/assignments/create", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: candidateId,
      hiring_manager_id: hiringManagerId || null,
      reporting_manager_id: reportingManagerId || null,
    }),
  });
  return data;
};

// Fields PUT /candidates/hr/update_candidate/{id} accepts (CandidateUpdateRequest).
// null/undefined are not sent, so a section save only changes its own fields.
const CANDIDATE_UPDATE_FIELDS = [
  "candidate_first_name", "candidate_middle_name", "candidate_last_name",
  "candidate_email", "candidate_mobile", "candidate_gender", "candidate_date_of_birth",
  "candidate_source", "candidate_experience", "candidate_skills", "candidate_joining_date",
  "candidate_notice_period", "candidate_expected_salary", "candidate_current_salary",
  "candidate_current_location", "candidate_job_title", "candidate_employee_type",
  "assigned_hr_manager_id", "assigned_report_manager_id", "assigned_recruiter_id",
];

export const updateCandidate = async (candidateId, payload) => {
  if (!payload) {
    throw new Error("Update payload is required");
  }
  const body = {};
  CANDIDATE_UPDATE_FIELDS.forEach((field) => {
    if (payload[field] != null && payload[field] !== "") body[field] = payload[field];
  });
  // PUT /candidate/{id} (used before) does not exist -- every save 404'd
  const { data } = await apiRequest(`/candidates/hr/update_candidate/${candidateId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return data;
};

export const deleteCandidate = async (candidateId) => {
  const { data } = await apiRequest(
    `/candidates/${candidateId}`,
    {
      method: "DELETE",
    },
  );
  return data;
};

export const updateCandidateStatus = async (candidateId, payload) => {
  const { data, response } = await apiRequest(`/status/${candidateId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getCandidateStatus = async (candidateId) => {
  const { data } = await apiRequest(`/status/${candidateId}`, {
    method: "GET",
  });
  return data;
};

export const getAssignedCandidates = async () => {
  const { data } = await apiRequest("/hr/assignments/candidates", {
    method: "GET",
  });

  return data;
};
export const getCandidateContacts = async (candidateId) => {
  const { data } = await apiRequest(
    `/candidates/hr/candidate/${candidateId}/contacts`,
    {
      method: "GET",
    },
  );

  return data;
};

// HR profile: education / experience lists are saved as a whole
export const saveCandidateEducation = async (candidateId, items) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/education`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
  return data;
};

export const saveCandidateExperience = async (candidateId, items) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/experience`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
  return data;
};

export const saveCandidateSkills = async (candidateId, items) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/skills`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
  return data;
};

export const saveCandidateCertifications = async (candidateId, items) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/certifications`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
  return data;
};

export const saveCandidateQualifications = async (candidateId, items) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/qualifications`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
  return data;
};

export const saveCandidateLicenses = async (candidateId, items) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/licenses`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
  return data;
};
