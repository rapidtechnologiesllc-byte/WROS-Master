// HR user directory API wrappers.
import { apiRequest } from "./client";

export const getAllUsers = async () => {
  const { data } = await apiRequest("/hr/users/all", {
    method: "GET"
  });
  return data;
};

export const getAssignedCandidates = async () => {
  const { data } = await apiRequest("/hr/assignments/candidates", {
    method: "GET"
  });
  return data;
};

export const getAssignedInterviews = async () => {
  const { data } = await apiRequest("/hr/interviews/assigned", {
    method: "GET"
  });
  return data;
};
