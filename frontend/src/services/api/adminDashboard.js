import { apiRequest } from "./client";

// Agent Fear State Dashboard







// Agent Maturity Dashboard

export const getAllAgentsMaturities = async () => {
  const { data } = await apiRequest("/admin/agents/maturity", { method: "GET" });
  return data;
};

export const getAgentMaturityDashboard = async (agentName) => {
  const { data } = await apiRequest(`/admin/agents/maturity/${agentName}`, { method: "GET" });
  return data;
};


