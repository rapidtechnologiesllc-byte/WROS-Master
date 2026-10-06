// Admin Weekly Recap API wrapper.
import { apiRequest } from "./client";

export const getWeeklyRecap = async (weeksBack = 0) => {
  const { data } = await apiRequest(`/admin/weekly-recap?weeks_back=${weeksBack}`, { method: "GET" });
  return data;
};
