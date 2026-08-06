// S-256/HRMS-0506 (canonical) Resource Demand Planning / Future Demand
// vs Bench Forecast.
import { apiRequest } from "./client";

export const getExpiringAllocations = async () => {
  const { data } = await apiRequest("/resource-forecast/expiring", { method: "GET" });
  return data;
};

export const getSkillGapAnalysis = async (businessUnitId) => {
  const suffix = businessUnitId ? `?business_unit_id=${businessUnitId}` : "";
  const { data } = await apiRequest(`/resource-forecast/gap-analysis${suffix}`, { method: "GET" });
  return data;
};
