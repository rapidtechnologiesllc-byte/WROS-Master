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

// The bench drill-down: days on bench, bench loss vs what each person earned while allocated
export const getBench = async ({ group, businessUnitId } = {}) => {
  const params = new URLSearchParams();
  if (group) params.set("group", group);
  if (businessUnitId) params.set("business_unit_id", businessUnitId);
  const qs = params.toString();
  const { data } = await apiRequest(`/workforce/bench${qs ? `?${qs}` : ""}`, { method: "GET" });
  if (!data || !Array.isArray(data.employees)) throw new Error("Unexpected response: no bench list.");
  return data;
};

// Workforce Overview bench groups open the bench screen (no dead tiles)
export const BENCH_PATH = "/workforce/bench";
export const isBenchGroup = (key) => key.startsWith("BENCH_");
export const groupPath = (key) => (isBenchGroup(key) ? `${BENCH_PATH}?group=${key}` : `/workforce/${toSlug(key)}`);
