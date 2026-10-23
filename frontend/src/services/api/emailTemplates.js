// Candidate stage email templates (Templates & Checklists > Email Templates; gated by "checklists").
import { apiRequest } from "./client";

// { stages: [{key, label}], placeholders: ["{{candidate_name}}", ...], templates: [...] }
export const listStageEmailTemplates = async () => {
  const { data } = await apiRequest("/email-templates", { method: "GET" });
  return data;
};

export const saveStageEmailTemplate = async (stage, payload) => {
  const { data } = await apiRequest(`/email-templates/${stage}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return data;
};

export const previewStageEmailTemplate = async (stage, { candidateName, jobTitle }) => {
  const query = new URLSearchParams({ candidate_name: candidateName, job_title: jobTitle });
  const { data } = await apiRequest(`/email-templates/${stage}/preview?${query}`, { method: "GET" });
  return data;
};
