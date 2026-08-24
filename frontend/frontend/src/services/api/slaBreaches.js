// S-020/HRMS-0420 -- Engagement SLA Monitoring API wrapper.
import { apiRequest } from "./client";

export const getActiveSLABreaches = async () => {
  const { data } = await apiRequest("/sla/breaches?is_resolved=false", { method: "GET" });
  return data;
};
