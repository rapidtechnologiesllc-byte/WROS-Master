// Renewals (CEO 2026-10-23): the extension pipeline for placements ending soon -- days left, bill
// rate, renewal status and owner (the client's account manager, else the BU Head, unless someone
// is set), with Extend (new date + rate + reason), Mark rolling off and Set owner / status. The
// renewal owner gets a task at the configured days before the end (60/30/15); the task opens
// this tab with ?allocation=<id>, which highlights that row.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CalendarClock, RefreshCw } from "lucide-react";
import { Button, Card, Select } from "../components/ui";
import cx from "../utils/cx";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import AllocationEditModal from "../components/AllocationEditModal";
import { marginLabel } from "../components/AllocationMargin";
import { getAllocations, getRenewals, updateRenewal } from "../services/api/allocations";
import { searchUsers } from "../services/api/users";

const STATUS_OPTIONS = [
  { value: "NOT_STARTED", label: "Not started" },
  { value: "IN_DISCUSSION", label: "In discussion" },
  { value: "EXTENDED", label: "Extended (agreed)" },
  { value: "ROLLING_OFF", label: "Rolling off" },
];
const STATUS_TONE = {
  NOT_STARTED: "bg-gray-100 text-gray-700",
  IN_DISCUSSION: "bg-sky-100 text-sky-800",
  EXTENDED: "bg-emerald-100 text-emerald-800",
  ROLLING_OFF: "bg-amber-100 text-amber-800",
};
const OWNER_SOURCE = { SET: "set", ACCOUNT_MANAGER: "account manager", BU_HEAD: "BU Head" };
const HORIZONS = [
  { value: "30", label: "Next 30 days" },
  { value: "60", label: "Next 60 days" },
  { value: "90", label: "Next 90 days" },
  { value: "180", label: "Next 180 days" },
];

const daysTone = (days, alertDays) => {
  if (days == null) return "text-gray-500";
  if (days < 0 || days <= Math.min(...alertDays)) return "font-semibold text-rose-700";
  if (days <= Math.max(...alertDays)) return "text-amber-700";
  return "text-gray-700";
};

function OwnerPicker({ row, users, onSave }) {
  const options = useMemo(() => [
    { value: "", label: `Default (${row.renewal_owner_source && row.renewal_owner_source !== "SET"
      ? OWNER_SOURCE[row.renewal_owner_source] : "account manager / BU Head"})` },
    ...users.map((u) => ({ value: u.UserID, label: u.UserName })),
  ], [users, row.renewal_owner_source]);
  const current = row.renewal_owner_source === "SET" ? row.renewal_owner_user_id : "";
  return <Select value={current} onChange={(value) => onSave({ ownerUserId: value })} options={options} />;
}

export default function RenewalsScreen() {
  const [searchParams] = useSearchParams();
  const focusId = searchParams.get("allocation");
  const [days, setDays] = useState("90");
  const [data, setData] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const canEdit = hasPermission("allocations", "edit");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getRenewals(days));
    } catch (err) {
      setError(err.message || "Failed to load renewals.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!canEdit) return;
    searchUsers({ limit: 200 })
      .then((res) => setUsers(res?.users || []))
      .catch((err) => setError(`Could not load people for the owner list: ${err.message}`));
  }, [canEdit]);

  useEffect(() => {
    if (!focusId || !data) return;
    const el = document.getElementById(`renewal-${focusId}`);
    if (el) el.scrollIntoView({ block: "center" });
  }, [focusId, data]);

  const save = async (row, change) => {
    setError("");
    try {
      await updateRenewal(row.allocation_id, change);
      await load();
    } catch (err) {
      setError(err.message || "Could not update the renewal.");
    }
  };

  const openExtend = async (row) => {
    setError("");
    try {
      const list = await getAllocations({ employeeId: row.employee_id });
      const allocation = list.find((a) => a.id === row.allocation_id);
      if (!allocation) throw new Error("The allocation is no longer visible.");
      setEditing(allocation);
    } catch (err) {
      setError(err.message || "Could not open the allocation.");
    }
  };

  const rows = data?.renewals || [];
  const alertDays = data?.alert_days?.length ? data.alert_days : [15];

  return (
    <Card
      title="Renewals"
      subtitle={`Placements ending soon and where each extension stands. Owners get a task ${alertDays.join(" / ")} days before the end.`}
      icon={<CalendarClock className="h-4 w-4" />}
      right={(
        <div className="flex items-center gap-2">
          <Select value={days} onChange={setDays} options={HORIZONS} />
          <Button variant="ghost" onClick={load}><RefreshCw className="h-4 w-4" /></Button>
        </div>
      )}
    >
      {error && <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
      {loading ? (
        <div className="py-6 text-center text-sm text-gray-500">Loading renewals…</div>
      ) : rows.length === 0 ? (
        <div className="py-6 text-center text-sm text-gray-500">No placement ends in the next {days} days.</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left">
              <tr>
                <th className="px-3 py-2 font-semibold">Consultant</th>
                <th className="px-3 py-2 font-semibold">Client · role</th>
                <th className="px-3 py-2 font-semibold">Ends</th>
                <th className="px-3 py-2 font-semibold">Days left</th>
                <th className="px-3 py-2 font-semibold">Bill rate</th>
                <th className="px-3 py-2 font-semibold">Margin</th>
                <th className="px-3 py-2 font-semibold">Status</th>
                <th className="px-3 py-2 font-semibold">Owner</th>
                <th className="px-3 py-2 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.allocation_id} id={`renewal-${row.allocation_id}`}
                  className={cx("border-b align-top", row.allocation_id === focusId && "bg-amber-50")}>
                  <td className="px-3 py-2 font-medium text-gray-900">{row.employee_name || "—"}</td>
                  <td className="px-3 py-2 text-gray-700">
                    {row.client_name || "—"}
                    <div className="text-xs text-gray-500">{row.role || row.job_title || ""}</div>
                  </td>
                  <td className="px-3 py-2 text-gray-700">{row.end_date}</td>
                  <td className={cx("px-3 py-2", daysTone(row.days_left, alertDays))}>
                    {row.days_left < 0 ? `${-row.days_left} overdue` : row.days_left}
                  </td>
                  <td className="px-3 py-2 text-gray-700">
                    {row.billing_rate_usd_cents ? `$${(row.billing_rate_usd_cents / 100).toFixed(2)}/h` : "—"}
                  </td>
                  <td className="px-3 py-2 text-gray-700">{marginLabel(row.margin_pct)}</td>
                  <td className="px-3 py-2">
                    {canEdit ? (
                      <Select value={row.renewal_status} options={STATUS_OPTIONS}
                        onChange={(value) => save(row, { renewalStatus: value })} />
                    ) : (
                      <span className={cx("rounded-full px-2 py-0.5 text-xs font-semibold", STATUS_TONE[row.renewal_status])}>
                        {STATUS_OPTIONS.find((o) => o.value === row.renewal_status)?.label}
                      </span>
                    )}
                    {row.renewal_note && <div className="mt-1 text-xs text-gray-500">{row.renewal_note}</div>}
                    {row.change_pending_approval && (
                      <div className="mt-1 text-xs font-semibold text-amber-700">Change awaiting margin approval</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-700">
                    {canEdit ? <OwnerPicker row={row} users={users} onSave={(c) => save(row, c)} /> : (
                      row.renewal_owner_name || "No owner"
                    )}
                    <div className="text-xs text-gray-500">
                      {row.renewal_owner_name || "nobody resolved"}
                      {row.renewal_owner_source ? ` (${OWNER_SOURCE[row.renewal_owner_source]})` : ""}
                    </div>
                  </td>
                  <td className="space-y-1 px-3 py-2">
                    {canEdit && (
                      <>
                        <Button variant="primary" size="sm" onClick={() => openExtend(row)}>Extend</Button>
                        {row.renewal_status !== "ROLLING_OFF" && (
                          <Button variant="ghost" size="sm" onClick={() => save(row, { renewalStatus: "ROLLING_OFF" })}>
                            Mark rolling off
                          </Button>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <AllocationEditModal allocation={editing} mode="extend" onClose={() => setEditing(null)} onSaved={load} />
      )}
    </Card>
  );
}
