import { useEffect, useState } from "react";
import { Drawer, Select, Button, Space } from "antd";
import {
  agingOptions,
  jobTypeOptions,
  locationOptions,
  priorityOptions,
  statusOptions,
} from "../../utils/mockData";
import { getAllUsers } from "../../services/api/users";
import { listBusinessUnits, departmentList } from "../../services/api/rbac";
import { listClients } from "../../services/api/clients";

const MANAGER_ROLES = ["Hiring Manager"];
const RECRUITER_ROLES = ["Recruiter", "Recruitment Manager", "Recruitment Team Lead"];

const FIlterDrawer = ({ open, onClose, filters, setFilters, onApply }) => {
  const [buOptions, setBuOptions] = useState([]);
  const [deptOptions, setDeptOptions] = useState([]);
  const [clientOptions, setClientOptions] = useState([]);
  const [managerOptions, setManagerOptions] = useState([]);
  const [recruiterOptions, setRecruiterOptions] = useState([]);

  useEffect(() => {
    // Real entity lists, not hardcoded fake names -- some (BU/Department)
    // are permission-gated (rbac.manage) so may come back empty for
    // roles that don't hold that permission; fails gracefully to an
    // empty dropdown rather than showing fabricated options.
    listBusinessUnits()
      .then((data) =>
        setBuOptions((data || []).map((bu) => ({ label: bu.name, value: bu.id }))),
      )
      .catch(() => setBuOptions([]));

    departmentList()
      .then((data) =>
        setDeptOptions((data || []).map((d) => ({ label: d.name, value: d.id }))),
      )
      .catch(() => setDeptOptions([]));

    listClients()
      .then((data) =>
        setClientOptions(
          (data?.clients || []).map((c) => ({ label: c.company_name, value: c.id })),
        ),
      )
      .catch(() => setClientOptions([]));

    getAllUsers()
      .then((data) => {
        const users = data?.users || [];
        setManagerOptions(
          users
            .filter((u) => MANAGER_ROLES.includes(u.user_role))
            .map((u) => ({ label: u.user_name, value: u.user_id })),
        );
        setRecruiterOptions(
          users
            .filter((u) => RECRUITER_ROLES.includes(u.user_role))
            .map((u) => ({ label: u.user_name, value: u.user_id })),
        );
      })
      .catch(() => {
        setManagerOptions([]);
        setRecruiterOptions([]);
      });
  }, []);

  const handleChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };
  return (
    <Drawer title="Filters" open={open} onClose={onClose}>
      <Space
        direction="vertical"
        style={{ width: "fit-content" }}
        size="middle"
      >
        <Select
          mode="multiple"
          placeholder="Status"
          options={statusOptions}
          value={filters.status}
          onChange={(v) => handleChange("job_status", v)}
          allowClear
          style={{ width: "100%" }}
        />
        <Select
          mode="multiple"
          placeholder="Job Type"
          options={jobTypeOptions}
          value={filters.type}
          style={{ width: "100%" }}
          onChange={(v) => handleChange("type", v)}
          allowClear
        />
        <Select
          placeholder="BU"
          options={buOptions}
          value={filters.bu}
          onChange={(v) => handleChange("bu", v)}
          style={{ width: "100%" }}
          allowClear
        />
        <Select
          placeholder="Department"
          options={deptOptions}
          onChange={(v) => handleChange("dept", v)}
          allowClear
          style={{ width: "100%" }}
        />
        <Select
          placeholder="Client"
          options={clientOptions}
          onChange={(v) => handleChange("client", v)}
          allowClear
          style={{ width: "100%" }}
        />
        <Select
          placeholder="Hiring Manager"
          options={managerOptions}
          onChange={(v) => handleChange("manager", v)}
          allowClear
          style={{ width: "100%" }}
        />
        <Select
          placeholder="Recruiter"
          options={recruiterOptions}
          onChange={(v) => handleChange("recruiter", v)}
          allowClear
          style={{ width: "100%" }}
        />
        <Select
          placeholder="Location"
          options={locationOptions}
          onChange={(v) => handleChange("location", v)}
          allowClear
          style={{ width: "100%" }}
        />
        <Select
          placeholder="Priority"
          options={priorityOptions}
          onChange={(v) => handleChange("priority", v)}
          allowClear
          style={{ width: "100%" }}
        />
        <Select
          placeholder="Aging Range"
          options={agingOptions}
          onChange={(v) => handleChange("aging", v)}
          allowClear
          style={{ width: "100%" }}
        />

        <Button type="primary" onClick={onApply} block>
          Apply Filters
        </Button>
      </Space>
    </Drawer>
  );
};

export default FIlterDrawer;
