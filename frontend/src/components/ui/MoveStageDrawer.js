import React, { useState } from "react";
import { Drawer, Select, Button, Space } from "antd";
import { updateCandidateStatus } from "../../services/api/candidates";
import { X, CheckCircle } from "lucide-react";

const MoveStageDrawer = ({ open, onClose, onSubmit, data }) => {
  const [stage, setStage] = useState();
  const [screenError, setScreenError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const stageOptions = [
    { label: "Applied", value: "Applied" },
    { label: "Hired", value: "Hired" },
    { label: "Interview", value: "Interview" },
    { label: "Screening", value: "Screening" },
    { label: "Onboarded", value: "Onboarded" },
    { label: "Pre-Onboarding", value: "Pre-Onboarding" },
    { label: "Rejected", value: "Rejected" },
  ];
  const handleSubmit = async () => {
    try {
      const result = await updateCandidateStatus(data?.id, {
        status: "Active",
        pipeline_status: stage,
      });
      if (result?.status === "success") {
        setActionSuccess(
          `Candidate ${result?.data?.candidate_name} moved to ${result?.data?.pipeline_status}`,
        );
        onSubmit(result?.data);
      }
      onClose();
    } catch (err) {
      // stays open: a refused move says what is still needed
      console.error("[MoveStage] Move refused:", err);
      setScreenError(err?.message || String(err));
    }
  };
  return (
    <>
      {/* Success Banner */}
      {actionSuccess && (
        <div className="mb-4 border border-green-200 bg-green-50 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-green-600">
              <CheckCircle className="h-5 w-5" />
            </div>
            <span className="text-green-800">{actionSuccess}</span>
          </div>
          <button
            onClick={() => setActionSuccess(null)}
            className="text-green-600 hover:text-green-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <Drawer title="Move Stage" open={open} onClose={onClose} width={400}>
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        {screenError ? (
          <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{screenError}</div>
        ) : null}
        <Select
          placeholder="Current Stage"
          options={stageOptions}
          value={data?.status}
          onChange={setStage}
          disabled={true}
          style={{ width: "100%" }}
        />
        <Select
          placeholder="Select Stage"
          options={stageOptions}
          value={stage}
          onChange={setStage}
          style={{ width: "100%" }}
        />

        <Button type="primary" block onClick={handleSubmit} disabled={!stage}>
          Move
        </Button>
        </Space>
      </Drawer>
    </>
  );
};

export default MoveStageDrawer;
