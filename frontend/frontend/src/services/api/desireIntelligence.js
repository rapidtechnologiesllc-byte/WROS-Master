// S-350/HRMS-P120 -- HR Intelligence Briefing (Candidate Desire Dashboard).
import { apiRequest } from "./client";

export const getDesireIntelligence = async (candidateId) => {
  const { data } = await apiRequest(
    `/candidates/${encodeURIComponent(candidateId)}/desire-intelligence`,
    { method: "GET" },
  );
  return data;
};

export const refreshDesireIntelligence = async (candidateId) => {
  const { data } = await apiRequest(
    `/candidates/${encodeURIComponent(candidateId)}/desire-intelligence/refresh`,
    { method: "POST" },
  );
  return data;
};
