// Auth API wrappers for HR/admin and candidate login flows.
import { apiRequest, getApiBaseUrl } from "./client";

export const login = async (payload) => {
  const { data } = await apiRequest("/auth/v1/login", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify(payload)
  });
  return data;
};

export const signup = async (payload) => {
  const { data } = await apiRequest("/auth/v1/signup", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify(payload)
  });
  return data;
};

export const candidateLogin = async (payload) => {
  const { data } = await apiRequest("/auth/candidate/login", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify(payload)
  });
  return data;
};

export const getAzureSigninUrl = () => `${getApiBaseUrl()}/msgraph/auth/signin`;

export const fetchAzureProfile = async () => {
  const { data } = await apiRequest("/msgraph/me", {
    method: "GET",
    skipAuth: true
  });
  return data;
};
