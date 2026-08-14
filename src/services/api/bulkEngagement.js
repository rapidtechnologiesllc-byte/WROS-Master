// S-074/HRMS-0474 -- Bulk Candidate Engagement Launch API wrapper.
import { apiRequest } from "./client";

export const bulkImportCsv = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiRequest("/candidates/bulk-import", { method: "POST", body: formData });
  return data;
};

export const bulkEngage = async (candidateIds) => {
  const { data } = await apiRequest("/candidates/bulk-engage", {
    method: "POST",
    body: JSON.stringify({ candidate_ids: candidateIds }),
  });
  return data;
};

export const getBulkJobStatus = async (jobId) => {
  const { data } = await apiRequest(`/candidates/bulk-jobs/${jobId}/status`, { method: "GET" });
  return data;
};

export const getActiveBulkJobs = async () => {
  const { data } = await apiRequest("/candidates/bulk-import/jobs/active", { method: "GET" });
  return data;
};

export const cancelBulkImportJob = async (jobId) => {
  const { data } = await apiRequest(`/candidates/bulk-import/${jobId}/cancel`, { method: "DELETE" });
  return data;
};
