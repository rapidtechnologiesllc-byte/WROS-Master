// S-205/HRMS-0107 -- Business Unit context switching API wrapper.
import { apiRequest } from "./client";

export const getMyBUAccess = async () => {
  const { data } = await apiRequest("/bu-context/my-access", { method: "GET" });
  return data;
};

export const switchBU = async (businessUnitId) => {
  const { data } = await apiRequest("/bu-context/switch", {
    method: "POST",
    body: JSON.stringify({ business_unit_id: businessUnitId }),
  });
  return data;
};

export const activateAllBUsView = async () => {
  const { data } = await apiRequest("/bu-context/all-bus", { method: "POST" });
  return data;
};
