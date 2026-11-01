// One conference, one cost (CEO 2026-10-31): every teammate's expenses for the event roll up
// here -- the total, how much is approved, and what each client (or internal BD) and each person
// carries. Finance folds a duplicate event into the right one with Merge.
import { useEffect, useState } from "react";
import { Card, Button, Select, Table } from "./ui";
import { getExpenseEventSummary, mergeExpenseEvent, searchExpenseEvents } from "../services/api/expenses";

const usd = (cents) =>
  `$${((cents || 0) / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function ConferenceCostCard() {
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState("");
  const [summary, setSummary] = useState(null);
  const [mergeInto, setMergeInto] = useState("");
  const [error, setError] = useState("");

  const loadEvents = async () => {
    try {
      const data = await searchExpenseEvents("");
      setEvents(data?.events || []);
      setError("");
    } catch (err) {
      setError(`Couldn't load conferences: ${err.message}`);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  useEffect(() => {
    if (!eventId) {
      setSummary(null);
      return;
    }
    getExpenseEventSummary(eventId)
      .then((data) => {
        setSummary(data);
        setError("");
      })
      .catch((err) => setError(`Couldn't load the conference cost: ${err.message}`));
  }, [eventId]);

  const merge = async () => {
    try {
      const target = await mergeExpenseEvent(eventId, mergeInto);
      setMergeInto("");
      await loadEvents();
      setEventId(target.id);
    } catch (err) {
      setError(`Merge failed: ${err.message}`);
    }
  };

  const options = [
    { label: "Select a conference", value: "", disabled: true },
    ...events.map((e) => ({ label: `${e.name}${e.location ? ` (${e.location})` : ""}`, value: e.id })),
  ];

  return (
    <Card title="Conference Cost" subtitle="Every teammate's spend on one conference, per client and per person.">
      {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
      <div className="max-w-md">
        <Select label="Conference" value={eventId} onChange={setEventId} options={options} />
      </div>
      {summary ? (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-6 text-sm">
            <div><div className="text-xs text-gray-500">Total</div><div className="font-semibold">{usd(summary.total_usd_cents)}</div></div>
            <div><div className="text-xs text-gray-500">Approved</div><div className="font-semibold">{usd(summary.approved_usd_cents)}</div></div>
            <div><div className="text-xs text-gray-500">Pending</div><div className="font-semibold">{usd(summary.pending_usd_cents)}</div></div>
            <div><div className="text-xs text-gray-500">Expenses</div><div className="font-semibold">{summary.expense_count}</div></div>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Table
              columns={[{ key: "who", header: "Client" }, { key: "amount", header: "Cost" }]}
              rows={summary.by_client.map((r) => ({ who: r.company_name, amount: usd(r.amount_usd_cents) }))}
            />
            <Table
              columns={[{ key: "who", header: "Person" }, { key: "amount", header: "Spent" }]}
              rows={summary.by_person.map((r) => ({ who: r.name, amount: usd(r.amount_usd_cents) }))}
            />
          </div>
          <div className="flex items-end gap-2">
            <div className="max-w-md flex-1">
              <Select
                label="Same conference as (merge into)"
                value={mergeInto}
                onChange={setMergeInto}
                options={[{ label: "Select", value: "", disabled: true },
                  ...options.slice(1).filter((o) => o.value !== eventId)]}
              />
            </div>
            <Button variant="secondary" disabled={!mergeInto} onClick={merge}>Merge</Button>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
