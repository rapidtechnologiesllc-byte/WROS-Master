// Job kinds review: jobs the classification could not decide, and classifying one (Admin -> System -> Job Kinds)
import { apiRequest } from "./client";

export const getJobsToClassify = async () => {
  const { data } = await apiRequest("/job-kinds/review", { method: "GET" });
  return data;
};

export const classifyJob = async (jobId, kind, reason) => {
  const { data } = await apiRequest(`/job-kinds/${encodeURIComponent(jobId)}`, {
    method: "PUT",
    body: JSON.stringify({ kind, reason }),
  });
  return data;
};
