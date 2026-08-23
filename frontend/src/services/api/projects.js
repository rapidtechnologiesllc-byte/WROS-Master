// HRMS-0801 (Project Lifecycle) + HRMS-0804 (Milestones) + HRMS-0805
// (Unfilled Roles) + HRMS-0806 (Revenue Estimate) + S-358/HRMS-0519
// (SI Partner Engagement Tagging).
import { apiRequest } from "./client";

export const createProject = async (body) => {
  const { data } = await apiRequest("/projects", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data;
};

export const getProjects = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.clientId) params.set("client_id", filters.clientId);
  if (filters.status) params.set("status", filters.status);
  const qs = params.toString();
  const { data } = await apiRequest(`/projects${qs ? `?${qs}` : ""}`, { method: "GET" });
  return data;
};

export const transitionProjectStatus = async (projectId, status) => {
  const { data } = await apiRequest(`/projects/${projectId}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
  return data;
};

export const createMilestone = async (projectId, body) => {
  const { data } = await apiRequest(`/projects/${projectId}/milestones`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data;
};

export const getMilestones = async (projectId) => {
  const { data } = await apiRequest(`/projects/${projectId}/milestones`, { method: "GET" });
  return data;
};

export const completeMilestone = async (projectId, milestoneId, completionDate) => {
  const { data } = await apiRequest(`/projects/${projectId}/milestones/${milestoneId}/complete`, {
    method: "POST",
    body: JSON.stringify({ completion_date: completionDate || undefined }),
  });
  return data;
};

export const getUnfilledRoles = async (projectId) => {
  const { data } = await apiRequest(`/projects/${projectId}/unfilled-roles`, { method: "GET" });
  return data;
};

export const getExpectedRevenue = async (projectId) => {
  const { data } = await apiRequest(`/projects/${projectId}/expected-revenue`, { method: "GET" });
  return data;
};
