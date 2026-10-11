import { apiRequest } from "./client";

// Projected vs actual revenue, anticipated vs actual expense (scoped server-side by role template)
export const getFinancialOutlook = async ({ period = "month", year, month, businessUnitId } = {}) => {
  const params = new URLSearchParams({ period });
  if (year) params.set("year", String(year));
  if (month) params.set("month", String(month));
  if (businessUnitId) params.set("business_unit_id", String(businessUnitId));
  const { data } = await apiRequest(`/finance/outlook?${params.toString()}`, { method: "GET" });
  return data;
};
