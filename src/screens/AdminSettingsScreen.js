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
import { apiRequest } from "../services/api/client";
import { ROUTES } from "../utils/Routes";
import { Plus, Edit2, Trash2, Building2, MapPin } from "lucide-react";

const CATEGORIES = [
  { key: "ORGANIZATION", label: "Organization" },
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

function OrganizationSection() {
  const [orgTab, setOrgTab] = useState("business-units");
  const [businessUnits, setBusinessUnits] = useState([]);
  const [deliveryCenters, setDeliveryCenters] = useState([
    { id: 1, name: "Austin, TX", type: "HQ", buServed: ["North America"], headcount: 150 },
    { id: 2, name: "Youngstown, OH", type: "Delivery", buServed: ["North America"], headcount: 300 },
  ]);
  const [showAddBUModal, setShowAddBUModal] = useState(false);
  const [newBUName, setNewBUName] = useState("");
  const [newBUDescription, setNewBUDescription] = useState("");
  const [isSubmittingBU, setIsSubmittingBU] = useState(false);

  // Load business units from database via API (same source as Create User dropdown)
  useEffect(() => {
    const loadBusinessUnits = async () => {
      try {
        const { data } = await apiRequest("/bu-context/available-buses", {
          skipAuth: true,
          method: "GET"
        });
        const busData = data?.business_units || [];
        setBusinessUnits(busData);
      } catch (err) {
        console.error("Failed to load business units:", err);
        setBusinessUnits([]);
      }
    };
    loadBusinessUnits();
  }, []);

  const handleAddBusinessUnit = async (e) => {
    e.preventDefault();
    if (!newBUName.trim()) {
      return;
    }

    setIsSubmittingBU(true);
    try {
      const payload = {
        name: newBUName.trim(),
        description: newBUDescription.trim() || null,
      };

      await apiRequest("/rbac/business-units", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      // Refresh business units list
      const { data } = await apiRequest("/bu-context/available-buses", {
        skipAuth: true,
        method: "GET"
      });
      const busData = data?.business_units || [];
      setBusinessUnits(busData);

      // Close modal and reset form
      setShowAddBUModal(false);
      setNewBUName("");
      setNewBUDescription("");
    } catch (err) {
      console.error("Failed to add business unit:", err);
    } finally {
      setIsSubmittingBU(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-200">
        <button
          onClick={() => setOrgTab("business-units")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            orgTab === "business-units"
              ? "border-bx-orange text-bx-orange"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          <Building2 className="inline h-4 w-4 mr-2" />
          Business Units
        </button>
        <button
          onClick={() => setOrgTab("delivery-centers")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            orgTab === "delivery-centers"
              ? "border-bx-orange text-bx-orange"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          <MapPin className="inline h-4 w-4 mr-2" />
          Delivery Centers
        </button>
        <button
          onClick={() => setOrgTab("hierarchy")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            orgTab === "hierarchy"
              ? "border-bx-orange text-bx-orange"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          Organizational Hierarchy
        </button>
      </div>

      {/* Business Units Tab */}
      {orgTab === "business-units" && (
        <div className="space-y-4">
          <button
            onClick={() => setShowAddBUModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium">
            <Plus className="h-4 w-4" />
            Add Business Unit
          </button>
          <div className="space-y-3">
            {businessUnits.map((bu) => (
              <div key={bu.id} className="border border-gray-200 rounded-lg p-4 flex items-start justify-between hover:bg-gray-50">
                <div className="flex-1">
                  <h4 className="font-semibold text-gray-900">{bu.name}</h4>
                  <div className="grid grid-cols-3 gap-4 mt-2 text-sm text-gray-600">
                    <div><span className="font-medium">Region:</span> {bu.region || "-"}</div>
                    <div><span className="font-medium">Continent:</span> {bu.continent || "-"}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="p-2 text-blue-600 hover:bg-blue-50 rounded"><Edit2 className="h-4 w-4" /></button>
                  <button className="p-2 text-red-600 hover:bg-red-50 rounded"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add Business Unit Modal */}
      {showAddBUModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Add Business Unit</h3>
              <button
                onClick={() => setShowAddBUModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleAddBusinessUnit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Unit Name *
                </label>
                <input
                  type="text"
                  value={newBUName}
                  onChange={(e) => setNewBUName(e.target.value)}
                  placeholder="e.g., Asia Pacific"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  disabled={isSubmittingBU}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description (Optional)
                </label>
                <textarea
                  value={newBUDescription}
                  onChange={(e) => setNewBUDescription(e.target.value)}
                  placeholder="Add a description..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  rows="3"
                  disabled={isSubmittingBU}
                />
              </div>
              <div className="flex gap-2 justify-end pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddBUModal(false)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                  disabled={isSubmittingBU}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                  disabled={!newBUName.trim() || isSubmittingBU}
                >
                  {isSubmittingBU ? "Adding..." : "Add Business Unit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delivery Centers Tab */}
      {orgTab === "delivery-centers" && (
        <div className="space-y-4">
          <button className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium">
            <Plus className="h-4 w-4" />
            Add Delivery Center
          </button>
          <div className="space-y-3">
            {deliveryCenters.map((dc) => (
              <div key={dc.id} className="border border-gray-200 rounded-lg p-4 flex items-start justify-between hover:bg-gray-50">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h4 className="font-semibold text-gray-900">{dc.name}</h4>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      dc.type === "HQ"
                        ? "bg-purple-100 text-purple-800"
                        : "bg-blue-100 text-blue-800"
                    }`}>
                      {dc.type}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-4 mt-2 text-sm text-gray-600">
                    <div><span className="font-medium">Serves:</span> {dc.buServed.join(", ")}</div>
                    <div><span className="font-medium">Headcount:</span> {dc.headcount}</div>
                    <div><span className="font-medium">Type:</span> {dc.type === "HQ" ? "Headquarters" : "Delivery Center"}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="p-2 text-blue-600 hover:bg-blue-50 rounded"><Edit2 className="h-4 w-4" /></button>
                  <button className="p-2 text-red-600 hover:bg-red-50 rounded"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hierarchy Tab */}
      {orgTab === "hierarchy" && (
        <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
          <h3 className="font-semibold text-gray-900 mb-6">Organizational Hierarchy Map</h3>

          {/* North America */}
          <div className="mb-8 border-l-4 border-blue-500 pl-4">
            <h4 className="font-semibold text-gray-900 mb-3">North America (BU Head: John Smith)</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white p-4 rounded border border-gray-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded">HQ</span>
                  <span className="font-medium">Austin, TX</span>
                </div>
                <p className="text-sm text-gray-600">Headcount: 150</p>
              </div>
              <div className="bg-white p-4 rounded border border-gray-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded">Delivery</span>
                  <span className="font-medium">Youngstown, OH</span>
                </div>
                <p className="text-sm text-gray-600">Headcount: 300</p>
              </div>
            </div>
          </div>

          {/* India */}
          <div className="border-l-4 border-green-500 pl-4">
            <h4 className="font-semibold text-gray-900 mb-3">India (BU Head: Raj Patel)</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white p-4 rounded border border-gray-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded">HQ</span>
                  <span className="font-medium">Hyderabad, India</span>
                </div>
                <p className="text-sm text-gray-600">Headcount: 200</p>
              </div>
              <div className="bg-white p-4 rounded border border-gray-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded">Delivery</span>
                  <span className="font-medium">Chennai, India</span>
                </div>
                <p className="text-sm text-gray-600">Headcount: 400</p>
              </div>
            </div>
          </div>
        </div>
      )}
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

  if (!panel) {
    return <div className="p-6 text-sm text-gray-500">No settings available.</div>;
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
        ) : activeCategory === "ORGANIZATION" ? (
          <Card
            title="Organization"
            subtitle="Manage Business Units, Delivery Centers, and organizational hierarchy."
          >
            <OrganizationSection />
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
