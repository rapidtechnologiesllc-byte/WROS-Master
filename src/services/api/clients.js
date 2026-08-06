// Client API wrappers.
import { apiRequest } from "./client";

export const listClients = async ({ activeOnly = true } = {}) => {
  const { data } = await apiRequest(`/clients?active_only=${activeOnly}`, {
    method: "GET",
  });
  return data;
};

export const getClient = async (clientId) => {
  const { data } = await apiRequest(`/clients/${clientId}`, { method: "GET" });
  return data;
};

export const createClient = async (payload) => {
  const { data } = await apiRequest("/clients", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const updateClient = async (clientId, payload) => {
  const { data } = await apiRequest(`/clients/${clientId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getBusinessUnitAssignments = async (businessUnitId) => {
  const { data } = await apiRequest(
    `/clients/business-units/${businessUnitId}/assignments`,
    { method: "GET" }
  );
  return data;
};
