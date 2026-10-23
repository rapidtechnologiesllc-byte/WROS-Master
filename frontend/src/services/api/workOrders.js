// Work orders (client POs): the client's signed authority to bill a placement. The PO number is
// printed on the invoice; hours after a PO's end date are not invoiced.
import { apiRequest } from "./client";

export const listWorkOrders = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.clientId) params.set("client_id", filters.clientId);
  if (filters.status) params.set("status", filters.status);
  const qs = params.toString();
  const { data } = await apiRequest(`/work-orders${qs ? `?${qs}` : ""}`, { method: "GET" });
  if (!data || !Array.isArray(data.work_orders)) throw new Error("Unexpected response: no work orders list.");
  return data.work_orders;
};

export const createWorkOrder = async (payload) => {
  const { data } = await apiRequest("/work-orders", { method: "POST", body: JSON.stringify(payload) });
  return data;
};

export const updateWorkOrder = async (workOrderId, payload) => {
  const { data } = await apiRequest(`/work-orders/${encodeURIComponent(workOrderId)}`, {
    method: "PATCH", body: JSON.stringify(payload),
  });
  return data;
};

export const changeWorkOrderStatus = async (workOrderId, action, endDate) => {
  const { data } = await apiRequest(`/work-orders/${encodeURIComponent(workOrderId)}/${action}`, {
    method: "POST", body: action === "end" ? JSON.stringify({ end_date: endDate || null }) : undefined,
  });
  return data;
};
