// Defect reporting API - logs user-reported production issues
import { apiRequest } from "./client";

export const reportDefect = async (description, affected_screen, severity = "MEDIUM") => {
  const { data } = await apiRequest("/defects/report", {
    method: "POST",
    body: JSON.stringify({
      description,
      affected_screen,
      severity,
    }),
  });
  return data;
};
