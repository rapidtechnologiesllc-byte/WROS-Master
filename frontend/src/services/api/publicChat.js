// Public (unauthenticated) Thunder chat widget API wrappers.
// No login exists for these calls -- skipAuth avoids the 401 ->
// "session expired, redirect to /" handling in apiRequest, which is
// for OUR authenticated session, not a visitor who was never logged in.
import { apiRequest } from "./client";

export const startPublicChat = async ({ fullName, email, phone, jobId, consent }) => {
  const { data } = await apiRequest("/public/thunder-chat/start", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({
      full_name: fullName,
      email,
      phone: phone || null,
      job_id: jobId || null,
      consent,
    }),
  });
  return data;
};

export const sendPublicChatMessage = async ({ candidateId, message }) => {
  const { data } = await apiRequest("/public/thunder-chat/message", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({ candidate_id: candidateId, message }),
  });
  return data;
};

export const getPublicChatHistory = async (candidateId) => {
  const { data } = await apiRequest(
    `/public/thunder-chat/history?candidate_id=${encodeURIComponent(candidateId)}`,
    { method: "GET", skipAuth: true },
  );
  return data;
};
