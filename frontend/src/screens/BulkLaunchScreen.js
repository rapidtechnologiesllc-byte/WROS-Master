// S-074/HRMS-0474 -- Bulk Candidate Engagement Launch.
import { useEffect, useRef, useState } from "react";
import { AlertCircle, X } from "lucide-react";
import { bulkEngage, bulkImportCsv, getBulkJobStatus, getActiveBulkJobs, getImportHistory, cancelBulkImportJob } from "../services/api/bulkEngagement";

export default function BulkLaunchScreen() {
  const [uploadType, setUploadType] = useState("candidate");  // Type selector
  const [file, setFile] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importHistory, setImportHistory] = useState([]);  // NEW: Store import history
  const [job, setJob] = useState(null);
  const [launching, setLaunching] = useState(false);
  const [actionError, setActionError] = useState(null);
  const pollRef = useRef(null);
  const fileInputRef = useRef(null);

  const uploadTypeOptions = [
    { value: "candidate", label: "Candidates", icon: "👤", description: "Import candidate records" },
    { value: "job", label: "Jobs", icon: "💼", description: "Import job openings" },
    { value: "employee", label: "Employees", icon: "👨‍💼", description: "Import employee records" },
    { value: "bank_statement", label: "Bank Statements", icon: "🏦", description: "Import bank statements" },
  ];

  // NEW: Load ongoing imports on component mount and auto-refresh
  useEffect(() => {
    const loadOngoingImports = async () => {
      try {
        const jobs = await getImportHistory();
        setImportHistory(jobs || []);
      } catch (err) {
        console.error("Failed to load import history:", err);
      }
    };

    // Load immediately
    loadOngoingImports();

    // Also refresh import history every 3 seconds to show updated counts in history
    const historyRefreshInterval = setInterval(loadOngoingImports, 3000);

    return () => {
      clearInterval(historyRefreshInterval);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleFileSelect = (selected) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setActionError("File must be a .csv file.");
      return;
    }
    setFile(selected);
    setImportResult(null);
    setActionError(null);
  };

  const handleCancelImport = async (jobId) => {
    try {
      const result = await cancelBulkImportJob(jobId);
      setActionError(null);

      // Refresh import history (including completed/cancelled jobs)
      const jobs = await getImportHistory();
      setImportHistory(jobs || []);
    } catch (err) {
      console.error("Error cancelling import:", err);
      setActionError(err?.message || "Failed to cancel import");
    }
  };

  const handleImport = async () => {
    if (!file) return;

    // Only candidate import is currently implemented
    if (uploadType !== "candidate") {
      setActionError(`${uploadTypeOptions.find(o => o.value === uploadType)?.label} bulk import coming soon!`);
      return;
    }

    setImporting(true);
    try {
      // The import runs in the request: the response is the final result
      // (imported / duplicates / errors); history below refreshes on its own.
      setImportResult(await bulkImportCsv(file));
      setActionError(null);
    } catch (err) {
      setActionError(err?.message || "CSV cannot exceed 100K rows, or is missing required columns.");
    } finally {
      setImporting(false);
    }
  };

  const pollJob = (jobId) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await getBulkJobStatus(jobId);
        setJob(status);
        if (status.status === "COMPLETED") {
          clearInterval(pollRef.current);
        }
      } catch {
        // transient poll failure -- try again next tick
      }
    }, 5000);
  };

  const handleLaunch = async () => {
    if (!importResult?.candidate_ids?.length) return;
    setLaunching(true);
    try {
      const launch = await bulkEngage(importResult.candidate_ids);
      setJob({ bulk_job_id: launch.bulk_job_id, status: "QUEUED", total_count: launch.total_candidates, success_count: 0, failed_count: 0, skipped_count: 0, errors: [] });
      setActionError(null);
      pollJob(launch.bulk_job_id);
    } catch (err) {
      setActionError(err?.message || "Failed to launch bulk engagement.");
    } finally {
      setLaunching(false);
    }
  };

  const processedCount = job ? job.success_count + job.failed_count + job.skipped_count : 0;

  return (
    <div className="space-y-5">
      {actionError && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-rose-700 hover:text-rose-900">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {/* Step 0: Select Upload Type */}
      <div className="rounded-2xl border bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-gray-900">0. Select Upload Type</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {uploadTypeOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => { setUploadType(option.value); setFile(null); setImportResult(null); }}
              className={`rounded-lg border-2 p-4 text-center transition-all ${
                uploadType === option.value
                  ? "border-bx-navy bg-blue-50"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <div className="text-2xl">{option.icon}</div>
              <div className="mt-2 text-xs font-semibold text-gray-900">{option.label}</div>
              <div className="mt-1 text-xs text-gray-600">{option.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Step 1: Import */}
      <div className="rounded-2xl border bg-white p-5 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">1. Import {uploadTypeOptions.find(o => o.value === uploadType)?.label}</h3>
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFileSelect(e.dataTransfer.files?.[0]);
          }}
          className="cursor-pointer rounded-xl border-2 border-dashed border-gray-300 p-8 text-center text-sm text-gray-500 hover:border-blue-400"
        >
          {file ? file.name : "Drop CSV here or click to upload"}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => handleFileSelect(e.target.files?.[0])}
          />
        </div>
        <div className="mt-3 flex justify-end">
          <button
            onClick={handleImport}
            disabled={!file || importing}
            className="rounded-lg bg-bx-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {importing ? "Importing..." : "Import CSV"}
          </button>
        </div>

        {importResult && (
          <div className="mt-4 space-y-2">
            <div className="text-sm text-gray-700">
              Imported: <span className="font-semibold">{importResult.imported}</span> · Duplicates skipped: <span className="font-semibold">{importResult.skipped_duplicates}</span> · Errors: <span className="font-semibold">{importResult.errors.length}</span>
            </div>
            {importResult.errors.length > 0 && (
              <ul className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                {importResult.errors.map((e, i) => (
                  <li key={i}>Row {e.row}: {e.reason}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {importResult?.candidate_ids?.length > 0 && (
        <div className="rounded-2xl border bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-gray-900">2. Launch</h3>
          {!job ? (
            <button
              onClick={handleLaunch}
              disabled={launching}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {launching ? "Launching..." : `Launch Thunder for ${importResult.candidate_ids.length} new candidates`}
            </button>
          ) : (
            <div className="space-y-3">
              <div className="h-3 w-full overflow-hidden rounded-full bg-gray-100">
                <div className="h-full bg-blue-500 transition-all" style={{ width: `${(processedCount / job.total_count) * 100}%` }} />
              </div>
              <div className="text-sm text-gray-700">
                {job.status === "COMPLETED" ? "Completed" : "Engaging candidates"}: {processedCount} of {job.total_count}
                {" — "}Success: {job.success_count} · Failed: {job.failed_count} · Skipped: {job.skipped_count}
              </div>
              {job.status === "COMPLETED" && job.errors.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-700">Failed candidates</h4>
                  <ul className="mt-1 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                    {job.errors.map((e, i) => (
                      <li key={i}>{e.candidate_id}: {e.reason}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* NEW: Import History */}
      {importHistory.length > 0 && (
        <div className="rounded-2xl border bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-gray-900">Import History</h3>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {importHistory.map((historyJob) => (
              <div key={historyJob.id} className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="font-semibold text-gray-900">
                      {historyJob.imported} / {historyJob.total_rows} imported
                      <span className={`ml-2 inline-block px-2 py-1 rounded ${
                        historyJob.status === "PROCESSING" ? "bg-blue-100 text-blue-700" :
                        historyJob.status === "QUEUED" ? "bg-yellow-100 text-yellow-700" :
                        historyJob.status === "COMPLETED" ? "bg-green-100 text-green-700" :
                        historyJob.status === "CANCELLED" ? "bg-gray-100 text-gray-700" :
                        "bg-red-100 text-red-700"
                      }`}>
                        {historyJob.status}
                      </span>
                    </div>
                    <div className="mt-1 text-gray-600">
                      {historyJob.status === "PROCESSING" ? "In Progress..." :
                       historyJob.status === "QUEUED" ? "Waiting to start..." :
                       historyJob.created_at ? new Date(historyJob.created_at).toLocaleString() : ""}
                    </div>
                  </div>
                  <div className="ml-4 flex flex-col items-end gap-2">
                    <div className="text-right text-gray-600">
                      <div>✓ {historyJob.imported}</div>
                      <div>⊗ {historyJob.errors}</div>
                    </div>
                    {(historyJob.status === "PROCESSING" || historyJob.status === "QUEUED") && (
                      <button
                        onClick={() => handleCancelImport(historyJob.id)}
                        className="rounded px-2 py-1 bg-red-100 text-red-700 hover:bg-red-200 font-semibold"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>

                {/* Show error reasons for FAILED jobs */}
                {historyJob.status === "FAILED" && historyJob.error_reasons?.length > 0 && (
                  <div className="mt-2 text-xs border-t pt-2">
                    <div className="font-semibold text-red-700 mb-1">Fix these issues in your CSV:</div>
                    {historyJob.error_reasons.map((err, i) => (
                      <div key={i} className="text-red-600 mb-1">
                        • {err.reason}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
