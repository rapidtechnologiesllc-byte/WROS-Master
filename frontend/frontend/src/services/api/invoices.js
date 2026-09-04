// HRMS-0907 -- Invoice Generation, Status Tracking.
import { apiRequest } from "./client";

export const generateInvoice = async (projectId, periodStart, periodEnd) => {
  const { data } = await apiRequest("/invoices/generate", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, period_start: periodStart, period_end: periodEnd }),
  });
  return data;
};

export const approveInvoice = async (invoiceId) => {
  const { data } = await apiRequest(`/invoices/${invoiceId}/approve`, { method: "POST" });
  return data;
};

export const sendInvoice = async (invoiceId) => {
  const { data } = await apiRequest(`/invoices/${invoiceId}/send`, { method: "POST" });
  return data;
};

export const markInvoicePaid = async (invoiceId) => {
  const { data } = await apiRequest(`/invoices/${invoiceId}/mark-paid`, { method: "POST" });
  return data;
};

export const getInvoices = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.projectId) params.set("project_id", filters.projectId);
  if (filters.clientId) params.set("client_id", filters.clientId);
  if (filters.status) params.set("status", filters.status);
  const qs = params.toString();
  const { data } = await apiRequest(`/invoices${qs ? `?${qs}` : ""}`, { method: "GET" });
  return data;
};
