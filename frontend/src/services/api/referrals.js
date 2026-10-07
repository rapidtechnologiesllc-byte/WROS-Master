// Employee referral API wrappers
import { apiRequest } from "./client";

export const getMyReferrals = async () => {
  const { data } = await apiRequest("/api/v1/referrals/referrals/all", {
    method: "GET",
  });
  return data;
};








