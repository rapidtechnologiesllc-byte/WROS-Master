import { Drawer, Select, Button, Space } from "antd";
import { agingOptions, buOptions, clientOptions, deptOptions, jobTypeOptions, locationOptions, managerOptions, priorityOptions, recruiterOptions, statusOptions } from "../../utils/mockData";

const FIlterDrawer = ({ open, onClose, filters, setFilters }) => {
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
          onChange={(v) => handleChange("status", v)}
          allowClear
          style={{ width: '100%' }}
        />
        <Select
          mode="multiple"
          placeholder="Job Type"
          options={jobTypeOptions}
          value={filters.type}
          style={{ width: '100%' }}
          onChange={(v) => handleChange("type", v)}
          allowClear
        />
        <Select
          placeholder="BU"
          options={buOptions}
          value={filters.bu}
          onChange={(v) => handleChange('bu', v)}
          style={{ width: '100%' }}
          allowClear
        />

        <Select
          placeholder="Department"
          options={deptOptions}
          onChange={(v) => handleChange('dept', v)}
          allowClear
          style={{ width: '100%' }}
        />

        <Select
          placeholder="Client"
          options={clientOptions}
          onChange={(v) => handleChange('client', v)}
          allowClear
          style={{ width: '100%' }}
        />

        <Select
          placeholder="Hiring Manager"
          options={managerOptions}
          onChange={(v) => handleChange('manager', v)}
          allowClear
          style={{ width: '100%' }}
        />
        <Select
          placeholder="Recruiter"
          options={recruiterOptions}
          onChange={(v) => handleChange('recruiter', v)}
          allowClear
          style={{ width: '100%' }}
        />

        <Select
          placeholder="Location"
          options={locationOptions}
          onChange={(v) => handleChange('location', v)}
          allowClear
          style={{ width: '100%' }}
        />

        <Select
          placeholder="Priority"
          options={priorityOptions}
          onChange={(v) => handleChange('priority', v)}
          allowClear
          style={{ width: '100%' }}
        />

        <Select
          placeholder="Aging Range"
          options={agingOptions}
          onChange={(v) => handleChange('aging', v)}
          allowClear
          style={{ width: '100%' }}
        />

        <Button type="primary" onClick={onClose}>
          Apply Filters
        </Button>
      </Space>
    </Drawer>
  );
};

export default FIlterDrawer;
