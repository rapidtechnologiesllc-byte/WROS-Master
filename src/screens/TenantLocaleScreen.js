// S-219/HRMS-0121 -- Multi-Continent Locale & Currency Config. Display
// preferences only -- every monetary field in this system still stores
// USD cents as its base unit; no currency-conversion math happens here
// (no exchange-rate source exists in this codebase).
import { useEffect, useState } from "react";
import { Globe2, RefreshCw } from "lucide-react";
import { Card, Button, Select } from "../components/ui";
import { getTenantLocale, updateTenantLocale } from "../services/api/tenant";

const DATE_FORMATS = ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"];
const CURRENCIES = ["USD", "INR", "GBP", "EUR", "CAD", "AUD"];
const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Europe/London",
  "Asia/Kolkata",
  "Asia/Dubai",
  "Australia/Sydney",
];

export default function TenantLocaleScreen() {
  const [locale, setLocale] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getTenantLocale();
      setLocale(res);
    } catch (err) {
      setError(err.message || "Failed to load locale settings.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const res = await updateTenantLocale({
        default_timezone: locale.default_timezone,
        default_date_format: locale.default_date_format,
        default_currency: locale.default_currency,
      });
      setLocale(res);
      setNotice("Saved.");
    } catch (err) {
      setError(err.message || "Failed to save locale settings.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Locale & Currency"
        subtitle="Per-tenant timezone, date format, and default display currency. Monetary fields always store in USD base -- this only controls how they display."
        icon={<Globe2 className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        {notice ? (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</div>
        ) : null}

        {loading || !locale ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : (
          <div className="grid max-w-xl gap-4">
            <Select
              label="Timezone"
              value={locale.default_timezone}
              onChange={(v) => setLocale({ ...locale, default_timezone: v })}
              options={TIMEZONES}
            />
            <Select
              label="Date Format"
              value={locale.default_date_format}
              onChange={(v) => setLocale({ ...locale, default_date_format: v })}
              options={DATE_FORMATS}
            />
            <Select
              label="Default Display Currency"
              value={locale.default_currency}
              onChange={(v) => setLocale({ ...locale, default_currency: v })}
              options={CURRENCIES}
            />
            <div className="text-xs text-gray-400">
              No currency conversion is applied -- this only sets the display currency label. All monetary amounts remain stored and computed in USD.
            </div>
            <Button variant="primary" disabled={saving} onClick={handleSave} className="w-fit">
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
