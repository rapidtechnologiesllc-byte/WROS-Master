import { Route } from "react-router-dom";
import MessageQueueMonitorEnhanced from "../screens/MessageQueueMonitorEnhanced";
import SLMTrainingData from "../screens/SLMTrainingData";

export const adminRoutes = [
  <Route key="admin-messagequeue" path="admin/messagequeue" element={<MessageQueueMonitorEnhanced />} />,
  <Route key="admin-slm-training" path="admin/slm-training" element={<SLMTrainingData />} />
];
