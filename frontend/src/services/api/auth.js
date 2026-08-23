// Auth API wrappers for HR/admin and candidate login flows.
import { apiRequest, getApiBaseUrl } from "./client";

export const validateEmail = async (email) => {
  const { data } = await apiRequest("/auth/validate-email", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({ email })
  });
  return data;
};

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

// 2026-08-07 -- Staff MFA (Phase 1 B3), wiring the real backend that
// already existed (POST /auth/login already returns mfa_required/
// mfa_setup_required/email_otp_required + a real mfa_pending token when
// applicable -- this was orphan code, this session's audit found it,
// nothing here is new backend). Same skipAuth + explicit Authorization
// header pattern as the candidate email-OTP functions above -- the
// mfa_pending token is not a real session, and a wrong code (a real
// 401) must not trip apiRequest's global "expired session" handling.
export const setupMfa = async (pendingToken) => {
  const { data } = await apiRequest("/auth/mfa/setup", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${pendingToken}` },
  });
  return data;
};

export const confirmMfaSetup = async (pendingToken, code) => {
  const { data } = await apiRequest("/auth/mfa/setup/confirm", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${pendingToken}` },
    body: JSON.stringify({ code }),
  });
  return data;
};

export const verifyMfa = async (pendingToken, { code, backupCode } = {}) => {
  const { data } = await apiRequest("/auth/mfa/verify", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${pendingToken}` },
    body: JSON.stringify({ code: code || undefined, backup_code: backupCode || undefined }),
  });
  return data;
};

export const resendStaffEmailOtp = async (pendingToken) => {
  const { data } = await apiRequest("/auth/mfa/email/resend", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${pendingToken}` },
  });
  return data;
};

export const verifyStaffEmailOtp = async (pendingToken, code) => {
  const { data } = await apiRequest("/auth/mfa/email/verify", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${pendingToken}` },
    body: JSON.stringify({ code }),
  });
  return data;
};
