// Workforce Overview (CEO 2026-10-14): where every employee stands between the bench, Staff Aug
// and Core. Each person is in exactly one group, so the tiles add up to headcount. Groups,
// labels and flags all come from GET /workforce/overview; nothing is decided here.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, Users } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { getWorkforceOverview } from "../services/api/workforce";

const Th = ({ children }) => <th className="px-4 py-3 text-xs font-semibold text-gray-700">{children}</th>;

function Flags({ person, windowDays }) {
  const flags = [];
  if (person.rolling_off) flags.push(`Rolling off (≤${windowDays}d)`);
  if (person.open_escalations) flags.push(`${person.open_escalations} open escalation(s)`);
  if (person.notice_period) flags.push("Notice period");
  if (!flags.length) return <span className="text-gray-400">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {flags.map((f) => (
        <span key={f} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">{f}</span>
      ))}
    </div>
  );
}

export default function WorkforceOverviewScreen() {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const overview = await getWorkforceOverview();
      setData(overview);
      setSelected((current) => current || overview?.groups?.find((g) => g.count)?.key || "");
    } catch (err) {
      setError(err.message || "Failed to load the workforce overview.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const groups = data?.groups || [];
  const group = groups.find((g) => g.key === selected);

  return (
    <div className="grid gap-4">
      <Card
        title="Workforce Overview"
        subtitle={`Every employee in one group: bench, Staff Aug or Core. Headcount ${data?.headcount ?? "—"}.`}
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
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {groups.map((g) => (
            <button
              key={g.key}
              type="button"
              onClick={() => setSelected(g.key)}
              className={cx(
                "rounded-xl border p-3 text-left transition",
                selected === g.key ? "border-gray-900 bg-gray-50" : "hover:border-gray-400",
              )}
            >
              <div className="text-2xl font-bold text-gray-900">{g.count}</div>
              <div className="text-sm font-semibold text-gray-800">{g.label}</div>
              <div className="mt-1 text-xs text-gray-500">{g.description}</div>
            </button>
          ))}
        </div>
        {data ? (
          <div className="mt-3 text-xs text-gray-500">
            Rolling off within {data.roll_off_window_days} days: {data.flags?.rolling_off || 0} · With open escalations:{" "}
            {data.flags?.open_escalations || 0} · On notice: {data.flags?.notice_period || 0}
          </div>
        ) : null}
      </Card>

      {group ? (
        <Card title={`${group.label} (${group.count})`} subtitle={group.description}>
          <div className="overflow-visible rounded-2xl border">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <Th>Employee</Th>
                  <Th>Business Unit</Th>
                  <Th>Buddy / Core</Th>
                  <Th>Client / Project</Th>
                  <Th>Allocation Ends</Th>
                  <Th>Flags</Th>
                </tr>
              </thead>
              <tbody className="divide-y bg-white">
                {group.people.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500">Nobody in this group.</td>
                  </tr>
                ) : (
                  group.people.map((p) => (
                    <tr key={p.employee_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        {p.candidate_id ? (
                          <Link to={`/candidates/${encodeURIComponent(p.candidate_id)}`} className="font-semibold text-blue-700 hover:underline">
                            {p.name}
                          </Link>
                        ) : (
                          <span className="font-semibold">{p.name}</span>
                        )}
                        <div className="text-xs text-gray-500">{p.status.replace(/_/g, " ")}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-700">{p.business_unit || "—"}</td>
                      <td className="px-4 py-3 text-xs text-gray-700">
                        Buddy {p.buddy_program_status.replace(/_/g, " ").toLowerCase()}
                        <div>{p.core_certified ? "Core-certified" : "Not Core-certified"}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-700">
                        <div className="font-semibold text-gray-900">{p.client || "—"}</div>
                        {p.project || ""}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-700">{p.allocation_end_date || "—"}</td>
                      <td className="px-4 py-3 text-xs"><Flags person={p} windowDays={data.roll_off_window_days} /></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
