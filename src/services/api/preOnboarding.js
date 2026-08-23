import { apiRequest } from "./client";

export const managerReviewList = async () => {
  const { data } = await apiRequest(`/preonboarding/hiring-manager/review`, {
    method: "GET",
  });
  return data;
};

export const managerReviewApprove = async (record,review) => {
  const { data } = await apiRequest(record?.approval_endpoint, {
    method: "POST",
    body: JSON.stringify({
      action: review,
      comments: "Good",
    }),
  });
  return data;
};


