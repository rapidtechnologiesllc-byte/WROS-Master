// S-014/HRMS-0414 -- Message Template Engine API wrappers.
import { apiRequest } from "./client";

export const listTemplates = async ({ channel, templateKey } = {}) => {
  const params = new URLSearchParams();
  if (channel) params.set("channel", channel);
  if (templateKey) params.set("template_key", templateKey);
  const qs = params.toString();
  const { data } = await apiRequest(`/templates${qs ? `?${qs}` : ""}`, { method: "GET" });
  return data;
};

export const createTemplate = async ({ templateKey, templateName, channel, body, subject }) => {
  const { data } = await apiRequest("/templates", {
    method: "POST",
    body: JSON.stringify({
      template_key: templateKey,
      template_name: templateName,
      channel,
      body,
      subject: subject || null,
    }),
  });
  return data;
};

export const activateTemplate = async (templateId) => {
  const { data } = await apiRequest(`/templates/${templateId}/activate`, { method: "POST" });
  return data;
};

export const previewTemplate = async (templateId, candidateId) => {
  const { data } = await apiRequest(
    `/templates/${templateId}/preview?candidate_id=${encodeURIComponent(candidateId)}`,
    { method: "GET" },
  );
  return data;
};
