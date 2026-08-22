import { useState } from "react";
import { toast } from "react-toastify";

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

export default function SLASection({ panel, onSave, loading }) {
  if (loading) return <div className="text-sm text-gray-500">Loading...</div>;
  if (!panel) return <div className="text-sm text-gray-400">No settings available.</div>;

  return (
    <div>
      <div className="text-sm text-gray-600 mb-4">
        Changes are Admin-only and take effect for every user within 60 seconds.
      </div>
      {panel.SLA && panel.SLA.length === 0 ? (
        <p className="text-sm text-gray-400">No settings in this category.</p>
      ) : (
        (panel.SLA || []).map((item) => (
          <ConfigRow key={item.config_key} item={item} onSave={onSave} />
        ))
      )}
    </div>
  );
}
