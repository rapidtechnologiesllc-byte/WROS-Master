// Shared API client helpers (base URL + auth headers).
//
// REACT_APP_API_BASE_URL is set explicitly per environment via
// .env.development (npm start -> localhost) and .env.production
// (npm run build -> the real backend) -- CRA loads the matching file
// automatically based on NODE_ENV, no manual setup needed per machine.
//
// The fallback below is intentionally NOT the production URL. It used
// to be, which meant any environment that didn't set the env var --
// including a bare `npm start` with no .env files present -- silently
// talked to the real production backend and real candidate/employee
// PII. Falling back to localhost instead means a misconfigured
// environment fails loudly and obviously (connection refused) rather
// than quietly reading/writing real data.
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://localhost:8080";

export const getApiBaseUrl = () => API_BASE_URL;

// FastAPI/Pydantic often returns { detail: [...] } or { detail: "msg" } on 4xx/5xx.
export const formatApiErrorMessage = (payload, statusCode) => {
  if (!payload || typeof payload !== "object") {
    // For all non-payload errors, show appropriate message
    if (statusCode === 500) {
      return "An unexpected error occurred. Please contact the help desk if this persists.";
    }
    if (statusCode === 504) {
      return "The backend service is not responding. Please try again or contact the help desk if the problem continues.";
    }
    if (statusCode === 401) {
      return "Your session has expired. Please sign in again.";
    }
    if (statusCode === 403) {
      return "You do not have permission to perform this action. Please contact the help desk if you believe this is an error.";
    }
    if (statusCode === 404) {
      return "The requested resource was not found. Please verify the information and try again.";
    }
    if (statusCode === 400) {
      return "Invalid request. Please check your input and try again.";
    }
    return "An error occurred while processing your request. Please try again or contact the help desk if the problem persists.";
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
      return JSON.stringify(detail);
    }
    return String(detail);
  };

  const fromDetail = formatDetail(rawDetail);
  if (fromDetail) return fromDetail;
  if (typeof rawMessage === "string" && rawMessage.trim()) return rawMessage;

  // Default messages based on status code
  if (statusCode === 500) {
    return "An unexpected error occurred. Please contact the help desk if this persists.";
  }
  if (statusCode === 504) {
    return "The backend service is not responding. Please try again or contact the help desk if the problem continues.";
  }
  if (statusCode === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (statusCode === 403) {
    return "You do not have permission to perform this action. Please contact the help desk if you believe this is an error.";
  }
  if (statusCode === 404) {
    return "The requested resource was not found. Please verify the information and try again.";
  }
  if (statusCode === 400) {
    return "Invalid request. Please check your input and try again.";
  }
  return "An error occurred while processing your request. Please try again or contact the help desk if the problem persists.";
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
  const url = `${API_BASE_URL}${path}`;
  console.log(`[API] ${method} ${path}`);

  let response;
  try {
    response = await fetch(url, {
      headers: skipAuth ? baseHeaders : withAuthHeaders(baseHeaders),
      credentials: 'omit',
      body,
      ...rest,
    });
  } catch (error) {
    console.error(`[API] Network error on ${method} ${path}:`, error.message);
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
    console.error(`[API] ${method} ${path} - Failed to parse JSON response: ${err.message}`);
    throw new Error(`Failed to parse API response: ${err.message}`);
  }

  console.log(`[API] ${method} ${path} - Status: ${response.status}`, data);

  if (!response.ok) {
    // Backend often returns 404 when optional candidate form rows do not exist yet.
    if (allow404 && response.status === 404) {
      console.warn(`[API] 404 allowed for ${path}`);
      return { data: null, response };
    }
    if (
      Array.isArray(allowStatuses) &&
      allowStatuses.includes(response.status)
    ) {
      console.warn(`[API] Status ${response.status} allowed for ${path}`);
      return { data: null, response };
    }
    // Expired or invalid JWT: redirect to login instead of surfacing "Invalid token" in the UI.
    if (response.status === 401 && !skipAuth) {
      console.error(`[API] 401 Unauthorized - redirecting to login`);
      clearAuthSessionAndRedirectToLogin();
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = formatApiErrorMessage(data, response.status);
    console.error(`[API] Error ${response.status} for ${path}: ${message}`, data);
    const error = new Error(message);
    error.status = response.status;
    // Structured 4xx bodies (e.g. { error, review_id, ... }) -- callers that
    // need more than the flattened message string can read this directly
    // instead of re-parsing it back out of `message`.
    error.detail = data && typeof data === "object" ? data.detail : undefined;
    throw error;
  }

  console.log(`[API] ✓ ${method} ${path}`);
  return { data, response };
};
