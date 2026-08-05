// Auth API wrappers for HR/admin and candidate login flows.
import { apiRequest, getApiBaseUrl } from "./client";

export const login = async (payload) => {
  const { data } = await apiRequest("/auth/login", {
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

// Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate half).
// verify/resend use the short-lived candidate_otp_pending token, not
// the normal session token -- skipAuth + an explicit Authorization
// header so a wrong code (a real 401) doesn't trip apiRequest's global
// "expired session, redirect to login" handling.
export const verifyCandidateEmailOtp = async (pendingToken, code) => {
  const { data } = await apiRequest("/auth/mfa/candidate/email/verify", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${pendingToken}` },
    body: JSON.stringify({ code }),
  });
  return data;
};

export const resendCandidateEmailOtp = async (pendingToken) => {
  const { data } = await apiRequest("/auth/mfa/candidate/email/resend", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${pendingToken}` },
  });
  return data;
};

// Called AFTER a full candidate login (real session token already in
// place) -- a normal authenticated call, no special headers needed.
export const setCandidateEmail2faOptIn = async (optedIn) => {
  const { data } = await apiRequest("/auth/mfa/candidate/opt-in", {
    method: "POST",
    body: JSON.stringify({ opted_in: optedIn }),
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
