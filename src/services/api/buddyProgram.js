// S-364 Buddy KPI Tracking + S-365 Graduation Gate API wrapper.
import { apiRequest } from "./client";

export const listBuddyProgramRecords = async () => {
  const { data } = await apiRequest("/buddy-program/records", { method: "GET" });
  return data;
};

export const createBuddyProgramRecord = async (payload) => {
  const { data } = await apiRequest("/buddy-program/records", { method: "POST", body: JSON.stringify(payload) });
  return data;
};

export const getBuddyProgramRecord = async (recordId) => {
  const { data } = await apiRequest(`/buddy-program/records/${recordId}`, { method: "GET" });
  return data;
};

export const submitWeeklyScores = async (recordId, weekNumber, scores) => {
  const { data } = await apiRequest(`/buddy-program/records/${recordId}/scores`, {
    method: "POST",
    body: JSON.stringify({ week_number: weekNumber, scores }),
  });
  return data;
};

export const getScorecard = async (recordId) => {
  const { data } = await apiRequest(`/buddy-program/records/${recordId}/scorecard`, { method: "GET" });
  return data;
};

export const getCanExtend = async (recordId) => {
  const { data } = await apiRequest(`/buddy-program/records/${recordId}/can-extend`, { method: "GET" });
  return data;
};

export const graduateEmployee = async (recordId, notes) => {
  const { data } = await apiRequest(`/buddy-program/records/${recordId}/graduate`, { method: "POST", body: JSON.stringify({ notes }) });
  return data;
};

export const extendProgram = async (recordId, notes) => {
  const { data } = await apiRequest(`/buddy-program/records/${recordId}/extend`, { method: "POST", body: JSON.stringify({ notes }) });
  return data;
};

export const exitProgram = async (recordId, notes) => {
  const { data } = await apiRequest(`/buddy-program/records/${recordId}/exit`, { method: "POST", body: JSON.stringify({ notes }) });
  return data;
};
