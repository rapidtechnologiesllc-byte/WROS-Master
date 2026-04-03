// Shared API client helpers (base URL + auth headers).
const API_BASE_URL =
  //process.env.REACT_APP_API_BASE_URL || "http://46.224.149.7:8080";
  process.env.REACT_APP_API_BASE_URL || "https://hrms-backend.blitzenx.com";
  //process.env.REACT_APP_API_BASE_URL || "http://localhost:8080";


export const getApiBaseUrl = () => API_BASE_URL;

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
    ...rest
  } = options;
  const baseHeaders = {
    "Content-Type": "application/json",
    ...(headers || {})
  };
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: (skipAuth ? baseHeaders : withAuthHeaders(baseHeaders)),
    ...rest
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
    const message = data?.detail || data?.message || "Request failed.";
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return { data, response };
};
