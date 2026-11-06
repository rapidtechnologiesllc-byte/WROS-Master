// Workforce Overview: every employee in one group between bench, Staff Aug and Direct.
import { apiRequest } from "./client";

// counts for every group and flag (the dashboard)
export const getWorkforceOverview = async (filters = {}) => {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString();
  const { data } = await apiRequest(`/workforce/overview${query ? `?${query}` : ""}`, { method: "GET" });
  return data;
};

export const getWorkforceFilters = async () => {
  const { data } = await apiRequest("/workforce/overview/filters", { method: "GET" });
  return data;
};

// the people behind one number: { group: "CORE" } or { flag: "rolling_off" }
export const getWorkforceSelection = async ({ group, flag, filters = "" }) => {
  const query = (group ? `group=${encodeURIComponent(group)}` : `flag=${encodeURIComponent(flag)}`) + (filters ? `&${filters}` : "");
  const { data } = await apiRequest(`/workforce/overview?${query}`, { method: "GET" });
  return data;
};

// URL slugs <-> API keys: STAFF_AUG_CORE_CERTIFIED <-> staff-aug-core-certified
export const toSlug = (key) => key.toLowerCase().replace(/_/g, "-");
export const groupKeyFromSlug = (slug) => slug.toUpperCase().replace(/-/g, "_");
export const flagKeyFromSlug = (slug) => slug.toLowerCase().replace(/-/g, "_");

// The bench drill-down: days on bench, bench loss vs what each person earned while allocated
export const getBench = async ({ group, businessUnitId, functionId, companyId, location } = {}) => {
  const params = new URLSearchParams();
  if (group) params.set("group", group);
  if (businessUnitId) params.set("business_unit_id", businessUnitId);
  if (functionId) params.set("function_id", functionId);
  if (companyId) params.set("company_id", companyId);
  if (location) params.set("location", location);
  const qs = params.toString();
  const { data } = await apiRequest(`/workforce/bench${qs ? `?${qs}` : ""}`, { method: "GET" });
  if (!data || !Array.isArray(data.employees)) throw new Error("Unexpected response: no bench list.");
  return data;
};

// Workforce Overview bench groups open the bench screen (no dead tiles)
export const BENCH_PATH = "/workforce/bench";
export const isBenchGroup = (key) => key.startsWith("BENCH_");
export const groupPath = (key) => (isBenchGroup(key) ? `${BENCH_PATH}?group=${key}` : `/workforce/${toSlug(key)}`);
