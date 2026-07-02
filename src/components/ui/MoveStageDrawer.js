import React, { useState } from "react";
import { Drawer, Select, Button, Space } from "antd";
import { updateCandidateStatus } from "../../services/api/candidates";
import { toast } from "react-toastify";

const MoveStageDrawer = ({ open, onClose, onSubmit, data }) => {
  const [stage, setStage] = useState();
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
        toast.success(
          `Candidate ${result?.data?.candidate_name} moved to ${result?.data?.pipeline_status}`,
        );
        onSubmit(result?.data);
      }
    } catch (err) {
      toast.error(err)
    } finally {
      onClose();
    }
  };
  return (
    <Drawer title="Move Stage" open={open} onClose={onClose} width={400}>
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
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
  );
};

export default MoveStageDrawer;
