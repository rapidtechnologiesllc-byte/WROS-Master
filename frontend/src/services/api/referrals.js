// Employee referral API wrappers
import { apiRequest } from "./client";

export const getMyReferrals = async () => {
  const { data } = await apiRequest("/api/v1/referrals/referrals/all", {
    method: "GET",
  });
  return data;
};

export const createReferral = async (payload) => {
  const { data } = await apiRequest("/api/v1/referrals/record-referral", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const approveReferral = async (referralId, newStatus) => {
  const { data } = await apiRequest(
    `/api/v1/referrals/update-referral-status/${referralId}?new_status=${newStatus}`,
    {
      method: "PUT",
    }
  );
  return data;
};

export const getPendingBonuses = async () => {
  const { data } = await apiRequest("/api/v1/referrals/pending-bonuses", {
    method: "GET",
  });
  return data;
};

export const getReferralDashboard = async () => {
  const { data } = await apiRequest("/api/v1/referrals/dashboard/referrals", {
    method: "GET",
  });
  return data;
};
