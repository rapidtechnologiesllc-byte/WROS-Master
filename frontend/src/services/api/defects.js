// Reported issues: report one from the app (Ask Flash -> Report an Issue) and work the HRMS issue log
// (Admin -> System -> Reported Issues). Stored in HRMS; nothing is sent to an outside tracker.
import { apiRequest } from "./client";

export const reportDefect = async (description, affected_screen, severity = "MEDIUM", blocking_production = false) => {
  const { data } = await apiRequest("/defects/report", {
    method: "POST",
    body: JSON.stringify({
      description,
      affected_screen,
      severity,
      blocking_production,
    }),
  });
  return data;
};

export const listReportedIssues = async (status) => {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const { data } = await apiRequest(`/defects${query}`, { method: "GET" });
  return data;
};

export const getReportedIssue = async (id) => {
  const { data } = await apiRequest(`/defects/${id}`, { method: "GET" });
  return data;
};

export const updateReportedIssue = async (id, changes) => {
  const { data } = await apiRequest(`/defects/${id}`, { method: "PUT", body: JSON.stringify(changes) });
  return data;
};

export const commentOnReportedIssue = async (id, body) => {
  const { data } = await apiRequest(`/defects/${id}/comments`, { method: "POST", body: JSON.stringify({ body }) });
  return data;
};
