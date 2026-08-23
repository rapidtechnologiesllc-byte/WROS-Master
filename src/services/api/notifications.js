// S-105/HRMS-P210 -- Portal Notification Center.
import { apiRequest } from "./client";

export const getNotifications = async () => {
  const { data } = await apiRequest("/notifications", { method: "GET" });
  return data;
};

export const markNotificationRead = async (notificationId) => {
  const { data } = await apiRequest(`/notifications/${notificationId}/mark-read`, { method: "POST" });
  return data;
};
