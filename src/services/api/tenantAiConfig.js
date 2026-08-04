// S-077/HRMS-0477 -- Tenant AI Configuration. Unified read/write over
// the org's Thunder settings (identity, engagement timing, SLA
// thresholds, digest, global pause) -- see the backend endpoint's own
// docstring for why this merges Users-backed fields with the new
// TenantAIConfig table rather than a second store for the same setting.
import { apiRequest } from "./client";

export const getTenantAIConfig = async () => {
  const { data } = await apiRequest("/admin/ai-config", { method: "GET" });
  return data;
};

export const updateTenantAIConfig = async (updates) => {
  const { data } = await apiRequest("/admin/ai-config", {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
  return data;
};
