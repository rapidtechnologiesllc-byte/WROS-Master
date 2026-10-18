// Agent Health (CEO 2026-10-17): every agent's maturity, success rate and trend (Agent State) and
// the weekly executive recap of agent health and pipeline (Weekly Recap). Each tab keeps its
// screen and permission (admin-agent-state / admin-weekly-recap).
import TabbedScreen from "../components/TabbedScreen";
import AdminAgentStateDashboard from "./AdminAgentStateDashboard";
import AdminWeeklyRecapDashboard from "./AdminWeeklyRecapDashboard";

const TABS = [
  { key: "state", label: "Agent State", resource: "admin-agent-state", render: () => <AdminAgentStateDashboard /> },
  { key: "recap", label: "Weekly Recap", resource: "admin-weekly-recap", render: () => <AdminWeeklyRecapDashboard /> },
];

export default function AgentHealthScreen() {
  return <TabbedScreen title="Agent Health" tabs={TABS} />;
}
