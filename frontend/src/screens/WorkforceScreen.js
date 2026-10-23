// Workforce Overview (CEO 2026-10-17): where every employee stands (bench / Staff Aug / Core) and,
// in the same screen, utilization and bench cost. Each tab keeps its screen and permission.
import TabbedScreen from "../components/TabbedScreen";
import WorkforceOverviewScreen from "./WorkforceOverviewScreen";
import UtilizationDashboardScreen from "./UtilizationDashboardScreen";

const TABS = [
  { key: "overview", label: "Overview", resource: "workforce-overview", render: () => <WorkforceOverviewScreen /> },
  { key: "utilization", label: "Utilization & Bench Cost", resource: "utilization-dashboard", render: () => <UtilizationDashboardScreen /> },
];

export default function WorkforceScreen() {
  return <TabbedScreen title="Workforce Overview" tabs={TABS} />;
}
