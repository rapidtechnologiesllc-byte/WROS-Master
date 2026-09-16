import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { AlertCircle, CheckCircle, X } from "lucide-react";
import CandidateDetailsScreen from "../../screens/CandidateDetailsScreen";
import { useSearchParams } from "react-router-dom";

export default function CandidateDetailsWrapper({
  fetchCandidateById,
  refreshCandidates,
  updateCandidate,
  notify,
}) {
  const { candidateId } = useParams();
  const [candidate, setCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchParams] = useSearchParams();
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const autoOpenSchedule = searchParams.get("schedule") === "true";
  const defaultTab = searchParams.get("tab") || "profile";

  useEffect(() => {
    const loadCandidate = async () => {
      try {
        const data = await fetchCandidateById(candidateId);
        setCandidate(data);
      } finally {
        setLoading(false);
      }
    };

    loadCandidate();
  }, [candidateId, fetchCandidateById]);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <>
      {/* Action Error Banner */}
      {actionError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-700 text-sm font-medium">{actionError}</p>
            </div>
            <button
              onClick={() => setActionError(null)}
              className="text-red-600 hover:text-red-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Action Success Banner */}
      {actionSuccess && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-green-700 text-sm font-medium">{actionSuccess}</p>
            </div>
            <button
              onClick={() => setActionSuccess(null)}
              className="text-green-600 hover:text-green-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      <CandidateDetailsScreen
        candidate={candidate}
        onRefreshCandidates={refreshCandidates}
        autoOpenSchedule={autoOpenSchedule}
        defaultTab={defaultTab}
        onUpdateCandidate={async (id, payload) => {
          setActionError(null);
          setActionSuccess(null);
          try {
            await updateCandidate(id, payload);
            try {
              const updatedCandidate = await fetchCandidateById(id);
              if (updatedCandidate && Object.keys(updatedCandidate).length > 0) {
                setCandidate(updatedCandidate);
              }
            } catch (fetchErr) {
            }
            if (typeof refreshCandidates === "function") {
              try {
                await refreshCandidates();
              } catch (refreshErr) {
              }
            }
            setActionSuccess("Candidate Updated");
          } catch (err) {
            console.error("Failed to update candidate:", err);
            setActionError(err?.message || "Failed to update candidate.");
          }
        }}
      />
    </>
  );
}
