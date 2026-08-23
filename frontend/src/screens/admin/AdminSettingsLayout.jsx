import { useParams, useNavigate } from "react-router-dom";
import { Card } from "../../components/ui";
import { ROUTES } from "../../utils/Routes";

const CATEGORIES = [
  { key: "organization", label: "Organization", route: ROUTES.ADMIN_SETTINGS_ORGANIZATION },
  { key: "ai-thresholds", label: "AI Thresholds", route: ROUTES.ADMIN_SETTINGS_AI_THRESHOLDS },
  { key: "sla", label: "SLA", route: ROUTES.ADMIN_SETTINGS_SLA },
  { key: "channels", label: "Channels", route: ROUTES.ADMIN_SETTINGS_CHANNELS },
  { key: "locale", label: "Locale", route: ROUTES.ADMIN_SETTINGS_LOCALE },
];

export default function AdminSettingsLayout({ section, children, title, subtitle, forbidden, loading }) {
  const navigate = useNavigate();

  if (loading) {
    return <div className="p-6 text-sm text-gray-500">Loading settings...</div>;
  }

  if (forbidden) {
    return (
      <div className="p-6">
        <Card title="Admin Settings">
          <p className="text-sm text-gray-500">
            You can view platform behavior below, but only an Admin can change it.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl gap-6 p-6">
      {/* Sidebar Navigation */}
      <aside className="w-52 shrink-0">
        <nav className="space-y-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              type="button"
              onClick={() => navigate(cat.route)}
              className={`block w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
                section === cat.key
                  ? "bg-bx-orange/10 text-bx-orange"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="min-w-0 flex-1">
        <Card title={title} subtitle={subtitle}>
          {children}
        </Card>
      </main>
    </div>
  );
}
