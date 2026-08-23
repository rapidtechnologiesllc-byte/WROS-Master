// S-063/HRMS-0463 -- Candidate Risk Dashboard API wrapper.
import { apiRequest } from "./client";

export const getRiskDashboard = async () => {
  const { data } = await apiRequest("/risk/dashboard", { method: "GET" });
  return data;
};

export const addCandidateToInterventionQueue = async (candidateId) => {
  const { data } = await apiRequest(`/risk/dashboard/candidates/${candidateId}/add-to-queue`, { method: "POST" });
  return data;
};
