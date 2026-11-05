import { apiRequest } from "./client";

export const getTemplateCatalog = async () => {
  const { data } = await apiRequest("/template-catalog", { method: "GET" });
  return data;
};

export const saveCatalogTemplate = async (store, id, payload) => {
  const { data } = await apiRequest(`/template-catalog/${store}/${id}`, { method: "PUT", body: JSON.stringify(payload) });
  return data;
};
