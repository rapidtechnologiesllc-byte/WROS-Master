// S-015/S-016 (HRMS-0415/0416) -- Conversation Search + Filters API wrapper.
import { apiRequest } from "./client";

export const searchConversations = async ({
  q, channel, dateFrom, dateTo, page = 1, perPage = 20,
  status, escalated, hasMissingFields, updatedAfter, updatedBefore,
}) => {
  const params = new URLSearchParams({ q, page: String(page), per_page: String(perPage) });
  if (channel) params.set("channel", channel);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (Array.isArray(status)) status.forEach((s) => params.append("status", s));
  if (escalated !== undefined && escalated !== null) params.set("escalated", String(escalated));
  if (hasMissingFields !== undefined && hasMissingFields !== null) params.set("has_missing_fields", String(hasMissingFields));
  if (updatedAfter) params.set("updated_after", updatedAfter);
  if (updatedBefore) params.set("updated_before", updatedBefore);
  const { data } = await apiRequest(`/conversations/search?${params.toString()}`, { method: "GET" });
  return data;
};
