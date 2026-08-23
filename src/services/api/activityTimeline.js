// S-216/HRMS-0118 -- Shared Activity Timeline & File Attachment Framework.
// Generic: works for any entity_type/entity_id, no per-entity API needed.
import { apiRequest } from "./client";

export const getTimeline = async (entityType, entityId, { page = 1, perPage = 25 } = {}) => {
  const { data } = await apiRequest(
    `/activity-timeline/${entityType}/${entityId}?page=${page}&per_page=${perPage}`,
    { method: "GET" },
  );
  return data;
};

export const postTimelineEntry = async (entityType, entityId, action, description) => {
  const { data } = await apiRequest(`/activity-timeline/${entityType}/${entityId}`, {
    method: "POST",
    body: JSON.stringify({ action, description }),
  });
  return data;
};

export const listFiles = async (entityType, entityId) => {
  const { data } = await apiRequest(`/file-uploads/${entityType}/${entityId}`, { method: "GET" });
  return data;
};

export const uploadFile = async (entityType, entityId, file, fileCategory = "GENERIC") => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiRequest(
    `/file-uploads/${entityType}/${entityId}?file_category=${encodeURIComponent(fileCategory)}`,
    { method: "POST", body: form },
  );
  return data;
};

export const getFileAccessUrl = async (fileId) => {
  const { data } = await apiRequest(`/file-uploads/${fileId}/access-url`, { method: "GET" });
  return data;
};
