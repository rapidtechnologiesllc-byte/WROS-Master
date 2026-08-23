// HR view of candidate documents (from backend API).
import { useEffect, useMemo, useState } from "react";
import { FileText } from "lucide-react";
import { Button, Card, StatusBadge } from "../components/ui";
import { getCandidateDocuments, viewDocument } from "../services/api/documents";

const DOC_LABELS = {
  resume: "Resume",
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement"
};

export default function Documents({
  candidate,
  candidates = [],
  selectedCandidateId = "",
  onChangeCandidate,
  onSubmit
}) {
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const activeCandidate = useMemo(() => {
    return (
      candidates.find((c) => String(c.id) === String(selectedCandidateId || candidate?.id)) ||
      candidate
    );
  }, [candidates, selectedCandidateId, candidate]);

  const handleView = async (documentId) => {
    try {
      const { blob } = await viewDocument(documentId);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 15000);
    } catch (err) {
      setError(err.message || "Failed to view document.");
    }
  };

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

  return (
    <div className="grid gap-4">
      <Card title="Candidate Documents" icon={<FileText className="h-4 w-4" />}>
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
          {activeCandidate?.email ? (
            <span className="ml-2 text-gray-500">({activeCandidate.email})</span>
          ) : null}
        </div>

        {loading ? (
          <div className="py-4 text-center text-sm text-gray-500">
            Loading documents…
          </div>
        ) : null}

        {!loading && error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
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
                <div className="flex items-center gap-3">
                  <FileText className="h-4 w-4 text-gray-500" />
                  <div>
                    <div className="text-sm font-semibold">
                      {DOC_LABELS[doc.document_type] || doc.document_type}
                    </div>
                    <div className="text-xs text-gray-500">
                      {doc.original_filename} •{" "}
                      {doc.uploaded_at
                        ? new Date(doc.uploaded_at).toLocaleDateString()
                        : "-"}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={doc.is_verified ? "Verified" : "Pending"} />
                  <Button
                    variant="secondary"
                    onClick={() => handleView(doc.id)}
                    disabled={!doc.id}
                  >
                    View
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : !loading ? (
          <div className="rounded-2xl border bg-gray-50 p-4 text-sm text-gray-600">
            No documents uploaded yet. Candidate can upload from their portal.
          </div>
        ) : null}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onSubmit}
            className="rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800"
          >
            Go to Verification
          </button>
        </div>
      </Card>
    </div>
  );
}
