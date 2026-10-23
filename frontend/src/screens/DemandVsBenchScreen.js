// Demand vs Bench (CEO 2026-10-17): what demand is coming (Resource Forecast: expiring allocations,
// skill gaps) and who on the bench can meet it (Resource Management: bench scan and the RM's
// recommendation queue). Each tab keeps its screen and permission.
import TabbedScreen from "../components/TabbedScreen";
import ForecastScreen from "./ForecastScreen";
import RenewalsScreen from "./RenewalsScreen";
import ResourceManagementScreen from "./ResourceManagementScreen";

// Renewals: the extension pipeline for the same roll-off list (CEO 2026-10-23); its API checks
// resource-forecast view, its actions the allocations edit permission
const TABS = [
  { key: "forecast", label: "Resource Forecast", resource: "resource-forecast", render: () => <ForecastScreen /> },
  { key: "renewals", label: "Renewals", resource: "resource-forecast", render: () => <RenewalsScreen /> },
  { key: "bench", label: "Bench Matches", resource: "resources", render: () => <ResourceManagementScreen /> },
];

export default function DemandVsBenchScreen() {
  return <TabbedScreen title="Demand vs Bench" tabs={TABS} />;
}
