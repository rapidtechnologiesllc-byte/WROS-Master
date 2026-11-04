// The lowest bill rate for an employee: their hourly cost (pay + the location's statutory and overhead
// rate, or a sub-vendor's rate) grossed up by each line's margin floor. The server works it out
// (margin_guard_service.minimum_bill_rate); what it cannot work out it names, never guesses.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getEmployeeMinimumBillRate } from "../services/api/employees";
import { lineTypeLabel } from "../utils/lineType";

const usd = (cents) => `$${(cents / 100).toFixed(2)}`;

export default function MinimumBillRate({ result, billRateCents }) {
  if (!result) return null;
  const minimums = result.lines.map((l) => l.minimum_usd_cents).filter((v) => v != null);
  const notSet = [...result.missing, ...(result.missing_margin_lines || []).map((line) => `margin floor for ${lineTypeLabel(line)}`)];
  const below = billRateCents != null && minimums.length > 0 && billRateCents < Math.min(...minimums);
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">
      <div className="font-semibold text-gray-900">Minimum bill rate{result.country ? ` (${result.country})` : ""}</div>
      {result.pay_hourly_usd_cents != null ? (
        <div className="mt-1">
          Pay {usd(result.pay_hourly_usd_cents)} / hr
          {result.statutory_pct != null ? ` + ${result.statutory_pct}% statutory + ${result.overhead_pct}% overhead` : ""}
          {result.break_even_usd_cents != null ? ` = ${usd(result.break_even_usd_cents)} / hr break-even` : ""}
        </div>
      ) : null}
      {result.lines.filter((l) => l.minimum_usd_cents != null).map((l) => (
        <div key={l.delivery_engine} className="mt-1">
          {lineTypeLabel(l.delivery_engine)}: <span className="font-semibold text-gray-900">{usd(l.minimum_usd_cents)} / hr</span>
          {` for the ${l.min_margin_pct}% margin floor (below ${usd(l.hard_floor_usd_cents)} a Partner must approve)`}
        </div>
      ))}
      {notSet.length ? (
        <div className="mt-1 text-amber-800">
          Not set yet: {notSet.join(", ")}. Statutory and overhead are set on{" "}
          <Link className="underline" to="/finance-operations">Finance Operations</Link>, margin floors on{" "}
          <Link className="underline" to="/pnl?view=rate-card">P&amp;L &gt; Rate Card</Link>.
        </div>
      ) : null}
      {below ? <div className="mt-1 font-medium text-rose-700">This bill rate is below the minimum: placing them at it will need approval.</div> : null}
    </div>
  );
}

export function EmployeeMinimumBillRate({ employeeId, current }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    getEmployeeMinimumBillRate(employeeId)
      .then((data) => { if (live) setResult(data); })
      .catch((err) => { if (live) setError(`Could not work out the minimum bill rate: ${err.message}`); });
    return () => { live = false; };
  }, [employeeId]);
  if (error) return <div className="text-xs text-rose-700">{error}</div>;
  return <MinimumBillRate result={result} billRateCents={current ?? null} />;
}
