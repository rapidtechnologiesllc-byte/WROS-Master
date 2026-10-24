// Employee performance: reviews, peer praise / feedback, internal notes (backend /performance).
import { apiFetch, apiRequest } from "./client";

export const getEmployeePerformance = async (employeeId) => {
  const { data } = await apiRequest(`/performance/employees/${employeeId}`, { method: "GET" });
  return data;
};

export const getMyPerformance = async () => {
  const { data } = await apiRequest("/performance/me", { method: "GET" });
  return data;
};

export const getColleagues = async () => {
  const { data } = await apiRequest("/performance/colleagues", { method: "GET" });
  return data.colleagues;
};

// { rating, summary, strengths, improvements, goals, visibility, complete }
export const writeReview = async (reviewId, body) => {
  const { data } = await apiRequest(`/performance/reviews/${reviewId}`, { method: "PUT", body: JSON.stringify(body) });
  return data;
};

export const uploadRecording = async (reviewId, file) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiRequest(`/performance/reviews/${reviewId}/recording`, { method: "POST", body: form });
  return data;
};

export const linkRecording = async (reviewId, url) => {
  const { data } = await apiRequest(`/performance/reviews/${reviewId}/recording-link`, {
    method: "PUT", body: JSON.stringify({ url }),
  });
  return data;
};

// The stored recording as a blob URL the page can play (the download needs the auth header)
export const recordingBlobUrl = async (reviewId) => {
  const response = await apiFetch(`/performance/reviews/${reviewId}/recording`);
  if (!response.ok) throw new Error(`Could not load the recording (HTTP ${response.status})`);
  return URL.createObjectURL(await response.blob());
};

export const giveFeedback = async (employeeId, { kind, body, anonymous }) => {
  const { data } = await apiRequest(`/performance/employees/${employeeId}/feedback`, {
    method: "POST", body: JSON.stringify({ kind, body, anonymous }),
  });
  return data;
};

export const addNote = async (employeeId, body) => {
  const { data } = await apiRequest(`/performance/employees/${employeeId}/notes`, {
    method: "POST", body: JSON.stringify({ body }),
  });
  return data;
};
