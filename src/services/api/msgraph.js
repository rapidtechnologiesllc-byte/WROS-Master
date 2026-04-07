// Microsoft Graph API wrappers used by scheduling/email/SharePoint features.
import { getApiBaseUrl, maybeRedirectOnUnauthorized } from "./client";

export const getMicrosoftSigninUrl = () => `${getApiBaseUrl()}/msgraph/auth/signin`;

const getAuthHeaders = () => {
  const token = localStorage.getItem("hrms_token");
  return token ? { Authorization: `Bearer ${token}` } : undefined;
};

export const getGraphMe = async () => {
  // Checks if a Microsoft account is connected.
  const response = await fetch(`${getApiBaseUrl()}/msgraph/me`, {
    method: "GET",
    credentials: "include",
    headers: getAuthHeaders()
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    // 401 here usually means "Microsoft account not linked yet", not expired HR JWT.
    // Do not run session logout redirect — that made Connect Microsoft appear broken.
    if (response.status === 401) {
      const message = data?.detail || data?.message || "Microsoft sign-in required.";
      throw new Error(
        typeof message === "string" ? message : "Microsoft sign-in required."
      );
    }
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Microsoft sign-in required.";
    throw new Error(message);
  }

  return data;
};

export const scheduleUserMeeting = async ({
  subject,
  startIso,
  endIso,
  attendees = [],
  timezone = "UTC",
  teamsOnline = true
}) => {
  // Schedules a meeting using the signed-in Microsoft account.
  if (!subject) {
    throw new Error("Meeting subject is required.");
  }
  if (!startIso || !endIso) {
    throw new Error("Start and end time are required.");
  }

  const params = new URLSearchParams();
  params.set("subject", subject);
  params.set("start_iso", startIso);
  params.set("end_iso", endIso);
  params.set("timezone", timezone);
  params.set("teams_online", teamsOnline ? "true" : "false");
  attendees.forEach((email) => {
    params.append("attendees", email);
  });

  const response = await fetch(
    `${getApiBaseUrl()}/msgraph/calendar/schedule?${params.toString()}`,
    {
      method: "POST",
      credentials: "include",
      headers: getAuthHeaders()
    }
  );

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message =
      data?.detail || data?.message || "Failed to schedule Microsoft meeting.";
    throw new Error(message);
  }

  return data;
};

export const scheduleTeamsMeeting = async ({
  organizerEmail,
  subject,
  startIso,
  endIso,
  attendees = [],
  timezone = "UTC",
  teamsOnline = true,
  location
}) => {
  // Schedules a meeting using the service account on behalf of organizerEmail.
  if (!organizerEmail) {
    throw new Error("Organizer email is required.");
  }
  if (!subject) {
    throw new Error("Meeting subject is required.");
  }
  if (!startIso || !endIso) {
    throw new Error("Start and end time are required.");
  }

  const params = new URLSearchParams();
  params.set("organizer_email", organizerEmail);
  params.set("subject", subject);
  params.set("start_iso", startIso);
  params.set("end_iso", endIso);
  params.set("timezone", timezone);
  params.set("teams_online", teamsOnline ? "true" : "false");
  if (location) {
    params.set("location", location);
  }
  attendees.forEach((email) => {
    params.append("attendees", email);
  });

  const response = await fetch(
    `${getApiBaseUrl()}/msgraph/service/calendar/schedule?${params.toString()}`,
    {
      method: "POST",
      headers: getAuthHeaders()
    }
  );

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Failed to schedule Teams meeting.";
    throw new Error(message);
  }

  return data;
};

export const getMyMeetings = async ({ top = 10, skip = 0 } = {}) => {
  // Lists meetings for the signed-in Microsoft account.
  const response = await fetch(
    `${getApiBaseUrl()}/msgraph/calendar/meetings?top=${top}&skip=${skip}`,
    { method: "GET", credentials: "include", headers: getAuthHeaders() }
  );

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Failed to fetch meetings.";
    throw new Error(message);
  }

  return data;
};

export const getServiceCalendarEvents = async ({
  userEmail,
  startTime,
  endTime
}) => {
  // Reads a user's calendar using the service account.
  if (!userEmail) {
    throw new Error("User email is required.");
  }
  const params = new URLSearchParams();
  if (startTime) params.set("start_time", startTime);
  if (endTime) params.set("end_time", endTime);
  const response = await fetch(
    `${getApiBaseUrl()}/msgraph/service/calendar/events/${encodeURIComponent(
      userEmail
    )}?${params.toString()}`,
    { method: "GET", headers: getAuthHeaders() }
  );

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message =
      data?.detail || data?.message || "Failed to fetch service calendar.";
    throw new Error(message);
  }

  return data;
};

export const sendGraphMail = async ({ to, subject, bodyText }) => {
  // Sends an email via Microsoft Graph (requires connected account).
  if (!to) {
    throw new Error("Recipient email is required.");
  }
  if (!subject) {
    throw new Error("Email subject is required.");
  }
  if (!bodyText) {
    throw new Error("Email body is required.");
  }

  const params = new URLSearchParams();
  params.set("to", to);
  params.set("subject", subject);
  params.set("body_text", bodyText);

  const response = await fetch(
    `${getApiBaseUrl()}/msgraph/mail/send?${params.toString()}`,
    {
      method: "POST",
      credentials: "include",
      headers: getAuthHeaders()
    }
  );

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Failed to send mail.";
    throw new Error(message);
  }

  return data;
};

export const testSharepointConnection = async () => {
  // Verifies SharePoint service account configuration.
  const response = await fetch(`${getApiBaseUrl()}/msgraph/sharepoint/test-connection`, {
    method: "GET",
    headers: getAuthHeaders()
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Failed to test SharePoint connection.";
    throw new Error(message);
  }

  return data;
};

export const listSharepointDrives = async () => {
  // Lists SharePoint drives to help choose a drive ID.
  const response = await fetch(`${getApiBaseUrl()}/msgraph/sharepoint/list-drives`, {
    method: "GET",
    headers: getAuthHeaders()
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Failed to list SharePoint drives.";
    throw new Error(message);
  }

  return data;
};
