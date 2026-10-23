// Employee referral API wrappers
import { apiRequest } from "./client";

export const getMyReferrals = async () => {
  const { data } = await apiRequest("/api/v1/referrals/referrals/all", {
    method: "GET",
  });
  return data;
};

// Employees who can be named as the referrer on Add Candidate (+ the caller's own employee id)
export const getReferrers = async () => {
  const { data } = await apiRequest("/api/v1/referrals/referrers", {
    method: "GET",
  });
  return data;
};
