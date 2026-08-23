// HRMS-1105 (canonical S-320) Resource Management Agent -- bench-scan +
// recommendation queue + pursue/approve/reject.
import { apiRequest } from "./client";

export const triggerBenchScan = async () => {
  const { data } = await apiRequest("/resource-management/scan", {
    method: "POST",
  });
  return data;
};

export const getRecommendationQueue = async () => {
  const { data } = await apiRequest("/resource-management/recommendations", {
    method: "GET",
  });
  return data;
};

export const pursueRecommendation = async (recommendationId) => {
  const { data } = await apiRequest(
    `/resource-management/recommendations/${recommendationId}/pursue`,
    { method: "POST" },
  );
  return data;
};

export const approveRecommendation = async (recommendationId) => {
  const { data } = await apiRequest(
    `/resource-management/recommendations/${recommendationId}/approve`,
    { method: "POST" },
  );
  return data;
};

export const rejectRecommendation = async (recommendationId) => {
  const { data } = await apiRequest(
    `/resource-management/recommendations/${recommendationId}/reject`,
    { method: "POST" },
  );
  return data;
};

// S-253 -- top bench candidates for a demand, by skill match.
export const getMatchingBenchResources = async (demandId) => {
  const { data } = await apiRequest(
    `/resource-management/demands/${demandId}/matching-bench-resources`,
    { method: "GET" },
  );
  return data;
};
