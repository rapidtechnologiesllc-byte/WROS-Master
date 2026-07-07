import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, Maximize2, Minus, Plus } from "lucide-react";
import {
  getCandidateDocuments,
  verifyDocument,
  viewDocument,
} from "../../services/api/documents";
import { sendPlainEmail } from "../../services/api/email";
import { getHrCandidateFullDetails } from "../../services/api/candidateSelfService";

const DOCUMENT_LABELS = {
  pan: "PAN Card",
  aadhar: "Aadhaar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slips",
  bank_statement: "Bank Statement",
  resume: "Resume",
};

export default function DocumentsTab({
  candidateId,
  candidateEmail,
  candidateName,
  onDocumentsUpdate,
}) {
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("success");
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [previewLoadingId, setPreviewLoadingId] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [currentGroupedFileIndex, setCurrentGroupedFileIndex] = useState(0);
  const [previewNavigation, setPreviewNavigation] = useState(null);
  const [rejectDoc, setRejectDoc] = useState(null);
  const [rejectReason, setRejectReason] = useState("");
  const [candidateFullDetails, setCandidateFullDetails] = useState(null);
  const [candidateDetailsLoading, setCandidateDetailsLoading] = useState(false);
  const noticeTimerRef = useRef(null);

  const activeDocument = useMemo(() => {
    if (!selectedDoc) return null;
    const groupedFiles = Array.isArray(selectedDoc?.files)
      ? selectedDoc.files
      : null;
    if (!groupedFiles?.length) {
      return selectedDoc;
    }
    return groupedFiles?.[currentGroupedFileIndex] ?? groupedFiles?.[0] ?? null;
  }, [selectedDoc, currentGroupedFileIndex]);
  const groupedFiles = Array.isArray(selectedDoc?.files)
    ? selectedDoc.files
    : [];
  const hasGroupedFiles = groupedFiles.length > 0;
  const totalGroupedFiles = groupedFiles.length;
  const canGoPrevious = currentGroupedFileIndex > 0;
  const canGoNext = currentGroupedFileIndex < totalGroupedFiles - 1;

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
      console.log("Rows:", rows);
      if (onDocumentsUpdate) {
        onDocumentsUpdate(data);
      }
      setDocuments(rows);
      if (rows.length && !selectedDoc) {
        setSelectedDoc(rows[0]);
      }
    } catch (err) {
      setDocuments([]);
      setSelectedDoc(null);
      showNotice(err.message || "Failed to load documents.", "error");
    } finally {
      setLoading(false);
    }
  }, [candidateId, selectedDoc, showNotice]);
  const fetchCandidateFullDetails = useCallback(async () => {
    if (!candidateId) return;
    try {
      setCandidateDetailsLoading(true);
      const data = await getHrCandidateFullDetails(candidateId);
      setCandidateFullDetails(data || null);
    } catch (err) {
      setCandidateFullDetails(null);
      showNotice(
        err?.message || "Failed to load candidate submitted details.",
        "error",
      );
    } finally {
      setCandidateDetailsLoading(false);
    }
  }, [candidateId, showNotice]);

  useEffect(() => {
    fetchDocuments();
    fetchCandidateFullDetails();

    return () => {
      if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    };
  }, [fetchDocuments, fetchCandidateFullDetails]);
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    const loadGroupedPreview = async () => {
      if (!hasGroupedFiles || !activeDocument?.id) return;
      try {
        setPreviewLoadingId(activeDocument.id);
        clearPreviewUrl();
        const { blob } = await viewDocument(activeDocument.id);
        const fileUrl = URL.createObjectURL(blob);
        setPreviewUrl(fileUrl);
      } catch (err) {
        showNotice(err?.message || "Failed to open document.", "error");
      } finally {
        setPreviewLoadingId(null);
        setPreviewNavigation(null);
      }
    };
    loadGroupedPreview();
  }, [activeDocument?.id, hasGroupedFiles]);

  const handleSelectDocument = async (doc) => {
    if (!doc) return;
    setSelectedDoc(doc);
    setCurrentGroupedFileIndex(0);
    clearPreviewUrl();
    const documentToPreview = Array.isArray(doc?.files) ? doc?.files?.[0] : doc;
    if (!documentToPreview?.id) {
      showNotice("Document preview is not available.", "error");
      return;
    }
    try {
      setPreviewLoadingId(documentToPreview?.id);
      const { blob } = await viewDocument(documentToPreview?.id);
      const fileUrl = URL.createObjectURL(blob);
      clearPreviewUrl();
      setPreviewUrl(fileUrl);
    } catch (err) {
      setPreviewUrl("");
      showNotice(err?.message || "Failed to open document.", "error");
    } finally {
      setPreviewLoadingId(null);
    }
  };
  const notifyCandidateDocumentStatus = async ({
    documentType,
    status,
    reason = "",
  }) => {
    if (!candidateEmail) {
      return {
        success: false,
        message: "Candidate email is missing.",
      };
    }
    const documentLabel = getDocumentLabel(documentType);
    const displayName = candidateName || "Candidate";
    const subject =
      status === "approved"
        ? `${documentLabel} Approved`
        : `${documentLabel} Rejected`;

    const bodyContent =
      status === "approved"
        ? `Hi ${displayName},

Your ${documentLabel} has been approved successfully.
Regards,
HR Team`
        : `Hi ${displayName},

Your ${documentLabel} has been rejected.
Reason: ${reason}
Please upload the correct document again.
Regards,
HR Team`;
    try {
      await sendPlainEmail({
        toEmail: candidateEmail,
        subject,
        bodyContent,
        isHtml: false,
        ccEmails: [],
      });
      return {
        success: true,
        message: "Notification email sent.",
      };
    } catch (err) {
      return {
        success: false,
        message: err.message || "Email notification failed.",
      };
    }
  };

  const handleVerifyDocument = async (doc) => {
    console.log("Selected document:", doc);
    if (!doc?.document_type) {
      showNotice("Document type is missing.", "error");
      return;
    }
    try {
      setActionLoadingId(doc?.id);
      await verifyDocument(doc?.id, true);

      const emailResult = await notifyCandidateDocumentStatus({
        documentType: doc.document_type,
        status: "approved",
      });
      await fetchDocuments();
      closeRejectModal();
      showNotice(
        emailResult.success
          ? `${getDocumentLabel(doc?.document_type)} approved and notification sent.`
          : `${getDocumentLabel(doc?.document_type)} approved, but ${emailResult.message}`,
        emailResult.success ? "success" : "error",
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
      await verifyDocument(rejectDoc?.id, false, trimmedReason);
      const emailResult = await notifyCandidateDocumentStatus({
        documentType: rejectDoc.document_type,
        status: "rejected",
        reason: trimmedReason,
      });
      await fetchDocuments();
      closeRejectModal();
      showNotice(
        emailResult.success
          ? `${getDocumentLabel(rejectDoc.document_type)} rejected and notification sent successfully.`
          : `${getDocumentLabel(rejectDoc.document_type)} rejected, but email notification failed.`,
        emailResult.success ? "success" : "error",
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
                  const isGroupedDocument = Array.isArray(doc?.files);
                  const isSelected = isGroupedDocument
                    ? selectedDoc?.document_type === doc?.document_type
                    : selectedDoc?.id === doc?.id;
                  const currentDoc = isGroupedDocument
                    ? doc?.files?.[currentGroupedFileIndex]
                    : doc;
                  const isVerified = Boolean(currentDoc?.is_verified);
                  const showRejectReason =
                    !isVerified && Boolean(currentDoc?.notes);
                  const isPreviewLoading = previewLoadingId === currentDoc?.id;
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
                  doc={activeDocument}
                  candidateFullDetails={candidateFullDetails}
                  isCandidateDetailsLoading={candidateDetailsLoading}
                  previewUrl={previewUrl}
                  isPreviewLoading={previewLoadingId === activeDocument?.id}
                  previewNavigation={previewNavigation}
                  isActionLoading={actionLoadingId === activeDocument?.id}
                  onPreview={() => handleSelectDocument(activeDocument)}
                  onVerify={() => handleVerifyDocument(activeDocument)}
                  onReject={() => openRejectModal(activeDocument)}
                  hasGroupedFiles={hasGroupedFiles}
                  currentGroupedFileIndex={currentGroupedFileIndex}
                  totalGroupedFiles={totalGroupedFiles}
                  canGoPrevious={canGoPrevious}
                  canGoNext={canGoNext}
                  onPrevious={() => {
                    setPreviewNavigation("previous");
                    setPreviewUrl("");
                    setCurrentGroupedFileIndex((prev) => prev - 1);
                  }}
                  onNext={() => {
                    setPreviewNavigation("next");
                    setPreviewUrl("");
                    setCurrentGroupedFileIndex((prev) => prev + 1);
                  }}
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
  candidateFullDetails,
  isCandidateDetailsLoading,
  previewUrl,
  isPreviewLoading,
  isActionLoading,
  onPreview,
  previewNavigation,
  onVerify,
  onReject,
  hasGroupedFiles,
  currentGroupedFileIndex,
  totalGroupedFiles,
  canGoPrevious,
  canGoNext,
  onPrevious,
  onNext,
}) {
  const [zoomLevel, setZoomLevel] = useState(100);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const viewerRef = useRef(null);
  const isVerified = Boolean(doc?.is_verified);
  const isImageFile = /\.(jpg|jpeg|png|webp)$/i.test(
    doc?.original_filename || "",
  );
  const isRejected = !isVerified && Boolean(doc?.notes);
  const handleZoomIn = () => {
    setZoomLevel((prev) => Math.min(prev + 10, 200));
  };
  const handleZoomOut = () => {
    setZoomLevel((prev) => Math.max(prev - 10, 50));
  };
  const handleFullscreen = async () => {
    try {
      if (document?.fullscreenElement) {
        await document?.exitFullscreen?.();
        return;
      }
      await viewerRef?.current?.requestFullscreen();
    } catch (error) {
      console.error("Fullscreen failed:", error);
    }
  };
  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
    };
  }, []);
  const submittedDetails = getSubmittedDetailsByDocumentType(
    doc?.document_type,
    candidateFullDetails,
  );
  const displayedGroups =
    hasGroupedFiles && Array.isArray(submittedDetails?.groups)
      ? submittedDetails.groups.slice(
          currentGroupedFileIndex,
          currentGroupedFileIndex + 1,
        )
      : submittedDetails?.groups;
  return (
    <div className="flex min-h-[72vh] flex-col">
      <div className="border-b px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold text-gray-900">
                {getDocumentLabel(doc?.document_type)}
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
      <div className="border-b p-5">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)]">
          <div className="rounded-2xl border border-gray-100 bg-white">
            <div className="border-b px-4 py-3">
              <h4 className="text-sm font-semibold text-gray-900">
                File Details
              </h4>
              <p className="mt-1 text-xs text-gray-500">
                Uploaded document information.
              </p>
            </div>

            <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
              <Info label="File Name" value={doc?.original_filename || "-"} />
              <Info
                label="Document Type"
                value={getDocumentLabel(doc?.document_type)}
              />
              <Info label="Uploaded At" value={formatDate(doc?.uploaded_at)} />
              <Info label="File Size" value={formatFileSize(doc?.file_size)} />
            </div>
          </div>

          <CandidateSubmittedDetails
            title={submittedDetails?.title}
            description={submittedDetails?.description}
            fields={submittedDetails?.fields}
            isLoading={isCandidateDetailsLoading}
            groups={displayedGroups}
          />
        </div>

        {isRejected ? (
          <div className="mt-4 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span className="font-semibold">Rejection reason:</span>{" "}
            {doc?.notes}
          </div>
        ) : null}
      </div>

      <div className="flex-1 p-5">
        {previewUrl ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-2xl border bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleZoomOut}
                  className="flex h-9 w-9 items-center justify-center rounded-xl border transition hover:bg-gray-50"
                >
                  <Minus size={16} />
                </button>

                <div className="min-w-[70px] text-center text-sm font-semibold text-gray-700">
                  {zoomLevel}%
                </div>

                <button
                  type="button"
                  onClick={handleZoomIn}
                  className="flex h-9 w-9 items-center justify-center rounded-xl border transition hover:bg-gray-50"
                >
                  <Plus size={16} />
                </button>
              </div>

              <div className="flex items-center gap-2">
                <a
                  href={previewUrl}
                  download={doc?.original_filename || "document"}
                  className="flex h-9 items-center gap-2 rounded-xl border px-4 text-sm font-medium transition hover:bg-gray-50"
                >
                  <Download size={16} />
                  Download
                </a>

                <button
                  type="button"
                  onClick={handleFullscreen}
                  className="flex h-9 items-center gap-2 rounded-xl border px-4 text-sm font-medium transition hover:bg-gray-50"
                >
                  <Maximize2 size={16} />
                  Fullscreen
                </button>
              </div>
            </div>
            {hasGroupedFiles ? (
              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={onPrevious}
                  disabled={!canGoPrevious}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:border-blue-500 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  ← Previous
                </button>
                <div className="rounded-lg bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700">
                  {currentGroupedFileIndex + 1} / {totalGroupedFiles}
                </div>
                <button
                  type="button"
                  onClick={onNext}
                  disabled={!canGoNext}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:border-blue-500 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next →
                </button>
              </div>
            ) : null}

            <div
              ref={viewerRef}
              className={`relative rounded-2xl border bg-gray-100 ${
                isImageFile
                  ? "flex h-[58vh] items-center justify-center overflow-auto p-6"
                  : "overflow-hidden"
              }`}
            >
              <div className="flex min-h-full min-w-full items-center justify-center p-6">
                {isImageFile ? (
                  <img
                    src={previewUrl}
                    alt={getDocumentLabel(doc?.document_type)}
                    draggable={false}
                    className="max-h-full max-w-full object-contain rounded-xl shadow-lg transition-transform duration-200"
                    style={{
                      transform: `scale(${zoomLevel / 100})`,
                      transformOrigin: "center center",
                    }}
                  />
                ) : (
                  <iframe
                    src={previewUrl}
                    title={getDocumentLabel(doc?.document_type)}
                    className="h-[70vh] w-full border-0 bg-white"
                    style={{
                      display: "block",
                    }}
                  />
                )}
              </div>
            </div>
          </div>
        ) : isPreviewLoading &&
          previewNavigation &&
          (doc?.document_type === "education" ||
            doc?.document_type === "experience") ? (
          <div className="flex h-[58vh] flex-col items-center justify-center rounded-2xl border border-dashed bg-gray-50 text-center">
            <div className="text-sm font-semibold text-gray-700">
              Loading document preview...
            </div>
            <p className="mt-1 max-w-sm text-sm text-gray-400">
              Please wait while the{" "}
              {previewNavigation === "previous" ? "previous" : "next"} document
              is being loaded.
            </p>
          </div>
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
              {getDocumentLabel(doc?.document_type)}
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
function CandidateSubmittedDetails({
  title,
  description,
  fields,
  isLoading,
  groups,
}) {
  const visibleFields = Array.isArray(fields)
    ? fields.filter(
        (field) =>
          field?.value !== undefined &&
          field?.value !== null &&
          field?.value !== "",
      )
    : [];
  const visibleGroups = Array.isArray(groups)
    ? groups
        .map((group) => ({
          ...group,
          fields: group.fields.filter(
            (field) =>
              field?.value !== undefined &&
              field?.value !== null &&
              field?.value !== "",
          ),
        }))
        .filter((group) => group.fields.length)
    : [];

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-700">
          Loading candidate submitted details...
        </div>
      </div>
    );
  }

  if (!visibleFields?.length && !visibleGroups?.length) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-700">
          No Submitted Details Available
        </div>
        <p className="mt-1 text-xs text-gray-400">
          No candidate details are available for this document type.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-gray-100 bg-white">
      <div className="border-b px-4 py-3">
        <h4 className="text-sm font-semibold text-gray-900">
          {title || "Candidate Submitted Details"}
        </h4>
        {description ? (
          <p className="mt-1 text-xs text-gray-500">{description}</p>
        ) : null}
      </div>
      {visibleGroups?.length ? (
        <div className="space-y-5 p-4">
          {visibleGroups.map((group, index) => (
            <div key={index} className="rounded-xl border border-gray-200">
              <div className="border-b bg-gray-50 px-4 py-3">
                <h5 className="font-semibold text-gray-800">{group?.title}</h5>
              </div>
              <div className="grid gap-3 p-4 md:grid-cols-2 2xl:grid-cols-3">
                {group.fields
                  .filter(
                    (field) =>
                      field?.value !== undefined &&
                      field?.value !== null &&
                      field?.value !== "",
                  )
                  .map((field) => (
                    <Info
                      key={`${field?.label}-${field?.value}`}
                      label={field?.label}
                      value={field?.value}
                    />
                  ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid gap-3 p-4 md:grid-cols-2 2xl:grid-cols-3">
          {visibleFields.map((field) => (
            <Info
              key={`${field?.label}-${field?.value}`}
              label={field?.label}
              value={field?.value}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function getSubmittedDetailsByDocumentType(documentType, candidateFullDetails) {
  const normalizedType = String(documentType || "").toLowerCase();

  if (normalizedType.includes("aadhar")) {
    const aadhar = candidateFullDetails?.aadhar;
    return {
      title: "Aadhar Details",
      description:
        "Details submitted by the candidate for Aadhar verification.",
      fields: [
        {
          label: "Aadhar Number",
          value: aadhar?.aadhar,
        },
        {
          label: "Name in Aadhar",
          value: aadhar?.name_in_aadhar,
        },
        {
          label: "Enrollment Number",
          value: aadhar?.enrollment_number,
        },
        {
          label: "Submitted",
          value: formatBooleanStatus(aadhar?.aadhar_is_submitted),
        },
      ],
    };
  }

  if (normalizedType.includes("pan")) {
    const pan = candidateFullDetails?.pan;

    return {
      title: "PAN Details",
      description: "Details submitted by the candidate for PAN verification.",
      fields: [
        {
          label: "PAN Number",
          value: pan?.pan,
        },
        {
          label: "Name in PAN",
          value: pan?.name_in_pan,
        },
        {
          label: "Father Name in PAN",
          value: pan?.father_name_in_pan,
        },
        {
          label: "Submitted",
          value: formatBooleanStatus(pan?.pan_is_submitted),
        },
      ],
    };
  }
  if (normalizedType.includes("education")) {
    const educationRecords = Array.isArray(candidateFullDetails?.education)
      ? candidateFullDetails.education
      : [];

    return {
      title: "Education Details",
      description: "Education details submitted by the candidate.",
      groups: educationRecords.map((item, index) => ({
        title: `Education ${index + 1}`,
        fields: [
          {
            label: "University / College",
            value: item?.education_institute,
          },
          {
            label: "Degree",
            value: item?.degree,
          },
          {
            label: "Branch / Specialization",
            value: item?.field_of_study,
          },
          {
            label: "Starting Year",
            value: item?.starting_year,
          },
          {
            label: "Year of Passing",
            value: item?.year_of_passing,
          },
          {
            label: "Percentage",
            value: item?.percentage,
          },
          {
            label: "Document Submitted",
            value: formatBooleanStatus(item?.document_is_submitted),
          },
        ],
      })),
    };
  }

  if (normalizedType.includes("experience")) {
    const experienceRecords = Array.isArray(candidateFullDetails?.experience)
      ? candidateFullDetails.experience
      : [];

    return {
      title: "Experience Details",
      description: "Experience details submitted by the candidate.",
      groups: experienceRecords.flatMap((item, index) => ({
        title: `Experience ${index + 1}`,
        fields: [
          {
            label: `Company ${index + 1}`,
            value: item?.company_name,
          },
          {
            label: `Job Title ${index + 1}`,
            value: item?.job_title,
          },
          {
            label: `Start Date ${index + 1}`,
            value: formatDate(item?.start_date),
          },
          {
            label: `End Date ${index + 1}`,
            value: formatDate(item?.end_date),
          },
          {
            label: `Experience ${index + 1}`,
            value: item?.year_of_experience,
          },
          {
            label: `Document Submitted ${index + 1}`,
            value: formatBooleanStatus(item?.document_is_submitted),
          },
        ],
      })),
    };
  }

  if (normalizedType.includes("resume")) {
    return {
      title: "Candidate Profile Details",
      description: "Basic profile details submitted by the candidate.",
      fields: [
        {
          label: "Candidate Name",
          value: candidateFullDetails?.candidate_name,
        },
        {
          label: "Email",
          value: candidateFullDetails?.candidate_email,
        },
        {
          label: "Mobile",
          value: candidateFullDetails?.candidate_mobile,
        },
        {
          label: "Job Title",
          value: candidateFullDetails?.candidate_job_title,
        },
        {
          label: "Experience",
          value: candidateFullDetails?.candidate_experience,
        },
        {
          label: "Skills",
          value: candidateFullDetails?.candidate_skills,
        },
      ],
    };
  }

  return {
    title: "Candidate Submitted Details",
    description: "No mapped candidate details found for this document type.",
    fields: [],
  };
}

function formatBooleanStatus(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "-";
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
