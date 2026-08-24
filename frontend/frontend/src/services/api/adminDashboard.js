import { apiRequest } from "./client";

// ============================================================================
// Agent Fear State Dashboard
// ============================================================================

export const getAgentFearDashboard = async () => {
  const { data } = await apiRequest("/admin/agents/fear", { method: "GET" });
  return data;
};

export const getAgentFearState = async (agentName) => {
  const { data } = await apiRequest(`/admin/agents/fear/${agentName}`, { method: "GET" });
  return data;
};

export const checkAgentRetirementStatus = async (agentName) => {
  const { data } = await apiRequest(`/admin/agents/fear/${agentName}/retirement-check`, { method: "GET" });
  return data;
};

// ============================================================================
// Agent Maturity Dashboard
// ============================================================================

export const getAllAgentsMaturities = async () => {
  const { data } = await apiRequest("/admin/agents/maturity", { method: "GET" });
  return data;
};

export const getAgentMaturityDashboard = async (agentName) => {
  const { data } = await apiRequest(`/admin/agents/maturity/${agentName}`, { method: "GET" });
  return data;
};

export const getAgentHealth = async (agentName) => {
  const { data } = await apiRequest(`/admin/agents/${agentName}/health`, { method: "GET" });
  return data;
};
