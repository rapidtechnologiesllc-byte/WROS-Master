// One shared record per conference (CEO 2026-10-31): "when we give 1 conference name it has to
// also make sure all team members use same or similar details to have the record built into 1
// event". Type to find the event your team already logged ("Namic-2026" finds "NAMIC 2026");
// add it only when it is not there. A name close to an existing event is refused by the server
// with the matches -- pick one, or confirm it really is a different event.
import { useEffect, useState } from "react";
import { Button, Input } from "./ui";
import { createExpenseEvent, searchExpenseEvents } from "../services/api/expenses";

const describe = (e) =>
  [e.name, e.location, e.start_date ? `from ${e.start_date}` : null].filter(Boolean).join(" · ");

export default function ExpenseEventPicker({ value, onChange }) {
  const [query, setQuery] = useState(value?.name || "");
  const [matches, setMatches] = useState([]);
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [details, setDetails] = useState({ year: "", startDate: "", endDate: "", location: "" });
  const [nearMatches, setNearMatches] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (value || !open) return undefined;
    const handle = setTimeout(async () => {
      try {
        const data = await searchExpenseEvents(query.trim());
        setMatches(data?.events || []);
        setError("");
      } catch (err) {
        setError(`Couldn't load conferences: ${err.message}`);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [query, open, value]);

  const pick = (event) => {
    onChange(event);
    setQuery(event.name);
    setOpen(false);
    setAdding(false);
    setNearMatches([]);
    setError("");
  };

  const add = async (confirmNew = false) => {
    try {
      const event = await createExpenseEvent({
        name: query.trim(),
        year: details.year ? Number(details.year) : null,
        start_date: details.startDate || null,
        end_date: details.endDate || null,
        location: details.location || null,
        confirm_new: confirmNew,
      });
      pick(event);
    } catch (err) {
      if (err.status === 409 && err.detail?.matches) {
        setNearMatches(err.detail.matches);
        setError(err.detail.message);
        return;
      }
      setError(err.message || "Couldn't add the conference.");
    }
  };

  if (value) {
    return (
      <div>
        <div className="mb-1 text-xs font-semibold text-gray-700">Conference</div>
        <div className="flex items-center justify-between rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm">
          <span>{describe(value)}</span>
          <button type="button" className="text-xs font-semibold text-bx-orange" onClick={() => onChange(null)}>
            Change
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <Input
        label="Conference"
        value={query}
        onChange={(v) => {
          setQuery(v);
          setOpen(true);
          setNearMatches([]);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search your team's conferences, e.g. NAMIC 2026"
      />
      {error ? <div className="mt-1 text-xs text-rose-700">{error}</div> : null}
      {nearMatches.length ? (
        <div className="mt-1 rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs">
          {nearMatches.map((m) => (
            <button key={m.id} type="button" className="block font-semibold text-bx-orange" onClick={() => pick(m)}>
              Use {describe(m)}
            </button>
          ))}
          <button type="button" className="mt-1 block text-gray-700 underline" onClick={() => add(true)}>
            No -- "{query.trim()}" is a different event
          </button>
        </div>
      ) : null}
      {open && !adding && !nearMatches.length ? (
        <div className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-gray-200 bg-white text-sm shadow">
          {matches.map((m) => (
            <button key={m.id} type="button" className="block w-full px-3 py-2 text-left hover:bg-gray-50" onClick={() => pick(m)}>
              {describe(m)}
            </button>
          ))}
          {query.trim() ? (
            <button
              type="button"
              className="block w-full px-3 py-2 text-left text-xs font-semibold text-bx-orange hover:bg-gray-50"
              onClick={() => setAdding(true)}
            >
              + Add "{query.trim()}" as a new conference
            </button>
          ) : null}
        </div>
      ) : null}
      {adding && !nearMatches.length ? (
        <div className="mt-2 grid grid-cols-2 gap-2 rounded-lg border border-gray-200 bg-white p-2">
          <Input label="Year (if not in the name)" value={details.year} onChange={(v) => setDetails((d) => ({ ...d, year: v }))} placeholder="2026" />
          <Input label="Location" value={details.location} onChange={(v) => setDetails((d) => ({ ...d, location: v }))} placeholder="Austin, TX" />
          <Input label="Starts" type="date" value={details.startDate} onChange={(v) => setDetails((d) => ({ ...d, startDate: v }))} />
          <Input label="Ends" type="date" value={details.endDate} onChange={(v) => setDetails((d) => ({ ...d, endDate: v }))} />
          <div className="col-span-2 flex gap-2">
            <Button onClick={() => add(false)}>Add conference</Button>
            <Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
