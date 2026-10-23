// Rate card / margin floors by delivery engine, country and role (P&L > Rate Card).
import { apiRequest } from "./client";

export const getMarginPolicies = async () => {
  const { data } = await apiRequest("/margin-policies", { method: "GET" });
  if (!data || !Array.isArray(data.policies)) throw new Error("Unexpected response: no rate card.");
  return data;
};

const toBody = (row) => JSON.stringify({
  delivery_engine: row.delivery_engine,
  country: row.country || null,
  role: row.role || null,
  min_margin_pct: Number(row.min_margin_pct),
  hard_floor_pct: Number(row.hard_floor_pct),
  active: row.active !== false,
});

export const createMarginPolicy = async (row) => {
  const { data } = await apiRequest("/margin-policies", { method: "POST", body: toBody(row) });
  return data;
};

export const updateMarginPolicy = async (id, row) => {
  const { data } = await apiRequest(`/margin-policies/${id}`, { method: "PUT", body: toBody(row) });
  return data;
};

export const deleteMarginPolicy = async (id) => {
  const { data } = await apiRequest(`/margin-policies/${id}`, { method: "DELETE" });
  return data;
};
