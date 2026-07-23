// Client API wrappers.
import { apiRequest } from "./client";

export const listClients = async () => {
  const { data } = await apiRequest("/clients", { method: "GET" });
  return data;
};
