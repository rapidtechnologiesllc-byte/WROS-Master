// Workforce Overview: every employee in one group between bench, Staff Aug and Core.
import { apiRequest } from "./client";

// counts for every group and flag (the dashboard)
export const getWorkforceOverview = async () => {
  const { data } = await apiRequest("/workforce/overview", { method: "GET" });
  return data;
};

// the people behind one number: { group: "CORE" } or { flag: "rolling_off" }
export const getWorkforceSelection = async ({ group, flag }) => {
  const query = group ? `group=${encodeURIComponent(group)}` : `flag=${encodeURIComponent(flag)}`;
  const { data } = await apiRequest(`/workforce/overview?${query}`, { method: "GET" });
  return data;
};

// URL slugs <-> API keys: STAFF_AUG_CORE_CERTIFIED <-> staff-aug-core-certified
export const toSlug = (key) => key.toLowerCase().replace(/_/g, "-");
export const groupKeyFromSlug = (slug) => slug.toUpperCase().replace(/-/g, "_");
export const flagKeyFromSlug = (slug) => slug.toLowerCase().replace(/-/g, "_");
