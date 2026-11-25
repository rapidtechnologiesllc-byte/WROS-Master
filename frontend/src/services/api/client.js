// Shared API client helpers (base URL + auth headers).
//
// Use relative URLs so dev server proxy (setupProxy.js) can forward to backend.
// In production, REACT_APP_API_URL can be set to the actual backend URL.
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8080";

// The server stores and sends every timestamp in UTC, mostly without a zone marker
// ("2026-11-24T20:48:04"). JavaScript reads an unmarked date-time as the viewer's LOCAL time, so
// times showed hours off (an overdue task looked due later). Mark them as UTC while reading the
// response, once, for every screen. Date-only values and already-marked times are left as sent.
const UNMARKED_SERVER_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?$/;
export const markServerTimestampsUtc = (_key, value) =>
  typeof value === "string" && UNMARKED_SERVER_TIMESTAMP.test(value) ? `${value}Z` : value;

const readServerJson = async (response) => {
  const text = await response.text();
  return text ? JSON.parse(text, markServerTimestampsUtc) : null;
};

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
    // gate refusals: {message, blockers: [...]} -> "message: blocker; blocker"
    if (typeof detail === "object" && Array.isArray(detail.blockers)) {
      const reasons = detail.blockers.filter(Boolean).join("; ");
      return [detail.message, reasons].filter(Boolean).join(": ");
    }
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
    localStorage.removeItem("hrms_authority");
    localStorage.removeItem("hrms_user_name");
    localStorage.removeItem("hrms_user_email");
    localStorage.removeItem("hrms_candidate_id");
    localStorage.removeItem("hrms_user_type");
    localStorage.removeItem("hrms_active_bu_id");
    localStorage.removeItem("hrms_bu_view");
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
  // The business unit chosen in the top-bar selector (BUSwitcher). The backend only uses it to
  // NARROW what the user's role already lets them see (app.core.bu_view); unset = their full scope.
  const activeBuId = localStorage.getItem("hrms_bu_view");
  if (activeBuId) {
    result["X-BU-View"] = activeBuId;
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
    return data.access_token;
  } catch (error) {
    console.error("[API] Token refresh error:", error);
    clearAuthSessionAndRedirectToLogin();
    throw error;
  }
};

// The web server in front of HRMS refuses a request body over about 1 MB. A form larger than that goes up in
// pieces to /uploads/parts, then the original request is sent with an empty body and the server rebuilds it
// (backend app/middleware/large_upload.py). Every upload in the app goes through here, so no screen has its own
// limit. Needs a signed-in token (a user's or a candidate portal link's) in the Authorization header.
const LARGEST_REQUEST_BYTES = 900 * 1024;
const PIECE_BYTES = 768 * 1024;

const newUploadId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)))
  .map((b) => b.toString(16).padStart(2, "0")).join("");

const authorizationOf = (headers) => {
  if (!headers) return null;
  if (typeof headers.get === "function") return headers.get("Authorization");
  return headers.Authorization || headers.authorization || null;
};

export const sendForm = async (url, init = {}) => {
  const { body } = init;
  if (!(body instanceof FormData)) return fetch(url, init);
  let estimate = 0;
  body.forEach((value) => { estimate += typeof value === "string" ? value.length : value.size; });
  const authorization = authorizationOf(init.headers);
  if (estimate <= LARGEST_REQUEST_BYTES || !authorization) return fetch(url, init);
  const encoded = new Request(url, { method: "POST", body });
  const contentType = encoded.headers.get("content-type");
  const whole = await encoded.blob();
  const origin = new URL(url, window.location.href);
  const partsUrl = `${origin.origin}${origin.pathname.replace(/\/api\/v1\/.*$/, "")}/api/v1/uploads/parts`;
  const total = Math.ceil(whole.size / PIECE_BYTES);
  const uploadId = newUploadId();
  for (let index = 0; index < total; index += 1) {
    const piece = await fetch(`${partsUrl}?upload_id=${uploadId}&index=${index}&total=${total}`, {
      method: "POST",
      credentials: "omit",
      headers: { Authorization: authorization, "Content-Type": "application/octet-stream" },
      body: whole.slice(index * PIECE_BYTES, (index + 1) * PIECE_BYTES),
    });
    if (!piece.ok) return piece;  // the caller shows the server's reason, as for any failed request
  }
  return fetch(url, {
    ...init,
    body: undefined,
    headers: { ...(init.headers || {}), "X-Upload-Body": `${uploadId}:${total}`, "X-Upload-Content-Type": contentType },
  });
};

// Drop-in for fetch() on backend paths: same Response object (callers keep
// their .ok / .json() handling), but the URL is built from API_BASE_URL
// with the /api/v1 prefix and the auth/BU headers are attached. A bare
// fetch("/api/v1/...") is relative to the page and misses the backend in
// production (nginx serves the API under /api).
export const apiFetch = (path, init = {}) => {
  const normalizedPath = path.startsWith("/api") ? path : `/api/v1${path}`;
  return sendForm(`${API_BASE_URL}${normalizedPath}`, {
    credentials: "omit",
    ...init,
    headers: withAuthHeaders(init.headers || {}),
  });
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
  let response;
  try {
    response = await sendForm(url, {
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
    throw new Error(`Network error: ${error.message}. Is the backend running on ${API_BASE_URL}?`);
  }

  let data = null;
  try {
    data = await readServerJson(response);
  } catch (err) {
    data = null;
  }
  if (!response.ok) {
    // Backend often returns 404 when optional candidate form rows do not exist yet.
    if (allow404 && response.status === 404) {
      return { data: null, response };
    }
    if (
      Array.isArray(allowStatuses) &&
      allowStatuses.includes(response.status)
    ) {
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
          const retryHeaders = withAuthHeaders(baseHeaders);
          retryHeaders.Authorization = `Bearer ${newAccessToken}`;

          const retryResponse = await sendForm(url, {
            headers: retryHeaders,
            credentials: 'omit',
            body,
            ...rest,
          });

          let retryData = null;
          try {
            retryData = await readServerJson(retryResponse);
          } catch (err) {
            retryData = null;
          }

          if (retryResponse.ok) {return { data: retryData, response: retryResponse };
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
  return { data, response };
};
