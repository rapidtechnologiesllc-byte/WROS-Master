// Candidate onboarding API wrappers.
import { apiRequest } from "./client";

export const createCandidate = async (payload) => {
  const { data } = await apiRequest("/onboarding/hr/create_candidate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getAllCandidates = async () => {
  const { data } = await apiRequest("/onboarding/hr/get_all_candidates", {
    method: "GET",
  });
  return data;
};

export const getCandidateById = async (candidateId) => {
  const { data } = await apiRequest(`/onboarding/hr/candidate/${candidateId}`, {
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

export const updateCandidate = async (candidateId, payload) => {
  const body = {};
  if (payload.candidate_job_title != null)
    body.candidate_job_title = payload.candidate_job_title;
  if (payload.candidate_first_name != null)
    body.candidate_first_name = payload.candidate_first_name;
  if (payload.candidate_middle_name != null)
    body.candidate_middle_name = payload.candidate_middle_name;
  if (payload.candidate_last_name != null)
    body.candidate_last_name = payload.candidate_last_name;
  if (payload.candidate_mobile != null)
    body.candidate_mobile = payload.candidate_mobile;
  if (payload.candidate_gender != null)
    body.candidate_gender = payload.candidate_gender;
  if (payload.candidate_date_of_birth != null)
    body.candidate_date_of_birth = payload.candidate_date_of_birth;
  if (payload.candidate_source != null)
    body.candidate_source = payload.candidate_source;
  if (payload.candidate_experience != null)
    body.candidate_experience = payload.candidate_experience;
  if (payload.candidate_skills != null)
    body.candidate_skills = payload.candidate_skills;
  if (payload.candidate_joining_date != null)
    body.candidate_joining_date = payload.candidate_joining_date;
  if (payload.candidate_expected_salary != null)
    body.candidate_expected_salary = payload.candidate_expected_salary;
  if (payload.candidate_current_salary != null)
    body.candidate_current_salary = payload.candidate_current_salary;
  if (payload.candidate_current_location != null)
    body.candidate_current_location = payload.candidate_current_location;
  if (payload.assigned_hr_manager_id != null)
    body.assigned_hr_manager_id = payload.assigned_hr_manager_id;
  if (payload.assigned_report_manager_id != null)
    body.assigned_report_manager_id = payload.assigned_report_manager_id;

  const { data } = await apiRequest(
    `/onboarding/hr/update_candidate/${candidateId}`,
    {
      method: "PUT",
      body: JSON.stringify(body),
    },
  );
  return data;
};

export const deleteCandidate = async (candidateId) => {
  const { data } = await apiRequest(
    `/onboarding/hr/delete_candidate/${candidateId}`,
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
    `/onboarding/hr/candidate/${candidateId}/contacts`,
    {
      method: "GET",
    },
  );

  return data;
};
