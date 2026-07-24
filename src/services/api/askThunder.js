// Internal "Ask Thunder" query API wrapper (authenticated).
import { apiRequest } from "./client";

export const askThunder = async (message) => {
  const { data } = await apiRequest("/ask-thunder/", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return data;
};
