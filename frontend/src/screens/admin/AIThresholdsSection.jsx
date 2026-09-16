import { useState } from "react";
import { X, AlertTriangle, CheckCircle } from "lucide-react";

function ConfigRow({ item, onSave }) {
  const [value, setValue] = useState(item.value);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const dirty = String(value) !== String(item.value);

  const handleSave = async () => {
    setSaving(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await onSave(item.config_key, item.value_type === "PERCENT" ? parseFloat(value) : parseInt(value, 10));
      setActionSuccess(`${item.label} updated.`);
    } catch (err) {
      setActionError(err.message || "Could not save this setting.");
      setValue(item.value);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      {actionError && (
        <div className="mb-3 flex items-start gap-3 rounded-lg bg-red-50 px-4 py-3 border border-red-200">
          <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">{actionError}</p>
          </div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="flex-shrink-0 text-red-400 hover:text-red-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}
      {actionSuccess && (
        <div className="mb-3 flex items-start gap-3 rounded-lg bg-green-50 px-4 py-3 border border-green-200">
          <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800">{actionSuccess}</p>
          </div>
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            className="flex-shrink-0 text-green-400 hover:text-green-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}
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
    </div>
  );
}

export default function AIThresholdsSection({ panel, onSave, loading }) {
  if (loading) return <div className="text-sm text-gray-500">Loading...</div>;
  if (!panel) return <div className="text-sm text-gray-400">No settings available.</div>;

  return (
    <div>
      <div className="text-sm text-gray-600 mb-4">
        Changes are Admin-only and take effect for every user within 60 seconds.
      </div>
      {panel.AI_THRESHOLDS && panel.AI_THRESHOLDS.length === 0 ? (
        <p className="text-sm text-gray-400">No settings in this category.</p>
      ) : (
        (panel.AI_THRESHOLDS || []).map((item) => (
          <ConfigRow key={item.config_key} item={item} onSave={onSave} />
        ))
      )}
    </div>
  );
}
