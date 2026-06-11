// HR user directory API wrappers.
import { apiRequest } from "./client";

export const getAllUsers = async () => {
  const { data } = await apiRequest("/hr/users/all", {
    method: "GET",
  });
  return data;
};

export const getAssignedCandidates = async () => {
  const { data } = await apiRequest("/hr/assignments/candidates", {
    method: "GET",
  });
  return data;
};

export const getAssignedInterviews = async () => {
  const { data } = await apiRequest("/hr/interviews/assigned", {
    method: "GET",
  });
  return data;
};

// HR/Admin user management
export const getHrMe = async () => {
  const { data } = await apiRequest("/hr/me", { method: "GET" });
  return data;
};

export const createHrUser = async (payload) => {
  const { data } = await apiRequest("/hr/users/create", {
    method: "POST",
    body: JSON.stringify({
      user_name: payload.user_name,
      user_email: payload.user_email,
      user_password: payload.user_password,
      user_role: payload.user_role,
    }),
  });
  return data;
};

// NOTE: backend `update_user` uses primitive query params (user_name/user_role),
// not a request body model.
export const updateHrUser = async (userId, { user_name, user_role } = {}) => {
  const params = new URLSearchParams();
  if (user_name != null) params.set("user_name", user_name);
  if (user_role != null) params.set("user_role", user_role);
  const qs = params.toString();
  const path = qs
    ? `/hr/users/${encodeURIComponent(userId)}?${qs}`
    : `/hr/users/${encodeURIComponent(userId)}`;

  const { data } = await apiRequest(path, { method: "PUT" });
  return data;
};

export const deleteHrUser = async (userId) => {
  const { data } = await apiRequest(`/hr/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
  return data;
};

export const changeHrMePassword = async ({
  current_password,
  new_password,
}) => {
  const { data } = await apiRequest("/hr/users/me/change-password", {
    method: "PUT",
    body: JSON.stringify({
      current_password,
      new_password,
    }),
  });
  return data;
};
export const searchUsers = async ({
  name,
  permission_role,
  user_role,
  department,
  business_unit,
  skip = 0,
  limit = 50,
} = {}) => {
  const params = new URLSearchParams();
  if (name?.trim()) {
    params.set("name", name.trim());
  }
  if (permission_role?.trim()) {
    params.set("permission_role", permission_role.trim());
  }
  if (user_role?.trim()) {
    params.set("user_role", user_role.trim());
  }
  if (department?.trim()) {
    params.set("department", department.trim());
  }
  if (business_unit?.trim()) {
    params.set("business_unit", business_unit.trim());
  }
  params.set("skip", String(skip));
  params.set("limit", String(limit));
  const { data } = await apiRequest(`/hr/users/search?${params.toString()}`, {
    method: "GET",
  });
  return data;
};
