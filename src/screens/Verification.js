// HR document verification (integrated with backend API).
import { useEffect, useMemo, useState } from "react";
import { ClipboardCheck } from "lucide-react";
import { Button, Card, StatusBadge } from "../components/ui";
import { getCandidateDocuments, verifyDocument } from "../services/api/documents";

const DOC_LABELS = {
  resume: "Resume",
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement"
};

export default function Verification({
  candidate,
  candidates = [],
  selectedCandidateId = "",
  onChangeCandidate,
  onApprove,
  onReject
}) {
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(null);
  const [error, setError] = useState("");

  const activeCandidate = useMemo(() => {
    return (
      candidates.find((c) => String(c.id) === String(selectedCandidateId || candidate?.id)) ||
      candidate
    );
  }, [candidates, selectedCandidateId, candidate]);

  useEffect(() => {
    if (!activeCandidate?.id) return;
    let isMounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await getCandidateDocuments(activeCandidate.id);
        if (isMounted) setDocs(res);
      } catch (err) {
        if (isMounted) setError(err.message || "Failed to load documents.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    load();
    return () => { isMounted = false; };
  }, [activeCandidate?.id]);

  const handleVerify = async (doc, isVerified) => {
    if (!activeCandidate?.id) return;
    setVerifying(doc.id);
    setError("");
    try {
      await verifyDocument(activeCandidate.id, doc.document_type, isVerified);
      const res = await getCandidateDocuments(activeCandidate.id);
      setDocs(res);
    } catch (err) {
      setError(err.message || "Failed to update verification.");
    } finally {
      setVerifying(null);
    }
  };

  const pendingCount = docs?.documents?.filter((d) => !d.is_verified).length ?? 0;
  const allVerified = docs?.documents?.length > 0 && pendingCount === 0;

  return (
    <div className="grid gap-4">
      <Card
        title="Document Verification"
        icon={<ClipboardCheck className="h-4 w-4" />}
        right={
          !loading ? (
            <StatusBadge
              status={allVerified ? "Verified" : `${pendingCount} pending`}
            />
          ) : null
        }
      >
        {candidates.length > 0 && onChangeCandidate ? (
          <label className="mb-4 block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Candidate</div>
            <select
              value={activeCandidate?.id || ""}
              onChange={(e) => onChangeCandidate(e.target.value)}
              className="w-full max-w-md rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.id})
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <div className="mb-3 text-sm text-gray-700">
          Candidate: <span className="font-semibold">{activeCandidate?.name}</span>
        </div>

        {loading ? (
          <div className="py-4 text-center text-sm text-gray-500">
            Loading documents…
          </div>
        ) : null}

        {!loading && error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {!loading && docs?.documents?.length ? (
          <div className="space-y-2">
            {docs.documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-2xl border bg-white p-4"
              >
                <div>
                  <div className="text-sm font-semibold">
                    {DOC_LABELS[doc.document_type] || doc.document_type}
                  </div>
                  <div className="text-xs text-gray-500">
                    {doc.original_filename}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {doc.is_verified ? (
                    <StatusBadge status="Verified" />
                  ) : (
                    <>
                      <Button
                        variant="danger"
                        onClick={() => handleVerify(doc, false)}
                        disabled={verifying === doc.id}
                      >
                        {verifying === doc.id ? "…" : "Reject"}
                      </Button>
                      <Button
                        onClick={() => handleVerify(doc, true)}
                        disabled={verifying === doc.id}
                      >
                        {verifying === doc.id ? "…" : "Verify"}
                      </Button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : !loading ? (
          <div className="rounded-2xl border bg-gray-50 p-4 text-sm text-gray-600">
            No documents to verify.
          </div>
        ) : null}

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={onReject} disabled={loading}>
            Pending / Rejected
          </Button>
          <Button
            onClick={onApprove}
            disabled={
              loading || (!allVerified && docs?.documents?.length > 0)
            }
          >
            All Verified – Proceed
          </Button>
        </div>
      </Card>
    </div>
  );
}
