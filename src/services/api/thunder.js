// "Test Thunder" chat -- POST /thunder/test-chat, GET history, POST reset.
import { apiRequest } from "./client";

export const sendTestChatMessage = async (message) => {
  const { data } = await apiRequest("/thunder/test-chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return data;
};

export const getTestChatHistory = async () => {
  const { data } = await apiRequest("/thunder/test-chat/history", {
    method: "GET",
  });
  return data;
};

export const resetTestChat = async () => {
  const { data } = await apiRequest("/thunder/test-chat/reset", {
    method: "POST",
  });
  return data;
};
