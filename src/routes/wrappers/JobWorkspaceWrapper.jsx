import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import JobWorkspaceScreen from "../../screens/JobWorkspaceScreen";
import { getAllJobs } from "../../services/api/jobs";
import { getCandidateById } from "../../services/api/candidates";
import { getJobById } from "../../services/api/jobs";
import { mapJobFromApi } from "../Approutes";
import { toast } from "react-toastify";

export default function JobWorkspaceWrapper({ candidates, notify }) {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [users, setUsers] = useState([]);

  useEffect(() => {
    const loadJob = async () => {
      try {
        const response = await getJobById(jobId);
        const mappedJob = mapJobFromApi(response, users);
        setJob(mappedJob);
      } catch (err) {
        toast.error("Failed to load job");
      }
    };

    loadJob();
  }, [jobId]);

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
    />
  );
}
