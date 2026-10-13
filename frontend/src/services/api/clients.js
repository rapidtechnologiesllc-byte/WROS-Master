// Client API wrappers.
import { apiRequest } from "./client";

export const listClients = async ({ activeOnly = true } = {}) => {
  const { data } = await apiRequest(`/clients?active_only=${activeOnly}`, {
    method: "GET",
  });
  return data;
};

// Account manager choices: active users from Users & Access Control
export const listAccountManagerOptions = async () => {
  const { data } = await apiRequest("/clients/account-manager-options", { method: "GET" });
  return data?.users || [];
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

export const getClientContacts = async (clientId) => {
  const { data } = await apiRequest(`/clients/${clientId}/contacts`, { method: "GET" });
  return data;
};

export const addClientContact = async (clientId, payload) => {
  const { data } = await apiRequest(`/clients/${clientId}/contacts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

// The BU head for a new job: the head of the BU in the client's company when clientId is given
export const getBusinessUnitAssignments = async (businessUnitId, clientId) => {
  const query = clientId ? `?client_id=${encodeURIComponent(clientId)}` : "";
  const { data } = await apiRequest(
    `/clients/business-units/${businessUnitId}/assignments${query}`,
    { method: "GET" }
  );
  return data;
};
