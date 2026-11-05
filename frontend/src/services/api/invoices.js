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

// Auto-invoicing (what the daily job does): drafts every invoice that is due from approved timesheets
export const runAutoInvoicing = async () => {
  const { data } = await apiRequest("/invoices/run-automation", { method: "POST" });
  return data;
};

// Sub-vendor invoices: contractors' approved timesheets, paid only after the client pays
export const getSubVendors = async () => {
  const { data } = await apiRequest("/vendor-invoices/sub-vendors", { method: "GET" });
  return data;
};

export const addSubVendor = async (vendor) => {
  const { data } = await apiRequest("/vendor-invoices/sub-vendors", { method: "POST", body: JSON.stringify(vendor) });
  return data;
};

export const getContractors = async () => {
  const { data } = await apiRequest("/vendor-invoices/contractors", { method: "GET" });
  return data;
};

export const setContractor = async (employeeId, subVendorId, hourlyRateUsdCents) => {
  const { data } = await apiRequest("/vendor-invoices/contractors", {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId, sub_vendor_id: subVendorId, hourly_rate_usd_cents: hourlyRateUsdCents }),
  });
  return data;
};

export const getEligibleVendorTimesheets = async (subVendorId, periodStart, periodEnd) => {
  const params = new URLSearchParams({ sub_vendor_id: subVendorId, period_start: periodStart, period_end: periodEnd });
  const { data } = await apiRequest(`/vendor-invoices/eligible-timesheets?${params}`, { method: "GET" });
  return data;
};

const jsonRequest = async (path, method, body) => {
  const { data } = await apiRequest(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
  return data;
};
export const updateSubVendor = (id, body) => jsonRequest(`/vendor-invoices/sub-vendors/${id}`, "PATCH", body);
export const requestSubVendorW9 = (id) => jsonRequest(`/vendor-invoices/sub-vendors/${id}/request-w9`, "POST");
export const getSubVendorRoles = () => jsonRequest("/vendor-invoices/roles", "GET");
export const getSubVendorSubmissions = () => jsonRequest("/vendor-invoices/submissions", "GET");
export const acceptSubVendorSubmission = (id, body) => jsonRequest(`/vendor-invoices/submissions/${id}/accept`, "POST", body);
export const rejectSubVendorSubmission = (id, note) => jsonRequest(`/vendor-invoices/submissions/${id}/reject`, "POST", { note });

export const getVendorInvoices = async () => {
  const { data } = await apiRequest("/vendor-invoices", { method: "GET" });
  return data;
};

export const addVendorInvoice = async (invoice) => {
  const { data } = await apiRequest("/vendor-invoices", { method: "POST", body: JSON.stringify(invoice) });
  return data;
};

export const approveVendorInvoice = async (id, note) => {
  const { data } = await apiRequest(`/vendor-invoices/${id}/approve`, { method: "POST", body: JSON.stringify({ note }) });
  return data;
};

export const rejectVendorInvoice = async (id, reason) => {
  const { data } = await apiRequest(`/vendor-invoices/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) });
  return data;
};

export const payVendorInvoice = async (id, paidOn, reference) => {
  const { data } = await apiRequest(`/vendor-invoices/${id}/pay`, {
    method: "POST",
    body: JSON.stringify({ paid_on: paidOn, reference }),
  });
  return data;
};
