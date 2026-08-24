// S-215/HRMS-0117 -- Error Logging Framework API wrapper.
import { apiRequest } from "./client";

export const getErrorLog = async ({ severity, integrationName } = {}) => {
  const params = new URLSearchParams();
  if (severity) params.set("severity", severity);
  if (integrationName) params.set("integration_name", integrationName);
  const qs = params.toString();
  const { data } = await apiRequest(`/error-log${qs ? `?${qs}` : ""}`, { method: "GET" });
  return data;
};
