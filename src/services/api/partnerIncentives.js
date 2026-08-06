// Partner incentive rules + events + EPIC-16 revenue-share calculator.
import { apiRequest } from "./client";

export const createIncentiveRule = async (payload) => {
  const { data } = await apiRequest("/partner-incentives/rules", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getPartnerIncentiveEvents = async (partnerUserId) => {
  const { data } = await apiRequest(`/partner-incentives/partners/${partnerUserId}/events`, { method: "GET" });
  return data;
};

export const calculateRevenueShare = async (partnerUserId, year, month) => {
  const { data } = await apiRequest(
    `/partner-incentives/partners/${partnerUserId}/calculate-revenue-share?year=${year}&month=${month}`,
    { method: "POST" },
  );
  return data;
};
