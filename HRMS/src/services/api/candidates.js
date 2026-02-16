// Candidate onboarding API wrappers.
import { apiRequest } from "./client";

export const createCandidate = async (payload) => {
  const { data } = await apiRequest("/onboarding/hr/create_candidate", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const getAllCandidates = async () => {
  const { data } = await apiRequest("/onboarding/hr/get_all_candidates", {
    method: "GET"
  });
  return data;
};

export const createCandidateAssignment = async ({
  candidateId,
  hiringManagerId,
  reportingManagerId
}) => {
  const { data } = await apiRequest("/hr/assignments/create", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: candidateId,
      hiring_manager_id: hiringManagerId || null,
      reporting_manager_id: reportingManagerId || null
    })
  });
  return data;
};
