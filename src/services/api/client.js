// Shared API client helpers (base URL + auth headers).
const API_BASE_URL =
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
  const { headers, ...rest } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: withAuthHeaders({
      "Content-Type": "application/json",
      ...(headers || {})
    }),
    ...rest
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    const message = data?.detail || data?.message || "Request failed.";
    throw new Error(message);
  }

  return { data, response };
};
