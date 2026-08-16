// Flash -- internal query API wrapper (authenticated). Renamed
// 2026-08-06 from "Ask Thunder"/askThunder.js -- functionally
// unchanged at rename time. See app/api/v1/endpoints/flash.py for the
// Thunder-vs-Flash product split rationale (Thunder = external
// candidate-facing agent, Flash = internal staff/employee agent).
import { apiRequest } from "./client";

// Backlog item, 2026-08-05 (wros_ask_thunder_bugs_and_memory_backlog):
// `history` is the last few {question, reply} turns from the SAME
// open chat panel -- FlashWidget.js already holds these in its
// own React state, this just sends them back so the backend can
// resolve a follow-up's pronoun/reference. Not a server-side
// conversation store.
export const askFlash = async (message, history = [], conversationState = null) => {
  const payload = { message, history };
  if (conversationState) {
    payload.conversation_state = conversationState;
  }
  const { data } = await apiRequest("/flash/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};
