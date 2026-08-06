// S-267 BU Revenue Target + PartnerGoal + S-241 Executive Dashboard +
// S-244 Pipeline Coverage.
import { apiRequest } from "./client";

export const getExecutiveDashboard = async () => {
  const { data } = await apiRequest("/revenue-targets/dashboard", { method: "GET" });
  return data;
};

export const getPipelineCoverage = async (revenueTargetUsdCents) => {
  const { data } = await apiRequest(
    `/revenue-targets/pipeline-coverage?revenue_target_usd_cents=${revenueTargetUsdCents}`,
    { method: "GET" },
  );
  return data;
};

export const createBuTarget = async (payload) => {
  const { data } = await apiRequest("/revenue-targets/bu", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getBuTarget = async (businessUnitId, targetPeriod, fiscalYear) => {
  const { data } = await apiRequest(
    `/revenue-targets/bu/${businessUnitId}?target_period=${targetPeriod}&fiscal_year=${fiscalYear}`,
    { method: "GET" },
  );
  return data;
};

export const createPartnerGoal = async (payload) => {
  const { data } = await apiRequest("/revenue-targets/partner-goals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getPartnerPosition = async (partnerUserId) => {
  const { data } = await apiRequest(`/revenue-targets/partners/${partnerUserId}/position`, {
    method: "GET",
  });
  return data;
};
