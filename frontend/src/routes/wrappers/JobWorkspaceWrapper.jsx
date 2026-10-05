import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";

import JobWorkspaceScreen from "../../screens/JobWorkspaceScreen";
import { getAllJobs } from "../../services/api/jobs";
import { getCandidateById } from "../../services/api/candidates";
import { getJobById, updateJob } from "../../services/api/jobs";
import { mapJobFromApi, normalizeJobStatusForApi } from "../Approutes";

export default function JobWorkspaceWrapper({ candidates, notify }) {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadJob = async () => {
      setError(null);
      try {
        const response = await getJobById(jobId);
        const mappedJob = mapJobFromApi(response, users);
        setJob(mappedJob);
      } catch (err) {
        setError("Failed to load job");
      }
    };

    loadJob();
  }, [jobId]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-full max-w-md p-6 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h2 className="text-lg font-semibold text-red-900">Error Loading Job</h2>
              <p className="mt-2 text-red-700">{error}</p>
              <button
                onClick={() => navigate("/jobs")}
                className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Go Back to Jobs
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!job) {
    return <div>Loading...</div>;
  }

  return (
    <JobWorkspaceScreen
      job={job}
      candidates={candidates}
      onAddCandidate={() => {
        navigate("/candidates/create");
      }}
      onOpenCandidate={(candidateId) => {
        navigate(`/candidates/${candidateId}`);
      }}
      onFetchCandidateById={async (candidateId) => {
        const res = await getCandidateById(candidateId);
        return res;
      }}
      onUpdateJob={async (fields) => {
        // fields are JobUpdateRequest keys; job_status arrives as the UI label
        const payload = Object.fromEntries(
          Object.entries(fields).filter(([, v]) => v !== undefined),
        );
        if (payload.job_status) payload.job_status = normalizeJobStatusForApi(payload.job_status);
        const updated = await updateJob(job.id, payload);
        setJob(mapJobFromApi(updated, users));
      }}
    />
  );
}
