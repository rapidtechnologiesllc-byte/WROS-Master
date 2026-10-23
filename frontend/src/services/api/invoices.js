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

// Delivered outside email (e.g. uploaded to the client's portal): invoice becomes SENT
export const recordExternalDelivery = async (invoiceId, note) => {
  const { data } = await apiRequest(`/invoices/${invoiceId}/record-external-delivery`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
  return data;
};

// The client's payment: bank transaction matched, invoice PAID on paid_on, revenue recognised
export const recordInvoicePayment = async (invoiceId, { paidOn, amountUsdCents, reference }) => {
  const { data } = await apiRequest(`/invoices/${invoiceId}/record-payment`, {
    method: "POST",
    body: JSON.stringify({ paid_on: paidOn, amount_usd_cents: amountUsdCents, reference }),
  });
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

// AR aging: unpaid sent invoices by client, bucketed by days past due (client payment terms)
export const getArAging = async () => {
  const { data } = await apiRequest("/invoices/ar/aging", { method: "GET" });
  if (!data || !Array.isArray(data.clients)) throw new Error("Unexpected response: no AR aging.");
  return data;
};
