import { lazy } from "react";
import { Route } from "react-router-dom";
import { Navigate } from "react-router-dom";

// Screens load when first opened (one chunk each), not all in the bundle every page downloads
const MessageQueueMonitorEnhanced = lazy(() => import("../screens/MessageQueueMonitorEnhanced"));
const SlmLearningScreen = lazy(() => import("../screens/SlmLearningScreen"));
const WorkforceScreen = lazy(() => import("../screens/WorkforceScreen"));
const WorkforceSegmentScreen = lazy(() => import("../screens/WorkforceSegmentScreen"));
const BenchScreen = lazy(() => import("../screens/BenchScreen"));
const CoreCertificationScreen = lazy(() => import("../screens/CoreCertificationScreen"));

export const adminRoutes = [
  <Route key="admin-messagequeue" path="admin/messagequeue" element={<MessageQueueMonitorEnhanced />} />,
  // SLM Learning: model, training data and learning transcript, a tab each (old routes redirect)
  <Route key="admin-slm" path="admin/slm" element={<SlmLearningScreen />} />,
  <Route key="admin-slm-training" path="admin/slm-training" element={<Navigate to="/admin/slm?view=training" replace />} />,
  <Route key="admin-slm-dashboard" path="admin/slm-dashboard" element={<Navigate to="/admin/slm?view=dashboard" replace />} />,
  <Route key="admin-slm-learning-transcript" path="admin/slm-learning-transcript" element={<Navigate to="/admin/slm?view=transcript" replace />} />,
  // Workforce Overview (bench / Staff Aug / Core) + Utilization & Bench Cost, a tab each
  <Route key="workforce" path="workforce" element={<WorkforceScreen />} />,
  <Route key="workforce-flag" path="workforce/flags/:flagSlug" element={<WorkforceSegmentScreen />} />,
  <Route key="workforce-core-cert" path="workforce/core-certification" element={<CoreCertificationScreen />} />,
  <Route key="workforce-bench" path="workforce/bench" element={<BenchScreen />} />,
  <Route key="workforce-group" path="workforce/:groupSlug" element={<WorkforceSegmentScreen />} />
];
