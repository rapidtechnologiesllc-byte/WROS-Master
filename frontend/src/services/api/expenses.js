// Partner/BU expense tracking API wrappers, 2026-08-05. Self-service --
// logged_by_user_id is always resolved server-side from the caller's
// own token, never sent from here.
import { apiFetch, apiRequest } from "./client";

export const createExpense = async (payload) => {
  const { data } = await apiRequest("/expenses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const listMyExpenses = async () => {
  const { data } = await apiRequest("/expenses/mine", { method: "GET" });
  return data;
};

export const listAllExpenses = async ({ clientId, purpose } = {}) => {
  const params = new URLSearchParams();
  if (clientId) params.set("client_id", clientId);
  if (purpose) params.set("purpose", purpose);
  const qs = params.toString();
  const { data } = await apiRequest(`/expenses${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
  return data;
};

export const approveExpense = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/approve`, {
    method: "POST",
  });
  return data;
};

// Manager step: once approved the expense counts as a cost in the P&L
export const managerApproveExpense = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/manager-approve`, { method: "POST" });
  return data;
};

export const managerRejectExpense = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/manager-reject`, { method: "POST" });
  return data;
};

export const markExpensePaid = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/mark-paid`, { method: "POST" });
  return data;
};

export const getClientInvestmentPosition = async (clientId) => {
  const { data } = await apiRequest(`/clients/${clientId}/investment-position`, {
    method: "GET",
  });
  return data;
};

// Attach a receipt (image or PDF); the server reads and checks it straight away and returns the
// updated expense (receipt_check_status MATCHED / MISMATCH / UNREADABLE)
export const uploadExpenseReceipt = async (expenseId, file) => {
  const body = new FormData();
  body.append("file", file);
  const { data } = await apiRequest(`/expenses/${expenseId}/receipt`, { method: "POST", body });
  return data;
};

// Open the receipt in a new tab (authenticated download)
export const openExpenseReceipt = async (expenseId) => {
  const response = await apiFetch(`/expenses/${expenseId}/receipt`);
  if (!response.ok) {
    throw new Error(`Receipt download failed (HTTP ${response.status})`);
  }
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
};
