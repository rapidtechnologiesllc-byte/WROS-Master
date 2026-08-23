// S-059/HRMS-0459 -- Candidate Journey Dashboard API wrapper.
import { apiRequest } from "./client";

export const getCandidateJourney = async (candidateId) => {
  const { data } = await apiRequest(`/candidates/${candidateId}/journey`, {
    method: "GET",
  });
  return data;
};
