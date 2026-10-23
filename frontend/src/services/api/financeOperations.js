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

// Net intercompany position of one company (by its id: settlements reference companies, not names)
export const getCompanyNetPosition = async (companyId) => {
  const { data } = await apiRequest(`/intercompany-settlements/company/${encodeURIComponent(companyId)}/net-position`, {
    method: "GET",
  });
  return data;
};
