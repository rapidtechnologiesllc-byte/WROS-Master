import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
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
    <CandidateDetailsScreen
      candidate={candidate}
      onRefreshCandidates={refreshCandidates}
      autoOpenSchedule={autoOpenSchedule}
      defaultTab={defaultTab}
      onUpdateCandidate={async (id, payload) => {
        try {
          await updateCandidate(id, payload);
          await refreshCandidates();
        } catch (err) {
          notify("Candidate", err.message || "Failed to update candidate.");
        }
      }}
    />
  );
}
