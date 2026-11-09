// Workforce Overview (CEO 2026-10-17): where every employee stands (bench / Staff Aug / Direct) and,
// in the same screen, utilization and bench cost; since 2026-11-09 also the Buddy Program, HTD intake and
// Demand vs Bench (forecast, renewals, bench matches). Each tab keeps its screen and permission.
import TabbedScreen from "../components/TabbedScreen";
import WorkforceOverviewScreen from "./WorkforceOverviewScreen";
import UtilizationDashboardScreen from "./UtilizationDashboardScreen";
import BuddyProgramListScreen from "./BuddyProgramListScreen";
import HtdIntakeScreen from "./HtdIntakeScreen";
import { TABS as DEMAND_TABS } from "./DemandVsBenchScreen";

const TABS = [
  { key: "overview", label: "Overview", resource: "workforce-overview", render: () => <WorkforceOverviewScreen /> },
  { key: "utilization", label: "Utilization & Bench Cost", resource: "utilization-dashboard", render: () => <UtilizationDashboardScreen /> },
  ...DEMAND_TABS,
  { key: "buddy", label: "Buddy Program", resource: "buddy-program", render: () => <BuddyProgramListScreen /> },
  { key: "htd", label: "HTD Intake", resource: "htd-intake", render: () => <HtdIntakeScreen /> },
];

export default function WorkforceScreen() {
  return <TabbedScreen title="Workforce Overview" tabs={TABS} />;
}
