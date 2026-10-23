// Margin guard UI (rate card, CEO 2026-10-23): the live margin line under an allocation form and
// the hook that asks the server for it. The server decides (margin_guard_service); this only shows
// the verdict: margin %, the floor, and who must approve when it is below the floor.
import { useEffect, useState } from "react";
import cx from "../utils/cx";
import { previewMargin } from "../services/api/allocations";

const PREVIEW_DELAY_MS = 400;

export function useMarginPreview(request, enabled) {
  const [margin, setMargin] = useState(null);
  const [error, setError] = useState("");
  const key = JSON.stringify(request);

  useEffect(() => {
    if (!enabled) {
      setMargin(null);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      previewMargin(JSON.parse(key))
        .then((data) => {
          if (!cancelled) {
            setMargin(data);
            setError("");
          }
        })
        .catch((err) => {
          if (!cancelled) {
            setMargin(null);
            setError(`Could not check the margin: ${err.message}`);
          }
        });
    }, PREVIEW_DELAY_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [key, enabled]);

  return { margin, error };
}

const TONE = {
  OK: "border-emerald-200 bg-emerald-50 text-emerald-800",
  NOT_BILLABLE: "border-gray-200 bg-gray-50 text-gray-700",
  NO_FLOOR_CONFIGURED: "border-amber-200 bg-amber-50 text-amber-800",
  BELOW_MIN: "border-amber-300 bg-amber-50 text-amber-900",
  NO_COST_DATA: "border-amber-300 bg-amber-50 text-amber-900",
  NO_BILL_RATE: "border-amber-300 bg-amber-50 text-amber-900",
  BELOW_HARD_FLOOR: "border-rose-200 bg-rose-50 text-rose-800",
};

export function MarginLine({ margin, error }) {
  if (error) return <div className="mt-2 text-xs text-rose-700">{error}</div>;
  if (!margin) return null;
  return (
    <div className={cx("mt-3 rounded-lg border px-3 py-2 text-xs", TONE[margin.margin_check] || TONE.OK)}>
      <span className="font-semibold">
        Margin {margin.margin_pct != null ? `${margin.margin_pct.toFixed(1)}%` : "unknown"}
      </span>
      {margin.loaded_hourly_cost_usd_cents != null && (
        <span> · loaded cost ${(margin.loaded_hourly_cost_usd_cents / 100).toFixed(2)}/h</span>
      )}
      <div>{margin.message}</div>
      {margin.approval_level && (
        <div className="font-semibold">Saving sends it for approval; no timesheet or invoice until it is approved.</div>
      )}
    </div>
  );
}

export const marginLabel = (pct) => (pct == null ? "—" : `${Number(pct).toFixed(1)}%`);
