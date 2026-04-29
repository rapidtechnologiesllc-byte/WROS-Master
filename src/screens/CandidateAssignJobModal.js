import { FileText } from "lucide-react";
import { Button, Card, Select } from "../components/ui";
import { useEffect, useState } from "react";
import { assignMultipleJobs, getAllJobs } from "../services/api/jobs";
import { mapJobFromApi } from "../App";
import { toast } from "react-toastify";

const CandidateAssignJobModal = ({ onClose, candidateDetails }) => {
  const [candidateRole] = useState("Candidate");
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(jobs[0]?.id || "");
  const [users, setUsers] = useState([]);
  const [isAssigning, setIsAssigning] = useState(false);
  const jobOptions = jobs.map((job) => ({
    label: job?.title,
    value: job?.id,
  }));

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        const refreshed = await getAllJobs();
        if (!isMounted) return;
        const mappedJobs = (refreshed?.jobs || []).map((j) =>
          mapJobFromApi(j, users),
        );
        setJobs(mappedJobs);
        if (!selectedJobId && mappedJobs?.length) {
          setSelectedJobId(mappedJobs[0]?.id);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSaveJob = async () => {
    setIsAssigning(true);

    try {
      const result = await assignMultipleJobs(
        selectedJobId,
        candidateDetails?.id,
        { application_status: "Applied" },
      );
      if (result?.status === 201) {
        toast.success("Job submitted successfully ✅");
        onClose();
      }
    } catch (err) {
      toast.error(
        err || "Candidate created but job assignment failed.",
      );
      console.log(err, "error while submitting job");
    } finally {
      setIsAssigning(false);
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4"
        role="dialog"
        aria-modal="true"
      >
        <div className="w-full max-w-4xl">
          <Card
            title="Submit Job"
            icon={<FileText className="h-4 w-4" />}
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div className="mb-4 grid gap-3 md:grid-cols-1">
              <Select
                label="Job Title"
                value={selectedJobId}
                onChange={(value) => setSelectedJobId(value)}
                options={jobOptions}
              />
            </div>
            <div className="mt-3">
              <Button
                onClick={handleSaveJob}
                // disabled={statusSaving}
                variant="primary"
              >
                Save
                {/* {statusSaving ? "Saving…" : "Save status"} */}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
};

export default CandidateAssignJobModal;
