// S-017/HRMS-0417 -- Candidate Portal API wrapper.
//
// Deliberately does NOT use services/api/client.js's apiRequest(): that
// helper reads the bearer token from localStorage("hrms_token") and,
// on a 401, redirects the whole app to the internal /auth login page --
// exactly wrong for this route. A candidate portal visitor arrives via
// a magic link with no internal account and must never see the
// internal login screen; an expired/invalid link should render this
// screen's own "This link has expired" message instead. So every call
// here takes the token explicitly (from the URL path, held in
// CandidatePortalScreen's own state) and lets the caller handle 401s.
import { getApiBaseUrl, formatApiErrorMessage } from "./client";

const portalRequest = async (path, token, options = {}) => {
  const { method = "GET", body } = options;
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(formatApiErrorMessage(data));
    error.status = response.status;
    throw error;
  }
  return data;
};

export const getPortalHome = (token) => portalRequest("/portal/home", token);
export const getPortalMessages = (token) => portalRequest("/portal/messages", token);
export const getPortalProfileFields = (token) => portalRequest("/portal/profile-fields", token);
export const updatePortalProfile = (token, fields) =>
  portalRequest("/portal/profile", token, { method: "PATCH", body: { fields } });
export const getPortalInterviews = (token) => portalRequest("/portal/interviews", token);
export const requestPortalReschedule = (token, interviewId, note) =>
  portalRequest(`/portal/interviews/${interviewId}/reschedule-request`, token, { method: "POST", body: { note } });
export const downloadPortalInterviewIcs = async (token, interviewId) => {
  const response = await fetch(`${getApiBaseUrl()}/portal/interviews/${interviewId}/ics`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Failed to download calendar invite.");
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `interview-${interviewId}.ics`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const sendPortalReply = (token, conversationId, messageBody) =>
  portalRequest(`/portal/conversations/${conversationId}/messages`, token, {
    method: "POST",
    body: { message_body: messageBody },
  });

// S-346 real-time fix, 2026-08-06: the backend has supported this
// long-poll endpoint since the widget was first built, but nothing on
// the frontend ever called it -- MessagesTab fetched once on load and
// never again, so a reply arriving on another channel (e.g. WhatsApp)
// while the portal tab was open never appeared without a manual
// reload. No WebSocket infra exists in this codebase (see the backend
// endpoint's own docstring), so this is the documented fallback: poll
// on a short interval for messages newer than after_id.
export const pollPortalMessages = (token, conversationId, afterId) =>
  portalRequest(`/portal/conversations/${conversationId}/messages/poll?after_id=${afterId}`, token);

// S-089 (HRMS-P109): Candidate Portal — Offer Viewer
export const getPortalOffers = (token) => portalRequest("/portal/offers", token);

// S-090 (HRMS-P110): Candidate Portal — Document Upload
export const getPortalDocuments = (token) => portalRequest("/portal/documents", token);

export const uploadPortalDocument = async (token, file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getApiBaseUrl()}/portal/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(data?.message || "Upload failed");
    error.status = response.status;
    throw error;
  }

  return data;
};
