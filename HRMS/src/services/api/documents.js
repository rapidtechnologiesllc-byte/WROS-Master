// Document upload helpers (resume and future candidate documents).
import { getApiBaseUrl } from "./client";

export const uploadResume = async ({ candidateId, file }) => {
  if (!candidateId) {
    throw new Error("Candidate ID is required for resume upload.");
  }
  if (!file) {
    throw new Error("Resume file is required.");
  }

  const token = localStorage.getItem("hrms_token");
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${getApiBaseUrl()}/documents/upload/resume?candidate_id=${encodeURIComponent(
      candidateId
    )}`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formData
    }
  );

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    const message = data?.detail || data?.message || "Resume upload failed.";
    throw new Error(message);
  }

  return data;
};
