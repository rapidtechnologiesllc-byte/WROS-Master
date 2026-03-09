// Job management API wrappers.
import { apiRequest } from "./client";

export const generateJobDescription = async (payload) => {
  const { data } = await apiRequest("/jobs/generate_job_description", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const createJob = async (payload) => {
  const { data } = await apiRequest("/jobs/create_job", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const getAllJobs = async () => {
  const { data } = await apiRequest("/jobs/all", {
    method: "GET"
  });
  return data;
};

export const updateJob = async (jobId, payload) => {
  const { data } = await apiRequest(`/jobs/update_job/${jobId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  return data;
};

export const deleteJob = async (jobId) => {
  const { data } = await apiRequest(`/jobs/delete_job/${jobId}`, {
    method: "DELETE"
  });
  return data;
};

export const postJobOnLinkedIn = async (jobId) => {
  const { data } = await apiRequest("/jobs/post-on-linkedin", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId })
  });
  return data;
};
