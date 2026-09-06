import { Route } from "react-router-dom";
import MessageQueueDashboard from "../screens/MessageQueueDashboard";

export const adminRoutes = [
  <Route key="admin-messagequeue" path="admin/messagequeue" element={<MessageQueueDashboard />} />
];
