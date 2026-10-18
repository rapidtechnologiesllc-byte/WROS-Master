// Recruiter Watch (CEO 2026-10-17): candidates who need a human now (Intervention Queue), every
// active candidate's risk (Risk Dashboard) and Thunder's own performance (Thunder Analytics) in one
// screen. Each tab keeps its screen and permission.
import TabbedScreen from "../components/TabbedScreen";
import InterventionQueueScreen from "./InterventionQueueScreen";
import RiskDashboardScreen from "./RiskDashboardScreen";
import ThunderAnalyticsScreen from "./ThunderAnalyticsScreen";

const TABS = [
  { key: "queue", label: "Intervention Queue", resource: "intervention-queue", render: () => <InterventionQueueScreen /> },
  { key: "risk", label: "Risk", resource: "risk-dashboard", render: () => <RiskDashboardScreen /> },
  { key: "thunder", label: "Thunder Analytics", resource: "thunder-analytics", render: () => <ThunderAnalyticsScreen /> },
];

export default function RecruiterWatchScreen() {
  return <TabbedScreen title="Recruiter Watch" tabs={TABS} />;
}
