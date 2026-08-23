// Candidate account + pipeline status (HR).
import { apiRequest } from "./client";

export const getCandidateStatus = async (candidateId) => {
  const { data } = await apiRequest(
    `/status/${encodeURIComponent(candidateId)}`,
    { method: "GET" }
  );
  return data;
};

export const getAllCandidateStatuses = async () => {
  const { data } = await apiRequest("/status/all", { method: "GET" });
  return data;
};

export const updateCandidateStatus = async (candidateId, { status, pipeline_status: pipelineStatus }) => {
  const body = {};
  if (status != null && status !== "") body.status = status;
  if (pipelineStatus != null && pipelineStatus !== "") body.pipeline_status = pipelineStatus;
  const { data } = await apiRequest(`/status/${encodeURIComponent(candidateId)}`, {
    method: "PUT",
    body: JSON.stringify(body)
  });
  return data;
};
