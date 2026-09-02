// Shared API client helpers (base URL + auth headers).
//
// Use relative URLs so dev server proxy (setupProxy.js) can forward to backend.
// In production, REACT_APP_API_BASE_URL can be set to the actual backend URL.
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "";

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
    localStorage.removeItem("hrms_refresh_token");
    localStorage.removeItem("hrms_role");
    localStorage.removeItem("hrms_user_name");
    localStorage.removeItem("hrms_user_email");
    localStorage.removeItem("hrms_candidate_id");
    localStorage.removeItem("hrms_user_type");
    localStorage.removeItem("hrms_active_bu_id");
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
  const result = { ...headers };
  if (token) {
    result.Authorization = `Bearer ${token}`;
  }
  // S-205/HRMS-0107 -- no server-side session store in this app (JWT-
  // only), so the active BU choice is persisted here and re-sent on
  // every request. The backend re-validates it against the user's
  // real bu_access rows every single call (BR-0107-01) -- this header
  // is a hint, never trusted as-is.
  const activeBuId = localStorage.getItem("hrms_active_bu_id");
  if (activeBuId) {
    result["X-Active-BU-Id"] = activeBuId;
  }
  return result;
};

// Track if we're already in a refresh attempt to prevent infinite loops
let isRefreshing = false;
let refreshPromise = null;

const refreshAccessToken = async () => {
  const refreshToken = localStorage.getItem("hrms_refresh_token");
  if (!refreshToken) {
    clearAuthSessionAndRedirectToLogin();
    throw new Error("No refresh token available");
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/v1/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${refreshToken}`,
      },
      credentials: 'omit',
    });

    if (!response.ok) {
      console.error("[API] Token refresh failed, redirecting to login");
      clearAuthSessionAndRedirectToLogin();
      throw new Error("Token refresh failed");
    }

    const data = await response.json();

    // Store new tokens
    localStorage.setItem("hrms_token", data.access_token);
    if (data.refresh_token) {
      localStorage.setItem("hrms_refresh_token", data.refresh_token);
    }

    console.log("[API] ✓ Token refreshed successfully");
    return data.access_token;
  } catch (error) {
    console.error("[API] Token refresh error:", error);
    clearAuthSessionAndRedirectToLogin();
    throw error;
  }
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

  const method = rest.method || "GET";
  // Automatically add /api/v1 prefix if not already present (backend routes registered with this prefix)
  const normalizedPath = path.startsWith("/api") ? path : `/api/v1${path}`;
  const url = `${API_BASE_URL}${normalizedPath}`;
  console.log(`[API] ${method} ${normalizedPath}`);

  let response;
  try {
    response = await fetch(url, {
      headers: skipAuth ? baseHeaders : withAuthHeaders(baseHeaders),
      credentials: 'omit',
      body,
      ...rest,
    });
  } catch (error) {
    console.error(`[API] Network error on ${method} ${normalizedPath}:`, error.message);
    console.error('[API] Debugging info:');
    console.error('  URL:', url);
    console.error('  Method:', method);
    console.error('  Headers:', withAuthHeaders(baseHeaders));
    throw new Error(`Network error: ${error.message}. Is the backend running on ${API_BASE_URL}?`);
  }

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  console.log(`[API] ${method} ${normalizedPath} - Status: ${response.status}`, data);

  if (!response.ok) {
    // Backend often returns 404 when optional candidate form rows do not exist yet.
    if (allow404 && response.status === 404) {
      console.warn(`[API] 404 allowed for ${normalizedPath}`);
      return { data: null, response };
    }
    if (
      Array.isArray(allowStatuses) &&
      allowStatuses.includes(response.status)
    ) {
      console.warn(`[API] Status ${response.status} allowed for ${normalizedPath}`);
      return { data: null, response };
    }

    // Handle 401 with automatic token refresh
    if (response.status === 401 && !skipAuth) {
      const refreshToken = localStorage.getItem("hrms_refresh_token");

      // Only attempt refresh if we have a refresh token and aren't already refreshing
      if (refreshToken && !isRefreshing && normalizedPath !== "/auth/v1/refresh") {
        isRefreshing = true;

        try {
          if (!refreshPromise) {
            refreshPromise = refreshAccessToken();
          }

          const newAccessToken = await refreshPromise;
          isRefreshing = false;
          refreshPromise = null;

          // Retry the original request with new token
          console.log(`[API] Retrying ${method} ${normalizedPath} with refreshed token`);
          const retryHeaders = withAuthHeaders(baseHeaders);
          retryHeaders.Authorization = `Bearer ${newAccessToken}`;

          const retryResponse = await fetch(url, {
            headers: retryHeaders,
            credentials: 'omit',
            body,
            ...rest,
          });

          let retryData = null;
          try {
            retryData = await retryResponse.json();
          } catch (err) {
            retryData = null;
          }

          if (retryResponse.ok) {
            console.log(`[API] ✓ ${method} ${normalizedPath} (after refresh)`);
            return { data: retryData, response: retryResponse };
          } else {
            // Retry still failed
            if (retryResponse.status === 401) {
              clearAuthSessionAndRedirectToLogin();
            }
            throw new Error(formatApiErrorMessage(retryData));
          }
        } catch (refreshError) {
          isRefreshing = false;
          refreshPromise = null;
          clearAuthSessionAndRedirectToLogin();
          throw refreshError;
        }
      } else {
        // No refresh token or already refreshing, redirect to login
        console.error(`[API] 401 Unauthorized - redirecting to login`);
        clearAuthSessionAndRedirectToLogin();
        throw new Error("Your session has expired. Please sign in again.");
      }
    }

    const message = formatApiErrorMessage(data);
    console.error(`[API] Error ${response.status} for ${normalizedPath}: ${message}`, data);
    const error = new Error(message);
    error.status = response.status;
    // Structured 4xx bodies (e.g. { error, review_id, ... }) -- callers that
    // need more than the flattened message string can read this directly
    // instead of re-parsing it back out of `message`.
    error.detail = data && typeof data === "object" ? data.detail : undefined;
    throw error;
  }

  console.log(`[API] ✓ ${method} ${normalizedPath}`);
  return { data, response };
};
