// S-014/HRMS-0414 -- Message Template Engine API wrappers.
import { apiRequest } from "./client";

export const listTemplates = async ({ channel, templateKey } = {}) => {
  // GET /message-templates takes no filters; filter here
  const { data } = await apiRequest("/message-templates", { method: "GET" });
  const rows = Array.isArray(data) ? data : [];
  return {
    templates: rows.filter((t) => (!channel || t.channel === channel) && (!templateKey || t.template_key === templateKey)),
  };
};

export const createTemplate = async ({ templateKey, templateName, channel, body, subject }) => {
  const { data } = await apiRequest(`/message-templates/${encodeURIComponent(templateKey)}`, {
    method: "POST",
    body: JSON.stringify({
      template_name: templateName,
      channel,
      body,
      subject: subject || null,
    }),
  });
  return data;
};

export const activateTemplate = async (templateId) => {
  const { data } = await apiRequest(`/message-templates/${templateId}/activate`, { method: "POST" });
  return data;
};

export const previewTemplate = async (templateId, candidateId) => {
  const { data } = await apiRequest(
    `/message-templates/${templateId}/preview?candidate_id=${encodeURIComponent(candidateId)}`,
    { method: "GET" },
  );
  return data;
};
