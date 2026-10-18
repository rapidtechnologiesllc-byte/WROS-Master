// Partner Home: GET /dashboards/partner (FY targets, operations) and
// GET /dashboards/partner/performance (KPIs, trend, actions). Both are scoped server-side to
// the business units the partner leads; org-level users pass partnerUserId.
import { apiRequest } from "./client";

const query = (params) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") qs.set(key, value);
  });
  return qs.toString() ? `?${qs}` : "";
};

export const getPartnerDashboard = async ({ partnerUserId, businessUnitId } = {}) => {
  const { data } = await apiRequest(
    `/dashboards/partner${query({ partner_user_id: partnerUserId, business_unit_id: businessUnitId })}`,
    { method: "GET" },
  );
  return data;
};

export const getPartnerPerformance = async ({ partnerUserId, businessUnitId, yearMonth, monthsBack = 6 } = {}) => {
  const { data } = await apiRequest(
    `/dashboards/partner/performance${query({
      partner_user_id: partnerUserId,
      business_unit_id: businessUnitId,
      year_month: yearMonth,
      months_back: monthsBack,
    })}`,
    { method: "GET" },
  );
  return data;
};
