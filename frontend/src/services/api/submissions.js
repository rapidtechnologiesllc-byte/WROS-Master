// HRMS-0711 Client Submission Pipeline. Also closes canonical S-249
// ("Restrict Market Candidate Submission") -- the market-profile guard
// is enforced server-side inside submitCandidate() already.
import { apiRequest } from "./client";

export const submitCandidate = async ({ demandId, candidateId, submissionRank, source }) => {
  const { data } = await apiRequest("/submissions", {
    method: "POST",
    body: JSON.stringify({
      demand_id: demandId,
      candidate_id: candidateId,
      submission_rank: submissionRank || undefined,
      source: source || "INTERNAL",
    }),
  });
  return data;
};

export const getSubmissions = async (demandId) => {
  const path = demandId ? `/submissions?demand_id=${encodeURIComponent(demandId)}` : "/submissions";
  const { data } = await apiRequest(path, { method: "GET" });
  return data;
};

// Open client jobs and bench/active/allocated employees in the caller's scope; each
// candidate carries the experience / employment-type issues that would block it.
export const getSubmissionOptions = async () => {
  const { data } = await apiRequest("/submissions/options", { method: "GET" });
  return data;
};

export const getSubmissionViolations = async () => {
  const { data } = await apiRequest("/submissions/violations", { method: "GET" });
  return data;
};

export const recordClientResponse = async (submissionId, newStatus, clientFeedback) => {
  const { data } = await apiRequest(`/submissions/${submissionId}/client-response`, {
    method: "POST",
    body: JSON.stringify({ new_status: newStatus, client_feedback: clientFeedback || undefined }),
  });
  return data;
};

// Internal submissions: market candidates on jobs, moving through the hiring pipeline to the bench.
export const getInternalSubmissions = async () => {
  const { data } = await apiRequest("/submissions/internal", { method: "GET" });
  return data;
};

// What the candidate's submit button does now (SUBMIT_TO_JOB / SUBMIT_TO_CLIENT / NONE) and why.
export const getSubmissionReadiness = async (candidateId, demandId) => {
  const query = demandId ? `?demand_id=${encodeURIComponent(demandId)}` : "";
  const { data } = await apiRequest(`/submissions/readiness/${encodeURIComponent(candidateId)}${query}`, {
    method: "GET",
  });
  return data;
};
