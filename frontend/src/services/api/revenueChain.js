// Revenue chain: candidate -> job -> project -> timesheet -> invoice -> cash -> P&L.
// Same calculation backs the org, partner, BU and client figures, so they always add up.
import { apiRequest } from "./client";

const period = (start, end) => `start=${start}&end=${end}`;

export const getPnl = async (start, end) => {
  const { data } = await apiRequest(`/revenue-chain/pnl?${period(start, end)}`, { method: "GET" });
  return data;
};

export const getChainLines = async (start, end, { partnerUserId, clientId } = {}) => {
  const params = new URLSearchParams({ start, end });
  if (partnerUserId) params.set("partner_user_id", partnerUserId);
  if (clientId) params.set("client_id", clientId);
  const { data } = await apiRequest(`/revenue-chain/lines?${params.toString()}`, { method: "GET" });
  return data;
};
