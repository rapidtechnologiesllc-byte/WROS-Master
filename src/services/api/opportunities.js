// Opportunity API wrappers (S-236/237/239/240).
import { apiRequest } from "./client";

export const listOpportunities = async ({ stage, clientId } = {}) => {
  const params = new URLSearchParams();
  if (stage) params.set("stage", stage);
  if (clientId) params.set("client_id", clientId);
  const qs = params.toString();
  const { data } = await apiRequest(`/opportunities${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
  return data;
};

export const getPipeline = async () => {
  const { data } = await apiRequest("/opportunities/pipeline", { method: "GET" });
  return data;
};

export const createOpportunity = async (payload) => {
  const { data } = await apiRequest("/opportunities", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const transitionOpportunityStage = async (opportunityId, payload) => {
  const { data } = await apiRequest(`/opportunities/${opportunityId}/transition`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const createRoleDemandFromOpportunity = async (opportunityId, payload) => {
  const { data } = await apiRequest(`/opportunities/${opportunityId}/role-demand`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getOpportunityRevenueRollup = async (opportunityId) => {
  const { data } = await apiRequest(`/opportunities/${opportunityId}/revenue-rollup`, {
    method: "GET",
  });
  return data;
};
