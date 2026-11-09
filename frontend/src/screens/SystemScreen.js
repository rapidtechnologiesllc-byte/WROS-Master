// System (CEO 2026-11-09): the technical screens in one place, for administrators -- the backend's health,
// error logs, agent health, the message queue, the resume model's learning and AI configuration. Each tab keeps
// its screen and the permission its API checks, so nobody sees more or less than before.
import TabbedScreen from "../components/TabbedScreen";
import SystemHealth from "./SystemHealth";
import ErrorLogScreen from "./ErrorLogScreen";
import MessageQueueMonitorEnhanced from "./MessageQueueMonitorEnhanced";
import TenantAIConfigScreen from "./TenantAIConfigScreen";
import { TABS as AGENT_TABS } from "./AgentHealthScreen";
import { TABS as SLM_TABS } from "./SlmLearningScreen";

const TABS = [
  { key: "health", label: "System Health", resource: "system-health", render: () => <SystemHealth /> },
  { key: "errors", label: "Error Logs", resource: "error-logs", render: () => <ErrorLogScreen /> },
  ...AGENT_TABS,
  { key: "queue", label: "Message Queue", resource: "message-queue", render: () => <MessageQueueMonitorEnhanced /> },
  ...SLM_TABS,
  { key: "ai", label: "AI Config", resource: "ai-config", render: () => <TenantAIConfigScreen /> },
];

export default function SystemScreen() {
  return <TabbedScreen title="System" tabs={TABS} />;
}
