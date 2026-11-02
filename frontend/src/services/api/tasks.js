// S-434 -- org-wide Task Dashboard API wrapper.
import { apiRequest } from "./client";

export const getMyDayTasks = async () => {
  const { data } = await apiRequest("/tasks/my-day", { method: "GET" });
  return data;
};

export const getUpcomingUrgentTasks = async () => {
  const { data } = await apiRequest("/tasks/my-day/upcoming", { method: "GET" });
  return data;
};

export const createTask = async (payload) => {
  const { data } = await apiRequest("/tasks", { method: "POST", body: JSON.stringify(payload) });
  return data;
};

export const confirmUrgentTask = async (taskId) => {
  const { data } = await apiRequest(`/tasks/${taskId}/confirm-urgent`, { method: "POST" });
  return data;
};

export const completeTask = async (taskId) => {
  const { data } = await apiRequest(`/tasks/${taskId}/complete`, { method: "POST" });
  return data;
};

export const getScheduledTasks = async () => {
  const { data } = await apiRequest("/tasks/my-day/scheduled", { method: "GET" });
  return data;
};

export const getTaskUpdateOptions = async () => {
  const { data } = await apiRequest("/tasks/update-options", { method: "GET" });
  return data;
};

export const getTaskUpdates = async (taskId) => {
  const { data } = await apiRequest(`/tasks/${taskId}/updates`, { method: "GET" });
  return data?.updates || [];
};

export const logTaskUpdate = async (taskId, payload) => {
  const { data } = await apiRequest(`/tasks/${taskId}/updates`, { method: "POST", body: JSON.stringify(payload) });
  return data;
};

// Comment thread on a task (approval decisions post their note here too)
export const getTaskComments = async (taskId) => {
  const { data } = await apiRequest(`/tasks/${taskId}/comments`, { method: "GET" });
  if (!data || !Array.isArray(data.comments)) throw new Error("Unexpected response: no comments list.");
  return data.comments;
};

export const addTaskComment = async (taskId, body) => {
  const { data } = await apiRequest(`/tasks/${taskId}/comments`, { method: "POST", body: JSON.stringify({ body }) });
  return data;
};

export const getTaskOptions = async () => {
  const { data } = await apiRequest("/tasks/options", { method: "GET" });
  return data;
};

export const getCandidateTasks = async (candidateId) => {
  const { data } = await apiRequest(`/tasks/candidate/${encodeURIComponent(candidateId)}`, { method: "GET" });
  return data;
};

export const stopRepeatingTask = async (taskId) => {
  const { data } = await apiRequest(`/tasks/${taskId}/stop-repeating`, { method: "POST" });
  return data;
};

// The reply the system drafted for a task's candidate email (null when there is none)
export const getTaskReplyDraft = async (taskId) => {
  const { data } = await apiRequest(`/tasks/${taskId}/reply-draft`, { method: "GET" });
  return data;
};

// Send the drafted reply (edited text optional); the task closes once Thunder has sent it
export const approveTaskReplyDraft = async (taskId, text) => {
  const { data } = await apiRequest(`/tasks/${taskId}/reply-draft/approve`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  return data;
};

export const discardTaskReplyDraft = async (taskId) => {
  const { data } = await apiRequest(`/tasks/${taskId}/reply-draft/discard`, { method: "POST" });
  return data;
};
