// DEFECT-9: Revenue Leakage display enhancements
// Shows last scan time, rescan button, severity badges, explanations

import { RefreshCw, AlertTriangle, AlertCircle, Info } from "lucide-react";
import { Button } from "./ui";

export function RevenueLeakageScanStatusHeader({ lastScannedAt, frequency, onRescan, loading }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return "Never";
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  return (
    <div className="rounded-lg border bg-blue-50 p-4 mb-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">Leakage Scan Status</h3>
          <div className="text-sm text-gray-600 mt-1">
            Last Scanned: <span className="font-medium">{formatDate(lastScannedAt)}</span>
          </div>
          <div className="text-sm text-gray-600">
            Frequency: <span className="font-medium">{frequency || "Daily at 2 AM UTC"}</span>
          </div>
        </div>
        <Button variant="primary" onClick={onRescan} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Scanning..." : "Rescan Now"}
        </Button>
      </div>
    </div>
  );
}

export function LeakageSeverityBadge({ type, amount }) {
  // type = "CRITICAL" | "WARNING" | "INFO"
  const styles = {
    CRITICAL: "bg-red-100 text-red-800 border-red-300",
    WARNING: "bg-yellow-100 text-yellow-800 border-yellow-300",
    INFO: "bg-blue-100 text-blue-800 border-blue-300",
  };

  const icons = {
    CRITICAL: <AlertTriangle className="h-4 w-4" />,
    WARNING: <AlertCircle className="h-4 w-4" />,
    INFO: <Info className="h-4 w-4" />,
  };

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded border ${styles[type] || styles.INFO}`}>
      {icons[type]}
      <span className="text-xs font-semibold">{type}</span>
      {amount && <span className="text-xs">${(amount / 100).toLocaleString()}</span>}
    </div>
  );
}

export const LEAKAGE_TYPE_EXPLANATIONS = {
  UUID_MISMATCH: "Project UUID on invoice doesn't match Work Order project",
  AMOUNT_VARIANCE: "Billed amount differs from Work Order rate",
  UNBILLED_HOURS: "Timesheet hours exist but no corresponding invoice",
  RATE_VARIANCE: "Employee pay rate changed mid-engagement without invoice adjustment",
  MISSING_WORKORDER: "Invoice issued without corresponding Work Order",
  OVERBILLED: "Invoice amount exceeds agreed-upon project budget",
};

export function LeakageExplanationTooltip({ type }) {
  const explanation = LEAKAGE_TYPE_EXPLANATIONS[type];
  if (!explanation) return null;

  return (
    <div className="text-xs text-gray-600 mt-2 p-2 bg-gray-50 rounded border border-gray-200">
      <strong>{type}:</strong> {explanation}
    </div>
  );
}
