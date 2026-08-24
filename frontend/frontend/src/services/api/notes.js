import { apiRequest } from "./client";

export const getCandidateNotes = async (candidateId) => {
  const { data } = await apiRequest(
    `/internal/notes/${encodeURIComponent(candidateId)}`,
    {
      method: "GET",
    },
  );

  return data;
};

export const createCandidateNote = async (candidateId, payload) => {
  const { data } = await apiRequest(
    `/internal/notes/${encodeURIComponent(candidateId)}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

  return data;
};
