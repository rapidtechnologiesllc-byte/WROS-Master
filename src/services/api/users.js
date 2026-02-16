// HR user directory API wrappers.
import { apiRequest } from "./client";

export const getAllUsers = async () => {
  const { data } = await apiRequest("/hr/users/all", {
    method: "GET"
  });
  return data;
};
