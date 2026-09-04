// Help Desk/IT-HR Ticketing API wrapper.
import { apiRequest } from "./client";

export const getTicketCategories = async () => {
  const { data } = await apiRequest("/tickets/categories", { method: "GET" });
  return data;
};

export const createTicket = async (payload) => {
  const { data } = await apiRequest("/tickets", { method: "POST", body: JSON.stringify(payload) });
  return data;
};

export const listRoutingRules = async () => {
  const { data } = await apiRequest("/tickets/admin/routing", { method: "GET" });
  return data;
};

export const createRoutingRule = async (payload) => {
  const { data } = await apiRequest("/tickets/admin/routing", { method: "POST", body: JSON.stringify(payload) });
  return data;
};

export const listSLAPolicies = async () => {
  const { data } = await apiRequest("/tickets/admin/sla-policies", { method: "GET" });
  return data;
};

export const updateSLAPolicy = async (priority, payload) => {
  const { data } = await apiRequest(`/tickets/admin/sla-policies/${priority}`, { method: "PATCH", body: JSON.stringify(payload) });
  return data;
};
