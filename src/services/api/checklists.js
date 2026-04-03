// HR checklist templates, assignment, completion; candidate self-service checklist.
import { apiRequest } from "./client";

export const listChecklistTemplates = async () => {
  const { data } = await apiRequest("/checklist/hr/templates", { method: "GET" });
  return data;
};

export const getChecklistTemplate = async (templateId) => {
  const { data } = await apiRequest(`/checklist/hr/templates/${templateId}`, {
    method: "GET"
  });
  return data;
};

export const createChecklistTemplate = async (payload) => {
  const { data } = await apiRequest("/checklist/hr/templates", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const updateChecklistTemplate = async (templateId, payload) => {
  const { data } = await apiRequest(`/checklist/hr/templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  return data;
};

export const deleteChecklistTemplate = async (templateId) => {
  const { data } = await apiRequest(`/checklist/hr/templates/${templateId}`, {
    method: "DELETE"
  });
  return data;
};

export const addChecklistTemplateItem = async (templateId, payload) => {
  const { data } = await apiRequest(`/checklist/hr/templates/${templateId}/items`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const updateChecklistTemplateItem = async (templateId, itemId, payload) => {
  const { data } = await apiRequest(
    `/checklist/hr/templates/${templateId}/items/${itemId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload)
    }
  );
  return data;
};

export const deleteChecklistTemplateItem = async (templateId, itemId) => {
  const { data } = await apiRequest(
    `/checklist/hr/templates/${templateId}/items/${itemId}`,
    { method: "DELETE" }
  );
  return data;
};

export const assignChecklistToCandidate = async ({ candidateId, templateId }) => {
  const { data } = await apiRequest("/checklist/hr/assign", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: candidateId,
      template_id: Number(templateId)
    })
  });
  return data;
};

export const getCandidateChecklists = async (candidateId) => {
  const { data } = await apiRequest(
    `/checklist/hr/candidate/${encodeURIComponent(candidateId)}`,
    { method: "GET" }
  );
  return data;
};

export const hrCompleteChecklistItem = async (itemId) => {
  const { data } = await apiRequest(`/checklist/hr/candidate-item/${itemId}/complete`, {
    method: "PUT"
  });
  return data;
};

export const getMyChecklists = async () => {
  const { data } = await apiRequest("/checklist/candidate/my-checklists", {
    method: "GET",
    // Some candidates do not have checklist assignments yet.
    allow404: true,
    allowStatuses: [401]
  });
  return data;
};

export const candidateCompleteChecklistItem = async (itemId) => {
  const { data } = await apiRequest(`/checklist/candidate/item/${itemId}/complete`, {
    method: "PUT"
  });
  return data;
};
