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
