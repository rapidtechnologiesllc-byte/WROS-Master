// HR user directory API wrappers.
import { apiRequest } from "./client";

// 2026-08-12 real bug fix -- Avinash: "users.map is not a function."
// The backend returns {total_users, users: [...]} (AllUsersResponse), but
// this used to return that wrapped object as-is, leaving every one of its
// ~11 callers to defensively re-unwrap `.users` themselves -- most did,
// two didn't (OpportunityPipelineScreen.js, ProfileTabEditable.js) and
// crashed on `.map()`. Unwrapped once here, so the function's real
// contract is "always returns a plain array" -- no caller should ever
// need to reach into `.users` again.
export const getAllUsers = async () => {
  const { data } = await apiRequest("/hr/users/all", {
    method: "GET",
  });
  return data?.users || [];
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

// Fetch user permission overrides
export const getUserPermissions = async (userId) => {
  try {
    const { data } = await apiRequest(`/rbac/users/${encodeURIComponent(userId)}/permissions`, {
      method: "GET",
    });
    return data?.permissions || {};
  } catch (err) {
    console.error("Failed to fetch permissions from /rbac/users endpoint:", err);
    // Fallback: try legacy endpoint
    try {
      const { data } = await apiRequest(`/hr/users/${encodeURIComponent(userId)}/permissions`, {
        method: "GET",
      });
      return data?.permissions || {};
    } catch (fallbackErr) {
      console.error("Fallback fetch also failed:", fallbackErr);
      return {};
    }
  }
};

// Save user permission overrides
export const updateUserPermissions = async (userId, permissions) => {
  try {
    const { data } = await apiRequest(`/rbac/users/${encodeURIComponent(userId)}/permissions`, {
      method: "PATCH",
      body: JSON.stringify({ permissions }),
    });
    return data;
  } catch (err) {
    console.error("Failed to update permissions via /rbac/users endpoint:", err);
    // Fallback: try legacy endpoint
    try {
      const { data } = await apiRequest(`/hr/users/${encodeURIComponent(userId)}/permissions`, {
        method: "PATCH",
        body: JSON.stringify({ permissions }),
      });
      return data;
    } catch (fallbackErr) {
      console.error("Fallback update also failed:", fallbackErr);
      throw fallbackErr;
    }
  }
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
export const getUserDetails = async (userId) => {
  const { data } = await apiRequest(`/hr/users/details/${userId}`, {
    method: "GET",
  });

  return data;
};

export const createHrAssignment = async (payload) => {
  const { data } = await apiRequest("/hr-assignments/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  return data;
};
export const getHrAssignmentByCandidate = async (candidateId) => {
  const { data } = await apiRequest(
    `/hr-assignments/by-candidate/${candidateId}`,
    {
      method: "GET",
    },
  );
  return data;
};
