import { react, useState } from "react";
import { Button, Card, Select, TextArea } from "../components/ui";
import { toast } from "react-toastify";
import { updateCandidateStatus } from "../services/api/candidates";

const PreonboardingModal = ({
  fullName,
  candidate,
  onClose,
  status,
  onSuccess,
}) => {
  const Locations = ["Hyderabad", "Chennai", "Texas", "Remote"];
  const Department = ["PRISM", "Sales", "HR"];
  const [selectLocation, setSelectLocation] = useState();
  const [selectDepartment, setSelectDepartment] = useState();
  const [note, setNote] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleSaveOnly = async () => {
    try {
      const updateStatus = await updateCandidateStatus(candidate?.id, {
        status: "Active",
        pipeline_status: status,
      });
      if (updateStatus?.status === "success") {
        toast.success(
          `Candidate ${updateStatus?.data?.candidate_name} moved to ${status}`,
        );
        onSuccess?.(status);
      }
    } catch (err) {
      toast.error("Error", err.message);
    } finally {
      onClose();
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
            title="Initia Pre-Onboarding Process"
            bodyClassName="px-2 py-4"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div>
              <span className="px-4">Preonboarding will be initiated for</span>
              <span style={{ fontSize: "16px", fontWeight: "bold" }}>
                {fullName}
              </span>
            </div>

            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Select Location"
                value={selectLocation}
                onChange={setSelectLocation}
                options={Locations}
              />
              <Select
                label="Select Department"
                value={selectDepartment}
                onChange={setSelectDepartment}
                options={Department}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Select BU (optional)"
                value={selectLocation}
                onChange={setSelectLocation}
                options={[]}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <TextArea
                label="Internal Note"
                placeholder="Add note here"
                onChange={setNote}
                value={note}
              />
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <Button variant="secondary">Cancel</Button>
              <Button onClick={handleSaveOnly} disabled={isSaving}>
                {isSaving ? "Saving..." : "Save"}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
};

export default PreonboardingModal;
