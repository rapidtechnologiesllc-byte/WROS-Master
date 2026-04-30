import { useCallback, useEffect, useRef, useState } from "react";
import {
  getCandidateDocuments,
  verifyDocument,
  viewDocument
} from "../../services/api/documents";

const DOCUMENT_LABELS = {
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement",
  resume: "Resume"
};

export default function DocumentsTab({ candidateId }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("success");
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [previewLoadingId, setPreviewLoadingId] = useState(null);

  const [previewDoc, setPreviewDoc] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");

  const [rejectDoc, setRejectDoc] = useState(null);
  const [rejectReason, setRejectReason] = useState("");

  const noticeTimerRef = useRef(null);

  const showNotice = useCallback((message, type = "success") => {
    setNotice(message);
    setNoticeType(type);

    if (noticeTimerRef.current) {
      clearTimeout(noticeTimerRef.current);
    }

    noticeTimerRef.current = setTimeout(() => {
      setNotice("");
    }, 4000);
  }, []);

  const closePreview = useCallback(() => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setPreviewDoc(null);
    setPreviewUrl("");
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
      setDocuments(Array.isArray(data?.documents) ? data.documents : []);
    } catch (err) {
      setDocuments([]);
      showNotice(err.message || "Failed to load documents.", "error");
    } finally {
      setLoading(false);
    }
  }, [candidateId, showNotice]);

  useEffect(() => {
    fetchDocuments();

    return () => {
      if (noticeTimerRef.current) {
        clearTimeout(noticeTimerRef.current);
      }
    };
  }, [fetchDocuments]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handlePreviewDocument = async (doc) => {
    if (!doc?.id) {
      showNotice("Document ID is missing.", "error");
      return;
    }

    try {
      setPreviewLoadingId(doc.id);

      const { blob } = await viewDocument(doc.id);
      const fileUrl = URL.createObjectURL(blob);

      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }

      setPreviewDoc(doc);
      setPreviewUrl(fileUrl);
    } catch (err) {
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

      closePreview();
      closeRejectModal();

      showNotice(`${getDocumentLabel(doc.document_type)} verified successfully.`, "success");
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
        trimmedReason
      );

      await fetchDocuments();

      closePreview();
      closeRejectModal();

      showNotice(`${getDocumentLabel(rejectDoc.document_type)} rejected successfully.`, "success");
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
      <div className="grid gap-4">
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
          documents.map((doc) => {
            const isVerified = Boolean(doc.is_verified);
            const isPreviewLoading = previewLoadingId === doc.id;
            const showRejectReason = !isVerified && Boolean(doc.notes);

            return (
              <div
                key={doc.id}
                className="flex flex-col gap-4 rounded-2xl border bg-white p-4 shadow-sm transition hover:shadow-md md:flex-row md:items-center md:justify-between"
              >
                <div className="min-w-0">
                  <div className="font-medium text-gray-900">
                    {getDocumentLabel(doc.document_type)}
                  </div>

                  <div className="mt-1 text-xs text-gray-500">
                    {doc.original_filename || "Uploaded document"} • Uploaded:{" "}
                    {formatDate(doc.uploaded_at)}
                  </div>

                  {showRejectReason ? (
                    <div className="mt-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-700">
                      <span className="font-semibold">Rejection reason:</span>{" "}
                      {doc.notes}
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <StatusBadge status={isVerified ? "verified" : "pending"} />

                  <button
                    type="button"
                    onClick={() => handlePreviewDocument(doc)}
                    disabled={!doc.id || isPreviewLoading}
                    className="rounded-lg border border-blue-100 px-3 py-1.5 text-xs font-semibold text-blue-600 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isPreviewLoading ? "Opening..." : "Preview"}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {previewDoc && previewUrl ? (
        <DocumentPreviewModal
          doc={previewDoc}
          previewUrl={previewUrl}
          isActionLoading={actionLoadingId === previewDoc.id}
          onClose={closePreview}
          onVerify={() => handleVerifyDocument(previewDoc)}
          onReject={() => openRejectModal(previewDoc)}
        />
      ) : null}

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

function DocumentPreviewModal({
  doc,
  previewUrl,
  isActionLoading,
  onClose,
  onVerify,
  onReject
}) {
  const isVerified = Boolean(doc.is_verified);
  const showRejectReason = !isVerified && Boolean(doc.notes);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-5xl flex-col rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
          <div>
            <div className="text-base font-semibold text-gray-900">
              {getDocumentLabel(doc.document_type)}
            </div>
            <div className="text-xs text-gray-500">
              {doc.original_filename || "Uploaded document"} • Uploaded:{" "}
              {formatDate(doc.uploaded_at)}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={isVerified ? "verified" : "pending"} />

            <button
              type="button"
              onClick={onVerify}
              disabled={isVerified || isActionLoading}
              className="rounded-lg border border-green-100 bg-green-50 px-3 py-1.5 text-xs font-semibold text-green-700 transition hover:bg-green-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isActionLoading ? "Processing..." : "Verify"}
            </button>

            <button
              type="button"
              onClick={onReject}
              disabled={isActionLoading}
              className="rounded-lg border border-red-100 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Reject
            </button>

            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border px-3 py-1.5 text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
            >
              Close
            </button>
          </div>
        </div>

        {showRejectReason ? (
          <div className="border-b bg-red-50 px-5 py-2 text-xs font-medium text-red-600">
            Rejection reason: {doc.notes}
          </div>
        ) : null}

        <div className="min-h-[60vh] flex-1 bg-gray-50 p-4">
          <iframe
            src={previewUrl}
            title={getDocumentLabel(doc.document_type)}
            className="h-[70vh] w-full rounded-xl border bg-white"
          />
        </div>
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
  onSubmit
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

  let styles = "bg-gray-100 text-gray-600";

  if (normalizedStatus === "verified") {
    styles = "bg-green-100 text-green-700";
  } else if (normalizedStatus === "pending") {
    styles = "bg-yellow-100 text-yellow-700";
  } else if (normalizedStatus === "rejected") {
    styles = "bg-red-100 text-red-700";
  }

  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${styles}`}>
      {formatDocumentType(normalizedStatus) || "Unknown"}
    </span>
  );
}

function formatDate(date) {
  if (!date) return "-";

  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return "-";
  }

  return parsedDate.toLocaleDateString();
}