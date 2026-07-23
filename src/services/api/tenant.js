// S-219/HRMS-0121 -- Multi-Continent Locale & Currency Config.
import { apiRequest } from "./client";

export const getTenantLocale = async () => {
  const { data } = await apiRequest("/tenants/me/locale", { method: "GET" });
  return data;
};

export const updateTenantLocale = async (fields) => {
  const { data } = await apiRequest("/tenants/me/locale", {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
  return data;
};
