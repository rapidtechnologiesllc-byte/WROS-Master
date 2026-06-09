// Shared API client helpers (base URL + auth headers).
const API_BASE_URL =
  //process.env.REACT_APP_API_BASE_URL || "http://46.224.149.7:8080";
  process.env.REACT_APP_API_BASE_URL || "https://hrms-backend.blitzenx.com";
  //process.env.REACT_APP_API_BASE_URL || "http://localhost:8080";


export const getApiBaseUrl = () => API_BASE_URL;

// FastAPI/Pydantic often returns { detail: [...] } or { detail: "msg" } on 4xx/5xx.
export const formatApiErrorMessage = (payload) => {
  if (!payload || typeof payload !== "object") {
    return "Request failed.";
  }
  const rawDetail = payload.detail;
  const rawMessage = payload.message;

  const formatDetail = (detail) => {
    if (detail == null) return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object") {
            const msg = item.msg || item.message || "";
            const loc = Array.isArray(item.loc)
              ? item.loc.filter((x) => x !== "body").join(" → ")
              : "";
            if (msg && loc) return `${loc}: ${msg}`;
            return msg || JSON.stringify(item);
          }
          return String(item);
        })
        .filter(Boolean)
        .join("; ");
    }
    if (typeof detail === "object" && detail.msg) return String(detail.msg);
    if (typeof detail === "object") {
      try {
        return JSON.stringify(detail);
      } catch {
        return "Request failed.";
      }
    }
    return String(detail);
  };

  const fromDetail = formatDetail(rawDetail);
  if (fromDetail) return fromDetail;
  if (typeof rawMessage === "string" && rawMessage.trim()) return rawMessage;
  return "Request failed.";
};

/** Clears stored auth and sends the user to the login screen (same keys as App `handleLogout`). */
export const clearAuthSessionAndRedirectToLogin = () => {
  try {
    localStorage.removeItem("hrms_token");
    localStorage.removeItem("hrms_role");
    localStorage.removeItem("hrms_user_name");
    localStorage.removeItem("hrms_user_email");
    localStorage.removeItem("hrms_candidate_id");
    localStorage.removeItem("hrms_user_type");
  } catch (_) {
    /* ignore */
  }
  window.location.replace("/");
};

/** Raw `fetch` helpers: if we had a token and got 401, redirect to login. Returns true when redirect ran. */
export const maybeRedirectOnUnauthorized = (response) => {
  if (response.status !== 401) return false;
  if (!localStorage.getItem("hrms_token")) return false;
  clearAuthSessionAndRedirectToLogin();
  return true;
};

const withAuthHeaders = (headers = {}) => {
  const token = localStorage.getItem("hrms_token");
  if (!token) {
    return headers;
  }
  return { ...headers, Authorization: `Bearer ${token}` };
};

export const apiRequest = async (path, options = {}) => {
  const {
    headers,
    skipAuth = false,
    allow404 = false,
    allowStatuses = [],
    body,
    ...rest
  } = options;
  const isFormData = body instanceof FormData;
  const baseHeaders = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(headers || {}),
  };
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: skipAuth ? baseHeaders : withAuthHeaders(baseHeaders),
    body,
    ...rest,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    // Backend often returns 404 when optional candidate form rows do not exist yet.
    if (allow404 && response.status === 404) {
      return { data: null, response };
    }
    if (Array.isArray(allowStatuses) && allowStatuses.includes(response.status)) {
      return { data: null, response };
    }
    // Expired or invalid JWT: redirect to login instead of surfacing "Invalid token" in the UI.
    if (response.status === 401 && !skipAuth) {
      clearAuthSessionAndRedirectToLogin();
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = formatApiErrorMessage(data);
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return { data, response };
};
