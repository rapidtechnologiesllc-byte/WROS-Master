// S-215/HRMS-0117 -- Error Logging Framework. Admin/Director-only
// read-only viewer over the real error_log table (additive to the
// existing file-based structured logger).
import { Fragment, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Card, Select } from "../components/ui";
import { getErrorLog } from "../services/api/errorLog";

const SEVERITY_STYLES = {
  CRITICAL: "bg-red-100 text-red-800 border-red-300",
  ERROR: "bg-amber-100 text-amber-800 border-amber-300",
  WARN: "bg-yellow-50 text-yellow-700 border-yellow-200",
  INFO: "bg-gray-100 text-gray-600 border-gray-200",
};
const SEVERITY_OPTIONS = [{ value: "", label: "All severities" }, "CRITICAL", "ERROR", "WARN", "INFO"];

export default function ErrorLogScreen() {
  const [errors, setErrors] = useState([]);
  const [severity, setSeverity] = useState("");
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  const load = async (sev) => {
    setLoading(true);
    try {
      const res = await getErrorLog({ severity: sev || undefined });
      setErrors(res.errors || []);
    } catch {
      toast.error("Could not load the error log.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(severity);
  }, [severity]);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div className="w-48">
          <Select value={severity} onChange={setSeverity} options={SEVERITY_OPTIONS} />
        </div>
      </div>

      <Card bodyClassName="p-0">
        {loading ? (
          <p className="p-4 text-sm text-gray-500">Loading...</p>
        ) : errors.length === 0 ? (
          <p className="p-4 text-sm text-gray-400">No errors logged.</p>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-bx-light text-xs uppercase text-gray-500">
              <tr>
                <th className="py-2 px-3">Time</th>
                <th className="py-2 px-3">Severity</th>
                <th className="py-2 px-3">Type</th>
                <th className="py-2 px-3">Message</th>
                <th className="py-2 px-3">Integration</th>
              </tr>
            </thead>
            <tbody>
              {errors.map((e) => (
                <Fragment key={e.id}>
                  <tr
                    className="border-t border-bx-border cursor-pointer hover:bg-bx-light"
                    onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                  >
                    <td className="py-2 px-3 text-xs text-gray-500 whitespace-nowrap">{e.created_at ? new Date(e.created_at).toLocaleString() : "--"}</td>
                    <td className="py-2 px-3">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-bx border ${SEVERITY_STYLES[e.severity] || ""}`}>{e.severity}</span>
                    </td>
                    <td className="py-2 px-3 text-sm text-bx-slate">{e.error_type}</td>
                    <td className="py-2 px-3 text-sm text-gray-600 max-w-xs truncate">{e.message}</td>
                    <td className="py-2 px-3 text-xs text-gray-500">{e.integration_name || "--"}</td>
                  </tr>
                  {expandedId === e.id && e.stack_trace && (
                    <tr className="bg-bx-light">
                      <td colSpan={5} className="px-3 py-2">
                        <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{e.stack_trace}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
