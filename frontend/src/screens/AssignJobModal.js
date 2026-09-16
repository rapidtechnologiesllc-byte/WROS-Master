import { useState } from "react";
import { Button, Card, Table } from "../components/ui";
import { assignJob } from "../services/api/jobs";
import { X, AlertTriangle, CheckCircle } from "lucide-react";

const AssignJobModal = ({
  candidate,
  onClose,
  allCandidates,
  selectedJob,
  setAssignModal,
  onAssignSuccess,
}) => {
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const assignJobHandler = async (candidateId) => {
    setActionError(null);
    setActionSuccess(null);

    if (!candidateId) {
      setActionError("Invalid Candidate");
      return;
    }

    if (!selectedJob?.id) {
      setActionError("No job selected");
      return;
    }

    try {
      const result = await assignJob(selectedJob.id, candidateId, {
        application_status: "Applied",
      });
      if (result?.status === 201) {
        setActionSuccess("Job assigned successfully ✅");
        const selectedCandidate = allCandidates.find(
          (c) => c.id === candidateId,
        );
        onAssignSuccess?.(selectedCandidate);
        onClose();
      } else {
        setActionError("Failed to assign job");
      }
    } catch (err) {
      console.error(err);
      setActionError("Something went wrong ❌");
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
            title="Submit Candidate"
            bodyClassName="px-2 py-4"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div>
              {actionError && (
                <div className="mb-3 flex items-start gap-3 rounded-lg bg-red-50 px-4 py-3 border border-red-200">
                  <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-red-800">{actionError}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActionError(null)}
                    className="flex-shrink-0 text-red-400 hover:text-red-600"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              )}
              {actionSuccess && (
                <div className="mb-3 flex items-start gap-3 rounded-lg bg-green-50 px-4 py-3 border border-green-200">
                  <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-600 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-green-800">{actionSuccess}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActionSuccess(null)}
                    className="flex-shrink-0 text-green-400 hover:text-green-600"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              )}
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
                          Submit Candidate
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
