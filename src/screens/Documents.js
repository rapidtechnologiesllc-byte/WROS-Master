// HR view of candidate documents (from backend API).
import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { Card, StatusBadge } from "../components/ui";
import { getCandidateDocuments } from "../services/api/documents";

const DOC_LABELS = {
  resume: "Resume",
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement"
};

export default function Documents({ candidate, onSubmit }) {
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!candidate?.id) return;
    let isMounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await getCandidateDocuments(candidate.id);
        if (isMounted) setDocs(res);
      } catch (err) {
        if (isMounted) setError(err.message || "Failed to load documents.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    load();
    return () => { isMounted = false; };
  }, [candidate?.id]);

  if (loading) {
    return (
      <div className="grid gap-4">
        <Card title="Candidate Documents" icon={<FileText className="h-4 w-4" />}>
          <div className="py-4 text-center text-sm text-gray-500">
            Loading documents…
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <Card title="Candidate Documents" icon={<FileText className="h-4 w-4" />}>
        <div className="mb-3 text-sm text-gray-700">
          Candidate: <span className="font-semibold">{candidate?.name}</span>
          {candidate?.email ? (
            <span className="ml-2 text-gray-500">({candidate.email})</span>
          ) : null}
        </div>

        {error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {docs?.documents?.length ? (
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
                <StatusBadge
                  status={doc.is_verified ? "Verified" : "Pending"}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border bg-gray-50 p-4 text-sm text-gray-600">
            No documents uploaded yet. Candidate can upload from their portal.
          </div>
        )}

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
