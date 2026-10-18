// Demand vs Bench (CEO 2026-10-17): what demand is coming (Resource Forecast: expiring allocations,
// skill gaps) and who on the bench can meet it (Resource Management: bench scan and the RM's
// recommendation queue). Each tab keeps its screen and permission.
import TabbedScreen from "../components/TabbedScreen";
import ForecastScreen from "./ForecastScreen";
import ResourceManagementScreen from "./ResourceManagementScreen";

const TABS = [
  { key: "forecast", label: "Resource Forecast", resource: "resource-forecast", render: () => <ForecastScreen /> },
  { key: "bench", label: "Bench Matches", resource: "resources", render: () => <ResourceManagementScreen /> },
];

export default function DemandVsBenchScreen() {
  return <TabbedScreen title="Demand vs Bench" tabs={TABS} />;
}
