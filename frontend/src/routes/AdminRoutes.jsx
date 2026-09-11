import { Route } from "react-router-dom";
import MessageQueueMonitorEnhanced from "../screens/MessageQueueMonitorEnhanced";
import SLMTrainingData from "../screens/SLMTrainingData";
import SLMDashboard from "../screens/SLMDashboard";

export const adminRoutes = [
  <Route key="admin-messagequeue" path="admin/messagequeue" element={<MessageQueueMonitorEnhanced />} />,
  <Route key="admin-slm-training" path="admin/slm-training" element={<SLMTrainingData />} />,
  <Route key="admin-slm-dashboard" path="admin/slm-dashboard" element={<SLMDashboard />} />
];
