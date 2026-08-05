// Internal "Ask Thunder" query API wrapper (authenticated).
import { apiRequest } from "./client";

// Backlog item, 2026-08-05 (wros_ask_thunder_bugs_and_memory_backlog):
// `history` is the last few {question, reply} turns from the SAME
// open chat panel -- AskThunderWidget.js already holds these in its
// own React state, this just sends them back so the backend can
// resolve a follow-up's pronoun/reference. Not a server-side
// conversation store.
export const askThunder = async (message, history = []) => {
  const { data } = await apiRequest("/ask-thunder/", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
  return data;
};
