import { apiRequest } from "./client";

/**
 * Send a plain text or HTML email using the HRMS mailbox service.
 */
export const sendPlainEmail = async ({
  toEmail,
  subject,
  bodyContent,
  isHtml = false,
  ccEmails = [],
}) => {
  const normalizedCcEmails = Array.isArray(ccEmails)
    ? ccEmails.map((email) => String(email).trim()).filter(Boolean)
    : [];

  const { data } = await apiRequest("/email/send", {
    method: "POST",
    body: JSON.stringify({
      to_email: toEmail,
      subject,
      body_content: bodyContent,
      is_html: isHtml,
      cc_emails: normalizedCcEmails,
    }),
  });

  return data;
};

/**
 * Send an interview invite for an already created interview.
 * Backend uses interview details from DB and can generate Teams event details.
 */
export const sendInterviewInvite = async ({
  interviewId,
  extraNotes,
  timezone = "Asia/Kolkata",
  createTeamsEvent = true,
}) => {
  const query = new URLSearchParams();

  if (extraNotes && String(extraNotes).trim()) {
    query.append("extra_notes", String(extraNotes).trim());
  }

  if (timezone) {
    query.append("timezone", timezone);
  }

  query.append("create_teams_event", String(createTeamsEvent));

  const { data } = await apiRequest(
    `/email/interview/invite/${interviewId}?${query.toString()}`,
    {
      method: "POST",
    },
  );

  return data;
};

export const sendMailAttachments = async ({
  toEmail,
  subject,
  bodyContent,
  files = [],
}) => {
  const { data } = await apiRequest("/email/send-with-attachments", {
    method: "POST",
    body: JSON.stringify({
      to_email: toEmail,
      subject,
      body_content: bodyContent,
      files: files,
    }),
  });

  return data;
};
