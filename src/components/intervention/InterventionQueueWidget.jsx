// S-062/HRMS-0462 -- dashboard "Needs Attention" widget.
import { useEffect, useState } from "react";
import { AlertOctagon } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getInterventionQueueSummary } from "../../services/api/interventionQueue";

export default function InterventionQueueWidget() {
  const [summary, setSummary] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    getInterventionQueueSummary()
      .then((data) => !cancelled && setSummary(data))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!summary || summary.total === 0) return null;

  return (
    <button
      onClick={() => navigate("/recruiter/intervention-queue")}
      className="w-full rounded-2xl border border-red-200 bg-red-50 p-4 text-left shadow-sm transition hover:shadow"
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-red-800">
        <AlertOctagon className="h-4 w-4" />
        Needs Attention
      </div>
      <div className="mt-1 text-sm text-red-700">
        {summary.critical} Critical | {summary.high} High | {summary.medium} Medium
      </div>
    </button>
  );
}
