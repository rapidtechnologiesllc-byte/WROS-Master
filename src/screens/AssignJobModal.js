import { Button, Card, Table } from "../components/ui";
import { assignJob } from "../services/api/jobs";
import { toast } from "react-toastify";

const AssignJobModal = ({
  candidate,
  onClose,
  allCandidates,
  selectedJob,
  setAssignModal,
  onAssignSuccess,
}) => {
  const assignJobHandler = async (candidateId) => {
    if (!candidateId) {
      toast.error("Invalid Candidate");
      return;
    }

    if (!selectedJob?.id) {
      toast.error("No job selected");
      return;
    }

    try {
      const result = await assignJob(selectedJob.id, candidateId);
      if (result?.status === 200) {
        toast.success("Job assigned successfully ✅");
        const selectedCandidate = allCandidates.find(
          (c) => c.id === candidateId,
        );
        onAssignSuccess?.(selectedCandidate);
        onClose();
      } else {
        toast.error("Failed to assign job");
      }
    } catch (err) {
      console.error(err);
      toast.error("Something went wrong ❌");
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex justify-center bg-black/40 p-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <div className="w-full max-w-4xl max-h-[80vh] flex flex-col">
          <Card
            title="Assign Candidate"
            bodyClassName="px-2 py-4"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div>
              <div className="max-h-[65vh] overflow-y-auto">
                <Table
                  columns={[
                    { key: "candidate", header: "Candidate" },
                    { key: "source", header: "Source" },
                    { key: "applied", header: "Applied / Added On" },
                    { key: "owner", header: "Owner" },
                    { key: "stage", header: "Stage" },
                    { key: "contact", header: "Contact" },
                    { key: "actions", header: "Actions" },
                  ]}
                  rows={allCandidates.map((c) => ({
                    candidate: (
                      <button className="font-semibold text-blue-700 hover:underline">
                        {c.name}
                      </button>
                    ),
                    source: c.source || "LinkedIn",
                    applied: c.createdAt || "—",
                    owner:
                      c.assignedHrManagerId || c.assignedReportManagerId || "—",
                    contact: (
                      <div className="text-xs">
                        <div>{c.phone || "—"}</div>
                        <div className="text-slate-500">{c.email || "—"}</div>
                      </div>
                    ),
                    actions: (
                      <span className="text-xs text-slate-500">
                        <button
                          onClick={() => {
                            assignJobHandler(c?.id);
                          }}
                          className="bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-emerald-500 disabled:opacity-60 rounded p-2"
                        >
                          Assign Job
                        </button>
                      </span>
                    ),
                  }))}
                />
              </div>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
};

export default AssignJobModal;
