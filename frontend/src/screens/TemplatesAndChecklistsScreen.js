// Templates & Checklists (CEO 2026-10-23): checklist templates and candidate stage email templates.
// Both tabs are gated by "checklists", the resource their APIs check.
import TabbedScreen from "../components/TabbedScreen";
import ChecklistTemplatesScreen from "./ChecklistTemplatesScreen";
import EmailTemplatesScreen from "./SettingsScreens/EmailTemplatesScreen";
import TemplateCatalogScreen from "./SettingsScreens/TemplateCatalogScreen";

const TABS = [
  { key: "all", label: "All Messages", resource: "checklists", render: () => <TemplateCatalogScreen /> },
  { key: "checklists", label: "Checklists", resource: "checklists", render: () => <ChecklistTemplatesScreen /> },
  { key: "email", label: "Email Templates", resource: "checklists", render: () => <EmailTemplatesScreen /> },
];

export default function TemplatesAndChecklistsScreen() {
  return <TabbedScreen title="Templates & Checklists" tabs={TABS} />;
}
