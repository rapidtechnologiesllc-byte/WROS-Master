// Workforce Overview dashboard (CEO 2026-10-14): where every employee stands between the bench,
// Staff Aug and Direct. Each person is in exactly one group, so the groups add up to headcount.
// Every number is a link to its own page (WorkforceSegmentScreen) listing exactly those people.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Award, RefreshCw, Users, Flag } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { getWorkforceFilters, getWorkforceOverview, groupPath, toSlug } from "../services/api/workforce";
import { getCoreCertificationRequests } from "../services/api/coreCertification";

function CountTile({ to, count, label, description }) {
  return (
    <Link to={to} className="block rounded-xl border p-3 transition hover:border-gray-900 hover:bg-gray-50">
      <div className="text-2xl font-bold text-blue-700 underline-offset-2 hover:underline">{count}</div>
      <div className="text-sm font-semibold text-gray-800">{label}</div>
      <div className="mt-1 text-xs text-gray-500">{description}</div>
    </Link>
  );
}

const FILTERS = [
  { key: "function_id", label: "All functions", list: "functions" },
  { key: "business_unit_id", label: "All business units", list: "business_units" },
  { key: "company_id", label: "All companies", list: "companies" },
  { key: "location", label: "All locations", list: "locations" },
];

// A tile's link keeps the filters, so its page lists the people it counted
const withFilters = (path, query) => (query ? `${path}${path.includes("?") ? "&" : "?"}${query}` : path);

export default function WorkforceOverviewScreen() {
  const [data, setData] = useState(null);
  const [choices, setChoices] = useState(null);
  const [filters, setFilters] = useState({});
  const [pendingCertifications, setPendingCertifications] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const filterQuery = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [overview, pending] = await Promise.all([
        getWorkforceOverview(Object.fromEntries(new URLSearchParams(filterQuery))),
        getCoreCertificationRequests("PENDING").catch((err) => {
          console.error("[WorkforceOverview] Direct certification requests unavailable:", err);
          return null;
        }),
      ]);
      setData(overview);
      setPendingCertifications(pending ? pending.requests.length : null);
    } catch (err) {
      setError(err.message || "Failed to load the workforce overview.");
    } finally {
      setLoading(false);
    }
  }, [filterQuery]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    getWorkforceFilters().then(setChoices).catch((err) => {
      console.error("[WorkforceOverview] Filters unavailable:", err);
      setError(`Could not load the filters: ${err.message}`);
    });
  }, []);

  return (
    <div className="grid gap-4">
      <Card
        title="Workforce Overview"
        subtitle={`Every employee in one group: bench, Staff Aug or Direct. Headcount ${data?.headcount ?? "—"}. Click a number to see the people.`}
        icon={<Users className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {FILTERS.map((f) => (
            <select
              key={f.key}
              aria-label={f.label}
              value={filters[f.key] || ""}
              onChange={(e) => setFilters((current) => ({ ...current, [f.key]: e.target.value }))}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
            >
              <option value="">{f.label}</option>
              {(choices?.[f.list] || []).map((c) => (
                typeof c === "string"
                  ? <option key={c} value={c}>{c}</option>
                  : <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          ))}
          {filterQuery ? <Button variant="ghost" onClick={() => setFilters({})}>Clear filters</Button> : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(data?.groups || []).map((g) => (
            <CountTile key={g.key} to={withFilters(groupPath(g.key), filterQuery)} count={g.count} label={g.label} description={g.description} />
          ))}
        </div>
      </Card>

      <Card
        title="Direct certification"
        subtitle="Buddy graduated + 90 approved billable Staff Aug days with no escalation → BU Head approval."
        icon={<Award className="h-4 w-4" />}
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <CountTile
            to="/workforce/core-certification"
            count={pendingCertifications ?? "—"}
            label="Awaiting BU Head decision"
            description="Approve, or tell Flash why not and it sets up the follow-ups."
          />
        </div>
      </Card>

      <Card title="Watch list" subtitle="Across every group." icon={<Flag className="h-4 w-4" />}>
        <div className="grid gap-3 sm:grid-cols-3">
          {(data?.flags || []).map((f) => (
            <CountTile
              key={f.key}
              to={withFilters(`/workforce/flags/${toSlug(f.key)}`, filterQuery)}
              count={f.count}
              label={f.label}
              description={f.key === "rolling_off" ? `Allocation ends within ${data.roll_off_window_days} days.` : f.description}
            />
          ))}
        </div>
      </Card>
    </div>
  );
}
