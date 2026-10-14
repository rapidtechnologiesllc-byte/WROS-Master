// Workforce Overview: every employee in one group between bench, Staff Aug and Core.
import { apiRequest } from "./client";

export const getWorkforceOverview = async () => {
  const { data } = await apiRequest("/workforce/overview", { method: "GET" });
  return data;
};
