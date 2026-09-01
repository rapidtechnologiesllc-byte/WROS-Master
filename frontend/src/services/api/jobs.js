// Job management API wrappers.
import {
  apiRequest,
  getApiBaseUrl,
  maybeRedirectOnUnauthorized,
} from "./client";

export const generateJobDescription = async (payload) => {
  const { data } = await apiRequest("/api/v1/jobs/generate_job_description", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const generateJobWithAgent = async (jobDescriptionOneliner) => {
  const { data } = await apiRequest("/api/v1/jobs/generate-with-agent", {
    method: "POST",
    body: JSON.stringify({ job_description_oneliner: jobDescriptionOneliner }),
  });
  return data;
};

export const generateJobComplete = async (jobDescriptionOneliner, answers) => {
  const { data } = await apiRequest("/api/v1/jobs/generate-complete", {
    method: "POST",
    body: JSON.stringify({
      job_description_oneliner: jobDescriptionOneliner,
      answers,
    }),
  });
  return data;
};

export const createJob = async (payload) => {
  const { data } = await apiRequest("/api/v1/jobs/create_job", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getAllJobs = async () => {
  const { data } = await apiRequest("/api/v1/jobs/all", {
    method: "GET",
  });
  return data;
};

export const getActiveJobs = async () => {
  const { data } = await apiRequest("/api/v1/jobs/active-jobs", {
    method: "GET",
    // Public listing used by both Auth and Candidate portal; avoid candidate-token 401 loops.
    skipAuth: true,
  });
  return data;
};

export const updateJob = async (jobId, payload) => {
  const { data } = await apiRequest(`/api/v1/jobs/update_job/${jobId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return data;
};

export const deleteJob = async (jobId) => {
  const { data } = await apiRequest(`/api/v1/jobs/delete_job/${jobId}`, {
    method: "DELETE",
  });
  return data;
};

export const approveJob = async (jobId) => {
  const { data } = await apiRequest(`/api/v1/jobs/${jobId}/approve`, {
    method: "POST",
  });
  return data;
};

export const postJobOnLinkedIn = async (jobId) => {
  const { data } = await apiRequest("/api/v1/jobs/post-on-linkedin", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId }),
  });
  return data;
};

// Public job application endpoint (no auth required), but we include Bearer if present.
// Backend expects multipart/form-data:
// - full_name, email, phone (required)
// - education (JSON string), experience (JSON string), resume (optional file)
export const applyForJob = async ({
  jobId,
  fullName,
  email,
  phone,
  totalExperienceYears,
  currentLocation,
  currentLpa,
  expectedLpa,
  preferredLocation,
  educationEntries = [],
  experienceEntries = [],
  resumeFile,
}) => {
  if (!jobId) throw new Error("jobId is required");
  if (!fullName) throw new Error("fullName is required");
  if (!email) throw new Error("email is required");
  if (!phone) throw new Error("phone is required");

  const formData = new FormData();
  formData.append("full_name", fullName);
  formData.append("email", email);
  formData.append("phone", phone);

  if (totalExperienceYears != null) {
    formData.append("total_experience_years", String(totalExperienceYears));
  }
  if (currentLocation) formData.append("current_location", currentLocation);
  if (currentLpa != null) formData.append("current_lpa", String(currentLpa));
  if (expectedLpa != null) formData.append("expected_lpa", String(expectedLpa));
  if (preferredLocation)
    formData.append("preferred_location", preferredLocation);

  if (educationEntries && educationEntries.length) {
    formData.append("education", JSON.stringify(educationEntries));
  }
  if (experienceEntries && experienceEntries.length) {
    formData.append("experience", JSON.stringify(experienceEntries));
  }
  if (resumeFile) formData.append("resume", resumeFile);

  const token = localStorage.getItem("hrms_token");
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/jobs/${encodeURIComponent(jobId)}/apply`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formData,
    },
  );

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Job application failed.";
    throw new Error(message);
  }

  return data;
};

export const candidateAppendedJob = async (id) => {
  const { data } = await apiRequest(`/api/v1/jobs/${id}/applications`, {
    method: "GET",
  });
  return data;
};

export const assignJob = async (jobId, candidateId, payload) => {
  const { data, response } = await apiRequest(
    `/api/v1/jobs/${jobId}/applications/${candidateId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  return (data, response);
};

export const removeCandidateApi = async (job_id, candidateId) => {
  const { data, response } = await apiRequest(
    `/api/v1/jobs/${job_id}/applications/${candidateId}`,
    {
      method: "DELETE",
    },
  );
  return (data, response);
};

export const assignMultipleJobs = async (job_id, candidate_id, payload) => {
  const { data, response } = await apiRequest(
    `/api/v1/jobs/${job_id}/applications/${candidate_id}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  return (data, response);
};

export const submitCandidateToJob = async (candidate_id, job_id) => {
  const { data, response } = await apiRequest(
    "/api/v1/submissions",
    {
      method: "POST",
      body: JSON.stringify({
        candidate_id: candidate_id,
        demand_id: job_id || job_id, // job_id is the demand_id in this context
        submission_rank: 1,
        source: "hrms",
      }),
    },
  );
  return { data, response };
};

export const jobsFilter = async (parameters) => {
  const { data } = await apiRequest(
    `/api/v1/jobs/filter${parameters ? `?${parameters}` : ""}`,
    {
      method: "GET",
    },
  );
  return data;
};
export const getCandidateApplications = async (candidateId) => {
  const { data } = await apiRequest(
    `/api/v1/jobs/candidate-applications/${candidateId}`,
    {
      method: "GET",
    },
  );
  return data;
};

export const getJobById = async (jobId) => {
  const { data } = await apiRequest(`/api/v1/jobs/job-details/${jobId}`, {
    method: "GET",
  });
  return data;
};
