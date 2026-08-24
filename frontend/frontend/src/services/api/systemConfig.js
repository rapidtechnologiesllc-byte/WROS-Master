// S-213/HRMS-0115 -- System Configuration & Admin Settings Panel.
import { apiRequest } from "./client";

export const getSettingsPanel = async () => {
  const { data } = await apiRequest("/system-config/settings", { method: "GET" });
  return data;
};

export const updateSetting = async (configKey, value) => {
  const { data } = await apiRequest(`/system-config/settings/${configKey}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
  return data;
};

export const updateLocale = async (updates) => {
  const { data } = await apiRequest("/system-config/locale", {
    method: "PUT",
    body: JSON.stringify(updates),
  });
  return data;
};
