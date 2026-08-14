// S-074/HRMS-0474 -- Bulk Candidate Engagement Launch.
import { useEffect, useRef, useState } from "react";
import { toast } from "react-toastify";
import { bulkEngage, bulkImportCsv, getBulkJobStatus } from "../services/api/bulkEngagement";

export default function BulkLaunchScreen() {
  const [uploadType, setUploadType] = useState("candidate");  // Type selector
  const [file, setFile] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const [job, setJob] = useState(null);
  const [launching, setLaunching] = useState(false);
  const pollRef = useRef(null);
  const fileInputRef = useRef(null);

  const uploadTypeOptions = [
    { value: "candidate", label: "Candidates", icon: "👤", description: "Import candidate records" },
    { value: "job", label: "Jobs", icon: "💼", description: "Import job openings" },
    { value: "employee", label: "Employees", icon: "👨‍💼", description: "Import employee records" },
    { value: "bank_statement", label: "Bank Statements", icon: "🏦", description: "Import bank statements" },
  ];

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleFileSelect = (selected) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      toast.error("File must be a .csv file.");
      return;
    }
    setFile(selected);
    setImportResult(null);
  };

  const handleImport = async () => {
    if (!file) return;

    // Only candidate import is currently implemented
    if (uploadType !== "candidate") {
      toast.error(`${uploadTypeOptions.find(o => o.value === uploadType)?.label} bulk import coming soon!`);
      return;
    }

    setImporting(true);
    try {
      const result = await bulkImportCsv(file);
      setImportResult(result);
      const typeLabel = uploadTypeOptions.find(o => o.value === uploadType)?.label || "Records";
      toast.success(`${result.message || `Imported ${result.imported} ${typeLabel.toLowerCase()}. ${result.skipped_duplicates} duplicate(s) skipped.`}`);
    } catch (err) {
      toast.error(err?.message || "CSV cannot exceed 100K rows, or is missing required columns.");
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
      pollJob(launch.bulk_job_id);
    } catch (err) {
      toast.error(err?.message || "Failed to launch bulk engagement.");
    } finally {
      setLaunching(false);
    }
  };

  const processedCount = job ? job.success_count + job.failed_count + job.skipped_count : 0;

  return (
    <div className="space-y-5">
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
    </div>
  );
}
