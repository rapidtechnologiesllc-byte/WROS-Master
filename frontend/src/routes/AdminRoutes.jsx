import { Route } from "react-router-dom";
import MessageQueueMonitor from "../screens/MessageQueueMonitor";

export const adminRoutes = [
  <Route key="admin-messagequeue" path="admin/messagequeue" element={<MessageQueueMonitor />} />
];
