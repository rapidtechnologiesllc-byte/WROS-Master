// EPIC-16 Finance & Accounting Operations -- Fully Loaded Cost,
// Blended Delivery Rate, BU P&L, Reserve Fund, Hiring Affordability,
// Intercompany Ledger.
import { apiRequest } from "./client";

export const setCostRateConfig = async (payload) => {
  const { data } = await apiRequest("/cost-rate-configs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

// Rates per cost object (BU x country), newest first, and the countries a rate can be set for
export const getCostRateConfigs = async () => {
  const { data } = await apiRequest("/cost-rate-configs", { method: "GET" });
  if (!Array.isArray(data)) throw new Error("Unexpected response: no cost-rate list.");
  return data;
};

export const getCostRateCountries = async () => {
  const { data } = await apiRequest("/cost-rate-configs/countries", { method: "GET" });
  if (!data || !Array.isArray(data.countries)) throw new Error("Unexpected response: no countries.");
  return data.countries;
};

export const getFullyLoadedCost = async (employeeId, businessUnitId) => {
  const suffix = businessUnitId ? `?business_unit_id=${businessUnitId}` : "";
  const { data } = await apiRequest(`/employees/${employeeId}/fully-loaded-cost${suffix}`, { method: "GET" });
  return data;
};

export const getBlendedDeliveryRate = async (businessUnitId, year, month) => {
  const { data } = await apiRequest(
    `/blended-delivery-rate/bu/${businessUnitId}?year=${year}&month=${month}`,
    { method: "GET" },
  );
  return data;
};

export const getBuPnl = async (businessUnitId, year, month) => {
  const { data } = await apiRequest(`/pnl/bu/${businessUnitId}?year=${year}&month=${month}`, { method: "GET" });
  return data;
};

export const recordReserveFundEntry = async (payload) => {
  const { data } = await apiRequest("/reserve-fund/entries", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getReserveFundStatus = async (businessUnitId, year, month) => {
  const { data } = await apiRequest(
    `/reserve-fund/bu/${businessUnitId}/status?year=${year}&month=${month}`,
    { method: "GET" },
  );
  return data;
};

export const checkHiringAffordability = async (businessUnitId, proposedAnnualSalaryUsdCents, year, month) => {
  const { data } = await apiRequest(
    `/hiring-affordability/bu/${businessUnitId}?proposed_annual_salary_usd_cents=${proposedAnnualSalaryUsdCents}&year=${year}&month=${month}`,
    { method: "GET" },
  );
  return data;
};

export const recordIntercompanySettlement = async (payload) => {
  const { data } = await apiRequest("/intercompany-settlements", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const listIntercompanySettlements = async () => {
  const { data } = await apiRequest("/intercompany-settlements", { method: "GET" });
  return data;
};

// Link an old settlement (recorded by free-text name that matched no company) to its companies
export const linkIntercompanySettlement = async (settlementId, fromCompanyId, toCompanyId) => {
  const { data } = await apiRequest(`/intercompany-settlements/${settlementId}/link-companies`, {
    method: "POST",
    body: JSON.stringify({ from_company_id: fromCompanyId, to_company_id: toCompanyId }),
  });
  return data;
};

// Bank reconciliation: unmatched bank credits, each with the sent invoices for exactly that amount and the
// one suggested, plus paid invoices that no bank credit confirms
export const getBankReconciliation = async () => {
  const { data } = await apiRequest("/bank-transactions/reconciliation", { method: "GET" });
  if (!data || !Array.isArray(data.transactions) || !Array.isArray(data.unmatched_paid_invoices)) {
    throw new Error("Unexpected response: no bank reconciliation.");
  }
  return data;
};

// A bank statement saved as CSV: every credit is recorded once (uploading the same file again adds nothing)
export const importBankStatement = async (file) => {
  const body = new FormData();
  body.append("file", file);
  const { data } = await apiRequest("/bank-transactions/import", { method: "POST", body });
  return data;
};

export const recordBankCredit = async ({ transactionDate, amountUsdCents, description }) => {
  const { data } = await apiRequest("/bank-transactions", {
    method: "POST",
    body: JSON.stringify({ transaction_date: transactionDate, amount_usd_cents: amountUsdCents, description }),
  });
  return data;
};

// Finance confirms the match: a sent invoice becomes paid on the date of the credit, revenue recognised
export const matchBankCredit = async (transactionId, invoiceId) => {
  const { data } = await apiRequest(`/bank-transactions/${transactionId}/match`, {
    method: "POST",
    body: JSON.stringify({ invoice_id: invoiceId }),
  });
  return data;
};

// Net intercompany position of one company (by its id: settlements reference companies, not names)
export const getCompanyNetPosition = async (companyId) => {
  const { data } = await apiRequest(`/intercompany-settlements/company/${encodeURIComponent(companyId)}/net-position`, {
    method: "GET",
  });
  return data;
};
