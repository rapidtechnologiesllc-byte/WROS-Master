// S-359/HRMS-P511 -- HTD Intake Pause Engine: Conversion Rate Breach.
import { apiRequest } from "./client";

export const calculateMonthlyMetric = async (month) => {
  const { data } = await apiRequest("/htd-intake/calculate-monthly-metric", {
    method: "POST",
    body: JSON.stringify({ month }),
  });
  return data;
};

export const checkHtdBreach = async () => {
  const { data } = await apiRequest("/htd-intake/check-breach", { method: "POST" });
  return data;
};

export const getHtdIntakeStatus = async () => {
  const { data } = await apiRequest("/htd-intake/status", { method: "GET" });
  return data;
};

export const resumeHtdIntake = async (auditFindings, correctiveActions) => {
  const { data } = await apiRequest("/htd-intake/resume", {
    method: "POST",
    body: JSON.stringify({ audit_findings: auditFindings, corrective_actions: correctiveActions }),
  });
  return data;
};

export const getHtdPauseLog = async () => {
  const { data } = await apiRequest("/htd-intake/pause-log", { method: "GET" });
  return data;
};
