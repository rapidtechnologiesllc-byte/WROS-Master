/**
 * CSRF Token Management Module
 * Handles fetching, storing, and retrieving CSRF tokens for state-changing requests.
 */

const CSRF_TOKEN_KEY = "csrf_token";
const CSRF_TOKEN_EXPIRY_KEY = "csrf_token_expiry";
const CSRF_TOKEN_EXPIRY_MS = 3600000; // 1 hour

/**
 * Fetch a fresh CSRF token from the backend.
 * Stores in localStorage and returns the token.
 */
export const fetchCSRFToken = async () => {
  let response;
  try {
    response = await fetch("/api/v1/csrf/token", {
      method: "GET",
      credentials: "omit",
    });
  } catch (err) {
    console.error("[CSRF] Fetch failed:", err);
    throw err;
  }

  try {
    if (!response.ok) {
      console.warn("[CSRF] Failed to fetch token, status:", response.status);
      return null;
    }

    let data;
    try {
      data = await response.json();
    } catch (err) {
      console.error("[CSRF] Failed to parse JSON:", err);
      throw err;
    }
    const token = data?.csrf_token || data?.token;

    if (!token) {
      console.warn("[CSRF] No token in response:", data);
      return null;
    }

    // Store token with expiry
    const expiryTime = Date.now() + CSRF_TOKEN_EXPIRY_MS;
    try {
      localStorage.setItem(CSRF_TOKEN_KEY, token);
      localStorage.setItem(CSRF_TOKEN_EXPIRY_KEY, expiryTime.toString());
    } catch (err) {
      // Non-critical storage failure - continue with token in memory
      // Token will be fetched again next request if memory is cleared
      console.error("[CSRF] Failed to persist token to storage:", err);
      throw new Error(`CSRF token storage failed: ${err.message}`);
    }

    console.debug("[CSRF] Token fetched and stored");
    return token;
  } catch (error) {
    console.error("[CSRF] Error fetching token:", error.message);
    // Re-throw so callers can decide whether to handle gracefully
    throw new Error(`Failed to fetch CSRF token: ${error.message}`);
  }
};

/**
 * Get the stored CSRF token, refreshing if expired.
 * Returns null if token cannot be obtained (non-throwing).
 */
export const getCSRFToken = async () => {
  try {
    const token = localStorage.getItem(CSRF_TOKEN_KEY);
    const expiry = localStorage.getItem(CSRF_TOKEN_EXPIRY_KEY);

    // Check if token exists and hasn't expired
    if (token && expiry && Date.now() < parseInt(expiry, 10)) {
      return token;
    }

    // Token missing or expired, fetch fresh one
    console.debug("[CSRF] Token missing or expired, fetching fresh token");
    let freshToken;
    try {
      freshToken = await fetchCSRFToken();
    } catch (err) {
      console.error("[CSRF] Failed to fetch fresh token:", err);
      throw err;
    }
    return freshToken;
  } catch (error) {
    console.error("[CSRF] Error getting token:", error.message);
    // Re-throw so callers can decide whether to handle gracefully
    throw new Error(`Failed to get CSRF token: ${error.message}`);
  }
};

/**
 * Clear the stored CSRF token (e.g., on logout).
 */
export const clearCSRFToken = () => {
  try {
    localStorage.removeItem(CSRF_TOKEN_KEY);
    localStorage.removeItem(CSRF_TOKEN_EXPIRY_KEY);
    console.debug("[CSRF] Token cleared");
  } catch (err) {
    console.error("[CSRF] Error clearing token:", err);
  }
};

/**
 * Initialize CSRF token on app startup.
 * Ensures a token is ready for use. Non-blocking - doesn't throw on failure.
 */
export const initializeCSRFToken = async () => {
  let token;
  try {
    try {
      token = await getCSRFToken();
    } catch (err) {
      console.error("[CSRF] Failed to get token during init:", err);
      throw err;
    }
    if (!token) {
      console.warn("[CSRF] Could not initialize CSRF token");
    }
  } catch (error) {
    // Non-blocking: CSRF is important but app can continue without it
    // Token will be fetched on first state-changing request if needed
    console.warn("[CSRF] Startup initialization failed (will retry on demand):", error.message);
  }
};
