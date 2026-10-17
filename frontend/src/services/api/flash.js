// Flash -- internal assistant API (authenticated). See app/api/v1/endpoints/flash.py.
// Since 2026-10-15 the conversation lives on the server (one per user): the bubble loads it
// on any screen, polls it while closed, and opens a discussion on a record from a deep link
// (?flash=kind:ref), e.g. a Core certification decision.
import { apiRequest } from "./client";

// Window event FlashWidget fires when a discussion ends ({detail: {kind}}), so the screen that
// opened it can refresh
export const FLASH_WORKFLOW_DONE_EVENT = "flash:workflow-done";

// The conversation: messages (only those after `afterId` when given), the open discussion,
// decisions waiting for the user, the unread count and how often to poll while closed.
export const getFlashConversation = async (afterId) => {
  const query = afterId != null ? `?after_id=${encodeURIComponent(afterId)}` : "";
  const { data } = await apiRequest(`/flash/conversation${query}`, { method: "GET" });
  return data;
};

// One turn: returns {reply, messages: [the question, the reply], active_workflow, brain_status}
export const askFlash = async (message) => {
  const { data } = await apiRequest("/flash/", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return data;
};

// Open a discussion on a record (deep-link target); returns Flash's first prompt
export const openFlashWorkflow = async (kind, ref) => {
  const { data } = await apiRequest("/flash/workflows/open", {
    method: "POST",
    body: JSON.stringify({ kind, ref }),
  });
  return data;
};

export const markFlashRead = async (upToId) => {
  const { data } = await apiRequest("/flash/conversation/read", {
    method: "POST",
    body: JSON.stringify({ up_to_id: upToId }),
  });
  return data;
};

export const resetFlashConversation = async () => {
  const { data } = await apiRequest("/flash/conversation/reset", { method: "POST" });
  return data;
};
