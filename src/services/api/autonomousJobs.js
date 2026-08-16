import { apiRequest } from "./client";

export const getJobClosureStatus = async (jobId) => {
  const { data } = await apiRequest(`/autonomous-jobs/status/${jobId}`, {
    method: "GET",
  });
  return data;
};

export const closeJobManually = async (jobId) => {
  const { data } = await apiRequest(`/autonomous-jobs/close/${jobId}`, {
    method: "POST",
  });
  return data;
};
