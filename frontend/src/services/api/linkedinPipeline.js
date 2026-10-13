// LinkedIn candidate pipeline API wrappers.
import { apiRequest } from "./client";

// Queue a LinkedIn profile: the backend creates the candidate record and a
// follow-up task, or answers ALREADY_EXISTS / ALREADY_QUEUED.
export const queueLinkedInCandidate = async ({ linkedinUrl, firstName, lastName, email }) => {
  const { data } = await apiRequest("/linkedin-candidate-pipeline/linkedin-queue", {
    method: "POST",
    body: JSON.stringify({
      linkedin_url: linkedinUrl,
      first_name: firstName || null,
      last_name: lastName || null,
      email: email || null,
    }),
  });
  return data;
};

export const listLinkedInPipeline = async (statusFilter) => {
  const query = statusFilter && statusFilter !== "all" ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  const { data } = await apiRequest(`/linkedin-candidate-pipeline/list${query}`, { method: "GET" });
  return data;
};

export const completeLinkedInImport = async (pipelineId, { linkedinUrl, phoneNumber, email }) => {
  const { data } = await apiRequest(`/linkedin-candidate-pipeline/${pipelineId}/complete-import`, {
    method: "POST",
    body: JSON.stringify({ linkedin_url: linkedinUrl, phone_number: phoneNumber, email }),
  });
  return data;
};

export const updateLinkedInPipelineStatus = async (pipelineId, status) => {
  const { data } = await apiRequest(`/linkedin-candidate-pipeline/${pipelineId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });
  return data;
};
