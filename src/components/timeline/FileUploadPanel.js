// S-216/HRMS-0118 -- reusable file attachment panel. Any entity detail
// screen drops this in with just an entityType/entityId; shows real
// scan status (Scanning/Clean/Quarantined) before ever offering a link,
// per BR-0118-02 -- no download link is rendered until scan_status is
// CLEAN.
import { useEffect, useRef, useState } from "react";
import { toast } from "react-toastify";
import { FileText, Upload } from "lucide-react";
import { getFileAccessUrl, listFiles, uploadFile } from "../../services/api/activityTimeline";

const SCAN_LABELS = {
  PENDING: { label: "Scanning...", className: "text-amber-600" },
  CLEAN: { label: "Clean", className: "text-emerald-600" },
  QUARANTINED: { label: "Quarantined", className: "text-rose-600" },
};

function FileRow({ file }) {
  const [accessUrl, setAccessUrl] = useState(null);
  const status = SCAN_LABELS[file.scan_status] || SCAN_LABELS.PENDING;

  useEffect(() => {
    if (file.scan_status !== "CLEAN") return;
    getFileAccessUrl(file.id).then((res) => setAccessUrl(res.access_url));
  }, [file.id, file.scan_status]);

  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-100 py-2 last:border-b-0">
      <div className="flex min-w-0 items-center gap-2">
        <FileText className="h-4 w-4 shrink-0 text-gray-400" />
        <div className="min-w-0">
          <div className="truncate text-xs font-medium text-gray-800">{file.original_filename}</div>
          <div className="text-[11px] text-gray-400">{file.file_category}</div>
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className={`text-xs font-semibold ${status.className}`}>{status.label}</div>
        {accessUrl ? (
          <a href={accessUrl} target="_blank" rel="noreferrer" className="text-[11px] text-bx-orange hover:underline">
            Open
          </a>
        ) : null}
      </div>
    </div>
  );
}

export default function FileUploadPanel({ entityType, entityId, fileCategory = "GENERIC" }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  const load = () => {
    if (!entityType || !entityId) return;
    setLoading(true);
    listFiles(entityType, entityId)
      .then(setFiles)
      .finally(() => setLoading(false));
  };

  useEffect(load, [entityType, entityId]);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadFile(entityType, entityId, file, fileCategory);
      toast.success("File uploaded -- scanning before it becomes available.");
      load();
    } catch (err) {
      toast.error(err.message || "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-700">Attachments</span>
        <label className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-bx-orange px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-bx-orange-hover">
          <Upload className="h-3.5 w-3.5" />
          {uploading ? "Uploading..." : "Upload"}
          <input ref={inputRef} type="file" className="hidden" onChange={handleFileChange} disabled={uploading} />
        </label>
      </div>
      {loading ? (
        <div className="py-4 text-center text-xs text-gray-400">Loading files...</div>
      ) : files.length === 0 ? (
        <div className="py-4 text-center text-xs text-gray-400">No files attached yet.</div>
      ) : (
        files.map((f) => <FileRow key={f.id} file={f} />)
      )}
    </div>
  );
}
