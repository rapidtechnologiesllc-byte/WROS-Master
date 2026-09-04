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

export const getSubmissionViolations = async () => {
  const { data } = await apiRequest("/submissions/violations", { method: "GET" });
  return data;
};

export const recordClientResponse = async (submissionId, newStatus, clientFeedback) => {
  const { data } = await apiRequest(`/submissions/${submissionId}/client-response`, {
    method: "PATCH",
    body: JSON.stringify({ new_status: newStatus, client_feedback: clientFeedback || undefined }),
  });
  return data;
};
