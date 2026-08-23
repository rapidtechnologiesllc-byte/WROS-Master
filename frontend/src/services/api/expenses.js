// Partner/BU expense tracking API wrappers, 2026-08-05. Self-service --
// logged_by_user_id is always resolved server-side from the caller's
// own token, never sent from here.
import { apiRequest } from "./client";

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

export const getClientInvestmentPosition = async (clientId) => {
  const { data } = await apiRequest(`/clients/${clientId}/investment-position`, {
    method: "GET",
  });
  return data;
};
