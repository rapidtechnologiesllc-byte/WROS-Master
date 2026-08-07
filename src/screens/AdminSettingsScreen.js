// S-213/HRMS-0115 -- System Configuration & Admin Settings Panel.
// Layout modeled on the HubSpot Settings reference Avinash shared: a
// left category sidebar + a right-hand list of settings rows, each with
// a name/description on the left and its control on the right.
//
// Locale is NOT reimplemented here -- TenantLocaleScreen (S-219/
// HRMS-0121, route ROUTES.TENANT_LOCALE) already owns those exact three
// fields for real. A second form here would be a second source of
// truth for the same setting; this tab links out to the real one instead.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Card } from "../components/ui";
import { getSettingsPanel, updateSetting } from "../services/api/systemConfig";
import { ROUTES } from "../utils/Routes";

const CATEGORIES = [
  { key: "AI_THRESHOLDS", label: "AI Thresholds" },
  { key: "SLA", label: "SLA" },
  { key: "CHANNELS", label: "Channels" },
  { key: "LOCALE", label: "Locale" },
];

function ConfigRow({ item, onSave }) {
  const [value, setValue] = useState(item.value);
  const [saving, setSaving] = useState(false);
  const dirty = String(value) !== String(item.value);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(item.config_key, item.value_type === "PERCENT" ? parseFloat(value) : parseInt(value, 10));
      toast.success(`${item.label} updated.`);
    } catch (err) {
      toast.error(err.message || "Could not save this setting.");
      setValue(item.value);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 border-b border-gray-100 py-3 last:border-b-0">
      <div className="min-w-0">
        <div className="text-sm font-medium text-gray-900">{item.label}</div>
        <div className="mt-0.5 text-xs text-gray-500">
          {item.value_type === "PERCENT"
            ? `Range ${item.min_value} - ${item.max_value}`
            : `Range ${item.min_value} - ${item.max_value}`}
          {" · default "}
          {item.default}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <input
          type="number"
          step={item.value_type === "PERCENT" ? "0.01" : "1"}
          min={item.min_value ?? undefined}
          max={item.max_value ?? undefined}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-24 rounded-xl border bg-white px-3 py-1.5 text-sm outline-none focus:border-bx-orange"
        />
        {dirty ? (
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-bx-orange px-3 py-1.5 text-xs font-semibold text-white hover:bg-bx-orange-hover disabled:opacity-60"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function LocaleSection({ locale }) {
  const navigate = useNavigate();
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
        <div>
          <div className="text-xs font-semibold text-gray-500">Timezone</div>
          <div className="mt-0.5 text-gray-900">{locale.default_timezone}</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-gray-500">Date Format</div>
          <div className="mt-0.5 text-gray-900">{locale.default_date_format}</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-gray-500">Currency</div>
          <div className="mt-0.5 text-gray-900">{locale.default_currency}</div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => navigate(ROUTES.TENANT_LOCALE)}
        className="rounded-lg bg-bx-orange px-3.5 py-2 text-sm font-semibold text-white hover:bg-bx-orange-hover"
      >
        Manage Locale & Currency
      </button>
    </div>
  );
}

export default function AdminSettingsScreen() {
  const [panel, setPanel] = useState(null);
  const [activeCategory, setActiveCategory] = useState("AI_THRESHOLDS");
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);

  const load = () => {
    setLoading(true);
    getSettingsPanel()
      .then(setPanel)
      .catch((err) => {
        if (err.status === 403) setForbidden(true);
        else toast.error("Could not load settings.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, []);

  const handleSaveConfig = async (key, value) => {
    await updateSetting(key, value);
    load();
  };

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
      <aside className="w-52 shrink-0">
        <nav className="space-y-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              type="button"
              onClick={() => setActiveCategory(cat.key)}
              className={`block w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
                activeCategory === cat.key
                  ? "bg-bx-orange/10 text-bx-orange"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="min-w-0 flex-1">
        {activeCategory === "LOCALE" ? (
          <Card
            title="Locale"
            subtitle="Default timezone, date format, and currency for this tenant."
          >
            <LocaleSection locale={panel.LOCALE} />
          </Card>
        ) : (
          <Card
            title={CATEGORIES.find((c) => c.key === activeCategory)?.label}
            subtitle="Changes are Admin-only and take effect for every user within 60 seconds."
          >
            {panel[activeCategory].length === 0 ? (
              <p className="text-sm text-gray-400">No settings in this category.</p>
            ) : (
              panel[activeCategory].map((item) => (
                <ConfigRow key={item.config_key} item={item} onSave={handleSaveConfig} />
              ))
            )}
          </Card>
        )}
      </main>
    </div>
  );
}
