// S-356/HRMS-0517 -- Employee Milestone Tracker: Personal, Project & Org.
import { apiRequest } from "./client";

export const createEmployeeMilestone = async (body) => {
  const { data } = await apiRequest("/employee-milestones", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data;
};

export const getEmployeeMilestones = async (employeeId) => {
  const { data } = await apiRequest(`/employee-milestones/employee/${employeeId}`, { method: "GET" });
  return data;
};

export const completeEmployeeMilestone = async (milestoneId, completionNotes) => {
  const { data } = await apiRequest(`/employee-milestones/${milestoneId}/complete`, {
    method: "POST",
    body: JSON.stringify({ completion_notes: completionNotes || undefined }),
  });
  return data;
};

export const scanOverdueMilestones = async () => {
  const { data } = await apiRequest("/employee-milestones/scan-overdue", { method: "POST" });
  return data;
};
