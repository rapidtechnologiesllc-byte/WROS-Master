import { Route } from "react-router-dom";
import MessageQueueMonitorEnhanced from "../screens/MessageQueueMonitorEnhanced";
import SLMTrainingData from "../screens/SLMTrainingData";
import SLMDashboard from "../screens/SLMDashboard";
import SLMLearningTranscript from "../screens/SLMLearningTranscript";
import WorkforceOverviewScreen from "../screens/WorkforceOverviewScreen";
import WorkforceSegmentScreen from "../screens/WorkforceSegmentScreen";

export const adminRoutes = [
  <Route key="admin-messagequeue" path="admin/messagequeue" element={<MessageQueueMonitorEnhanced />} />,
  <Route key="admin-slm-training" path="admin/slm-training" element={<SLMTrainingData />} />,
  <Route key="admin-slm-dashboard" path="admin/slm-dashboard" element={<SLMDashboard />} />,
  <Route key="admin-slm-learning-transcript" path="admin/slm-learning-transcript" element={<SLMLearningTranscript />} />,
  // Workforce Overview (bench / Staff Aug / Core), the employee-in-bench resource's page
  <Route key="workforce" path="workforce" element={<WorkforceOverviewScreen />} />,
  <Route key="workforce-flag" path="workforce/flags/:flagSlug" element={<WorkforceSegmentScreen />} />,
  <Route key="workforce-group" path="workforce/:groupSlug" element={<WorkforceSegmentScreen />} />
];
