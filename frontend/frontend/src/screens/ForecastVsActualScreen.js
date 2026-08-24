// S-242 (HRMS-0902) - Forecast vs Actual Revenue Tracking
// Shows projected revenue vs invoiced actual for each client, by month
import { useEffect, useState } from "react";
import { TrendingUp, RefreshCw, AlertCircle } from "lucide-react";
import { Card, Button, Select } from "../components/ui";
import cx from "../utils/cx";
import { forecastVsActual, forecastVsActualTrend } from "../services/api/revenue";
import { listBusinessUnits } from "../services/api/rbac";

function MetricRow({ label, forecast, actual, variance }) {
  const isNegative = variance < 0;
  const variancePercent = forecast > 0 ? ((variance / forecast) * 100).toFixed(1) : "—";
  return (
    <div className="flex items-center justify-between gap-4 border-b py-2 text-xs last:border-b-0">
      <span className="font-medium text-gray-900">{label}</span>
      <div className="flex gap-8">
        <div className="w-24 text-right">
          <div className="font-semibold text-gray-900">${forecast.toLocaleString()}</div>
          <div className="text-[11px] text-gray-500">Forecast</div>
        </div>
        <div className="w-24 text-right">
          <div className="font-semibold text-gray-900">${actual.toLocaleString()}</div>
          <div className="text-[11px] text-gray-500">Invoiced</div>
        </div>
        <div className={cx("w-24 text-right", isNegative ? "text-amber-700" : "text-emerald-700")}>
          <div className="font-semibold">${variance.toLocaleString()}</div>
          <div className="text-[11px]">{variancePercent}% var</div>
        </div>
      </div>
    </div>
  );
}

export default function ForecastVsActualScreen() {
  const [data, setData] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [businessUnits, setBusinessUnits] = useState([]);
  const [businessUnitId, setBusinessUnitId] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);

  const months = [
    { label: "January", value: 1 },
    { label: "February", value: 2 },
    { label: "March", value: 3 },
    { label: "April", value: 4 },
    { label: "May", value: 5 },
    { label: "June", value: 6 },
    { label: "July", value: 7 },
    { label: "August", value: 8 },
    { label: "September", value: 9 },
    { label: "October", value: 10 },
    { label: "November", value: 11 },
    { label: "December", value: 12 },
  ];

  useEffect(() => {
    listBusinessUnits()
      .then((list) => setBusinessUnits(list || []))
      .catch((err) => console.error("Failed to load business units:", err));
  }, []);

  const buOptions = [
    { label: "All Business Units", value: "" },
    ...businessUnits.map((bu) => ({ label: bu.name, value: bu.id })),
  ];

  const monthOptions = months;
  const yearOptions = Array.from({ length: 5 }, (_, i) => ({
    label: String(year - i),
    value: year - i,
  }));

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const params = { year, month };
      const fvaRes = businessUnitId
        ? await forecastVsActual(year, month, businessUnitId)
        : await forecastVsActual(year, month);
      const trendRes = await forecastVsActualTrend(year);
      setData(fvaRes);
      setTrendData(trendRes);
    } catch (err) {
      setError(err.message || "Failed to load forecast vs actual data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [businessUnitId, year, month]);

  const summaryRows = data
    ? [
        {
          label: "Total Forecast",
          forecast: data.total_forecast_usd_cents / 100,
          actual: data.total_invoiced_usd_cents / 100,
          variance: (data.total_forecast_usd_cents - data.total_invoiced_usd_cents) / 100,
        },
        ...(data.by_client || []).map((row) => ({
          label: row.client_name,
          forecast: row.forecast_usd_cents / 100,
          actual: row.invoiced_usd_cents / 100,
          variance: (row.forecast_usd_cents - row.invoiced_usd_cents) / 100,
        })),
      ]
    : [];

  return (
    <div className="grid gap-4">
      <Card
        title="Forecast vs Actual Revenue"
        subtitle="Monthly revenue forecast vs actual invoiced amount by client"
        icon={<TrendingUp className="h-4 w-4" />}
        right={
          <div className="flex items-center gap-2">
            <div className="w-40">
              <Select label="" value={businessUnitId} onChange={setBusinessUnitId} options={buOptions} />
            </div>
            <div className="w-32">
              <Select label="" value={String(month)} onChange={(v) => setMonth(Number(v))} options={monthOptions} />
            </div>
            <div className="w-28">
              <Select label="" value={String(year)} onChange={(v) => setYear(Number(v))} options={yearOptions} />
            </div>
            <Button variant="ghost" onClick={load} disabled={loading}>
              <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} />
            </Button>
          </div>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : summaryRows.length === 0 ? (
          <div className="py-8 text-center text-sm text-gray-500">No data for selected period.</div>
        ) : (
          <div className="space-y-4">
            {summaryRows.map((row, idx) => (
              <MetricRow key={idx} label={row.label} forecast={row.forecast} actual={row.actual} variance={row.variance} />
            ))}
          </div>
        )}
      </Card>

      {trendData && trendData.months && trendData.months.length > 0 ? (
        <Card
          title="Year-to-Date Trend"
          subtitle="Monthly forecast vs actual throughout the year"
          icon={<TrendingUp className="h-4 w-4" />}
        >
          <div className="space-y-2 text-xs">
            {trendData.months.map((m) => (
              <MetricRow
                key={m.month}
                label={`${m.month}`}
                forecast={m.forecast_usd_cents / 100}
                actual={m.invoiced_usd_cents / 100}
                variance={(m.forecast_usd_cents - m.invoiced_usd_cents) / 100}
              />
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
