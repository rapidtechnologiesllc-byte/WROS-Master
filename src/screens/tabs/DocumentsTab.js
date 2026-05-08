import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getCandidateDocuments,
  verifyDocument,
  viewDocument,
} from "../../services/api/documents";

const DOCUMENT_LABELS = {
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement",
  resume: "Resume",
};

export default function DocumentsTab({ candidateId }) {
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("success");
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [previewLoadingId, setPreviewLoadingId] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");

  const [rejectDoc, setRejectDoc] = useState(null);
  const [rejectReason, setRejectReason] = useState("");

  const noticeTimerRef = useRef(null);

  const selectedDoc = useMemo(() => {
    return (
      documents?.find((doc) => doc?.id === selectedDocId) ||
      documents?.[0] ||
      null
    );
  }, [documents, selectedDocId]);

  const showNotice = useCallback((message, type = "success") => {
    setNotice(message);
    setNoticeType(type);

    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);

    noticeTimerRef.current = setTimeout(() => {
      setNotice("");
    }, 4000);
  }, []);

  const clearPreviewUrl = useCallback(() => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl("");
    }
  }, [previewUrl]);

  const closeRejectModal = () => {
    setRejectDoc(null);
    setRejectReason("");
  };

  const fetchDocuments = useCallback(async () => {
    if (!candidateId) return;

    try {
      setLoading(true);
      const data = await getCandidateDocuments(candidateId);
      const rows = Array.isArray(data?.documents) ? data.documents : [];
      setDocuments(rows);
      if (rows.length && !selectedDocId) {
        setSelectedDocId(rows[0]?.id);
      }
    } catch (err) {
      setDocuments([]);
      setSelectedDocId(null);
      showNotice(err.message || "Failed to load documents.", "error");
    } finally {
      setLoading(false);
    }
  }, [candidateId, selectedDocId, showNotice]);

  useEffect(() => {
    fetchDocuments();

    return () => {
      if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    };
  }, [fetchDocuments]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleSelectDocument = async (doc) => {
    if (!doc?.id) {
      showNotice("Document ID is missing.", "error");
      return;
    }

    setSelectedDocId(doc.id);

    try {
      setPreviewLoadingId(doc.id);

      const { blob } = await viewDocument(doc.id);
      const fileUrl = URL.createObjectURL(blob);

      clearPreviewUrl();
      setPreviewUrl(fileUrl);
    } catch (err) {
      setPreviewUrl("");
      showNotice(err.message || "Failed to open document.", "error");
    } finally {
      setPreviewLoadingId(null);
    }
  };

  const handleVerifyDocument = async (doc) => {
    if (!doc?.document_type) {
      showNotice("Document type is missing.", "error");
      return;
    }

    try {
      setActionLoadingId(doc.id);

      await verifyDocument(candidateId, doc.document_type, true);
      await fetchDocuments();

      closeRejectModal();
      showNotice(
        `${getDocumentLabel(doc.document_type)} verified successfully.`,
        "success",
      );
    } catch (err) {
      showNotice(err.message || "Failed to verify document.", "error");
    } finally {
      setActionLoadingId(null);
    }
  };

  const openRejectModal = (doc) => {
    setRejectDoc(doc);
    setRejectReason("");
  };

  const handleRejectDocument = async () => {
    if (!rejectDoc?.document_type) {
      showNotice("Document type is missing.", "error");
      return;
    }

    const trimmedReason = rejectReason.trim();

    if (!trimmedReason) {
      showNotice("Rejection reason is required.", "error");
      return;
    }

    try {
      setActionLoadingId(rejectDoc.id);

      await verifyDocument(
        candidateId,
        rejectDoc.document_type,
        false,
        trimmedReason,
      );

      await fetchDocuments();
      closeRejectModal();

      showNotice(
        `${getDocumentLabel(rejectDoc.document_type)} rejected successfully.`,
        "error",
      );
    } catch (err) {
      showNotice(err.message || "Failed to reject document.", "error");
    } finally {
      setActionLoadingId(null);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border bg-white p-6 text-center text-sm text-gray-500">
        Loading documents...
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        {notice ? (
          <div
            className={`rounded-xl border px-4 py-3 text-sm font-medium ${
              noticeType === "success"
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-red-200 bg-red-50 text-red-700"
            }`}
          >
            {notice}
          </div>
        ) : null}

        {!documents.length ? (
          <div className="rounded-2xl border bg-white p-6 text-center text-sm text-gray-400">
            No documents available
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
            <section className="rounded-2xl border bg-white shadow-sm">
              <div className="border-b px-4 py-4">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                  Uploaded Documents
                </h3>
                <p className="mt-1 text-xs text-gray-400">
                  Select a document to preview and verify.
                </p>
              </div>

              <div className="max-h-[72vh] space-y-2 overflow-y-auto p-3">
                {documents.map((doc) => {
                  const isSelected = selectedDoc?.id === doc?.id;
                  const isVerified = Boolean(doc?.is_verified);
                  const showRejectReason = isVerified && Boolean(doc?.notes);
                  const isPreviewLoading = previewLoadingId === doc?.id;

                  return (
                    <button
                      key={String(doc?.id)}
                      type="button"
                      onClick={() => handleSelectDocument(doc)}
                      className={`w-full rounded-xl border p-3 text-left transition ${
                        isSelected
                          ? "border-gray-900 bg-gray-900 text-white shadow-sm"
                          : "border-gray-200 bg-white hover:bg-gray-50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div
                            className={`truncate text-sm font-semibold ${
                              isSelected ? "text-white" : "text-gray-900"
                            }`}
                          >
                            {getDocumentLabel(doc?.document_type)}
                          </div>

                          <div
                            className={`mt-1 truncate text-xs ${
                              isSelected ? "text-gray-300" : "text-gray-500"
                            }`}
                          >
                            {doc?.original_filename || "Uploaded document"}
                          </div>

                          <div
                            className={`mt-1 text-xs ${
                              isSelected ? "text-gray-300" : "text-gray-400"
                            }`}
                          >
                            Uploaded: {formatDate(doc?.uploaded_at)}
                          </div>
                        </div>

                        <StatusBadge
                          status={
                            isVerified
                              ? "verified"
                              : showRejectReason
                                ? "rejected"
                                : "pending"
                          }
                        />
                      </div>

                      {isPreviewLoading ? (
                        <div
                          className={`mt-2 text-xs ${isSelected ? "text-gray-300" : "text-blue-600"}`}
                        >
                          Opening preview...
                        </div>
                      ) : null}

                      {showRejectReason ? (
                        <div
                          className={`mt-3 rounded-lg px-3 py-2 text-xs ${
                            isSelected
                              ? "bg-white/10 text-red-100"
                              : "border border-red-100 bg-red-50 text-red-700"
                          }`}
                        >
                          <span className="font-semibold">Reason:</span>{" "}
                          {doc?.notes}
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="rounded-2xl border bg-white shadow-sm">
              {selectedDoc ? (
                <DocumentDetailsPanel
                  doc={selectedDoc}
                  previewUrl={previewUrl}
                  isPreviewLoading={previewLoadingId === selectedDoc.id}
                  isActionLoading={actionLoadingId === selectedDoc.id}
                  onPreview={() => handleSelectDocument(selectedDoc)}
                  onVerify={() => handleVerifyDocument(selectedDoc)}
                  onReject={() => openRejectModal(selectedDoc)}
                />
              ) : (
                <div className="flex min-h-[60vh] items-center justify-center text-sm text-gray-400">
                  Select a document to verify
                </div>
              )}
            </section>
          </div>
        )}
      </div>

      {rejectDoc ? (
        <RejectReasonModal
          doc={rejectDoc}
          reason={rejectReason}
          isLoading={actionLoadingId === rejectDoc.id}
          onChangeReason={setRejectReason}
          onCancel={closeRejectModal}
          onSubmit={handleRejectDocument}
        />
      ) : null}
    </>
  );
}

function DocumentDetailsPanel({
  doc,
  previewUrl,
  isPreviewLoading,
  isActionLoading,
  onPreview,
  onVerify,
  onReject,
}) {
  const isVerified = Boolean(doc?.is_verified);
  const isRejected = !isVerified && Boolean(doc?.notes);

  return (
    <div className="flex min-h-[72vh] flex-col">
      <div className="border-b px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold text-gray-900">
                {getDocumentLabel(doc.document_type)}
              </h3>
              <StatusBadge
                status={
                  isVerified ? "verified" : isRejected ? "rejected" : "pending"
                }
              />
            </div>

            <p className="mt-1 text-sm text-gray-500">
              Review the document details and approve or reject it.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onPreview}
              disabled={isPreviewLoading}
              className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isPreviewLoading ? "Opening..." : "Open Preview"}
            </button>

            <button
              type="button"
              onClick={onVerify}
              disabled={isVerified || isActionLoading}
              className="rounded-xl border border-green-100 bg-green-50 px-4 py-2 text-sm font-semibold text-green-700 transition hover:bg-green-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isActionLoading ? "Processing..." : "Approve"}
            </button>

            <button
              type="button"
              onClick={onReject}
              disabled={isActionLoading}
              className="rounded-xl border border-red-100 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 border-b p-5 md:grid-cols-2 xl:grid-cols-4">
        <Info label="File Name" value={doc?.original_filename || "-"} />
        <Info
          label="Document Type"
          value={getDocumentLabel(doc?.document_type)}
        />
        <Info label="Uploaded At" value={formatDate(doc?.uploaded_at)} />
        <Info label="File Size" value={formatFileSize(doc?.file_size)} />
      </div>

      {isRejected ? (
        <div className="mx-5 mt-5 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span className="font-semibold">Rejection reason:</span> {doc.notes}
        </div>
      ) : null}

      <div className="flex-1 p-5">
        {previewUrl ? (
          <iframe
            src={previewUrl}
            title={getDocumentLabel(doc.document_type)}
            className="h-[58vh] w-full rounded-2xl border bg-white"
          />
        ) : (
          <div className="flex h-[58vh] flex-col items-center justify-center rounded-2xl border border-dashed bg-gray-50 text-center">
            <div className="text-sm font-semibold text-gray-700">
              Preview not opened yet
            </div>
            <p className="mt-1 max-w-sm text-sm text-gray-400">
              Click Open Preview to view the document here while verifying the
              details.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function RejectReasonModal({
  doc,
  reason,
  isLoading,
  onChangeReason,
  onCancel,
  onSubmit,
}) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-5 py-4">
          <div className="text-base font-semibold text-gray-900">
            Reject document
          </div>

          <button
            type="button"
            onClick={onCancel}
            className="text-xl leading-none text-gray-400 hover:text-gray-700"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-4">
          <p className="text-sm text-gray-600">
            You are about to reject{" "}
            <span className="font-semibold text-gray-900">
              {getDocumentLabel(doc.document_type)}
            </span>
            . Please provide a reason.
          </p>

          <textarea
            value={reason}
            onChange={(e) => onChangeReason(e.target.value.slice(0, 250))}
            placeholder="Example: Document is blurry or wrong document uploaded"
            rows={4}
            className="mt-3 w-full resize-none rounded-xl border px-3 py-2 text-sm outline-none transition focus:border-red-300 focus:ring-2 focus:ring-red-100"
            autoFocus
          />

          <div className="mt-1 text-right text-xs text-gray-400">
            {reason.length} / 250
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t px-5 py-4">
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="rounded-lg border px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={onSubmit}
            disabled={isLoading || !reason.trim()}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? "Rejecting..." : "Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        {label}
      </div>
      <div className="mt-1 break-words text-sm font-medium text-gray-900">
        {value || "-"}
      </div>
    </div>
  );
}
function getDocumentLabel(type) {
  return DOCUMENT_LABELS[type] || formatDocumentType(type) || "Document";
}
function formatDocumentType(type) {
  if (!type) return "";

  return String(type)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
function StatusBadge({ status }) {
  const normalizedStatus = String(status || "").toLowerCase();

  let styles = "bg-gray-100 text-gray-600 border-gray-200";

  if (normalizedStatus === "verified") {
    styles = "bg-green-100 text-green-700 border-green-200";
  } else if (normalizedStatus === "pending") {
    styles = "bg-yellow-100 text-yellow-700 border-yellow-200";
  } else if (normalizedStatus === "rejected") {
    styles = "bg-red-100 text-red-700 border-red-200";
  }

  return (
    <span
      className={`rounded-full border px-3 py-1 text-xs font-semibold ${styles}`}
    >
      {formatDocumentType(normalizedStatus) || "Unknown"}
    </span>
  );
}

function formatDate(date) {
  if (!date) return "-";

  const parsedDate = new Date(date);
  if (Number.isNaN(parsedDate.getTime())) return "-";

  return parsedDate.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatFileSize(size) {
  const bytes = Number(size);
  if (!Number.isFinite(bytes) || bytes <= 0) return "-";

  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
