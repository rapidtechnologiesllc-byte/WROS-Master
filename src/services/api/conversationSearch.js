// S-015/HRMS-0415 -- Conversation Search API wrapper.
import { apiRequest } from "./client";

export const searchConversations = async ({ q, channel, dateFrom, dateTo, page = 1, perPage = 20 }) => {
  const params = new URLSearchParams({ q, page: String(page), per_page: String(perPage) });
  if (channel) params.set("channel", channel);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const { data } = await apiRequest(`/conversations/search?${params.toString()}`, { method: "GET" });
  return data;
};
