import React, { useEffect, useState } from "react";
import { Table, Tag, Dropdown } from "antd";
import { MoreOutlined } from "@ant-design/icons";
import Toolbar from "./Toolbar";
import FIlterDrawer from "./FilterDrawers";
import { jobsFilter } from "../../services/api/jobs";

const TableView = ({ job, onViewJob, onOpenJob }) => {
  const [view, setView] = useState("table");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [filters, setFilters] = useState({});
  const [searchText, setSearchText] = useState("");
  const [appliedFilters, setAppliedFilters] = useState({});
  const [tableData, setTableData] = useState(job || []);

  const handleReset = () => {
    setFilters({});
    setAppliedFilters({});
    setSearchText("");
    setTableData(job || []);
  };

  const handleSearch = (value) => {
    setSearchText(value);
  };

  const buildQueryParams = (filters) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (!value || (Array.isArray(value) && value.length === 0)) return;
      const lowerKey = key.toLowerCase();
      if (Array.isArray(value)) {
        value.forEach((v) => params.append(lowerKey, String(v).toLowerCase()));
      } else {
        params.append(lowerKey, String(value).toLowerCase());
      }
    });
    return params.toString();
  };

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const query = buildQueryParams({
          ...appliedFilters,
          search: searchText,
        });

        const result = await jobsFilter(query);
        const formattedJobs = result?.jobs?.map((item) => ({
          id: item.job_id,
          title: item.job_title,
          companyType: item.company_type,
          dept: item.department_id || "-",
          location: item.job_location,
          hiringManagerName: item.hiring_manager_id || "-",
          openPositions: item.no_of_positions,
          experienceLevel: item.job_experience,
          status: item.job_status,
        }));

        setTableData(formattedJobs || []);
      } catch (err) {
        console.error("API ERROR:", err);
      }
    };

    fetchJobs();
  }, [appliedFilters, searchText]);

  useEffect(() => {
    if (job?.length) {
      setTableData(job);
    }
  }, [job]);

  const columns = [
    {
      title: "Title",
      dataIndex: "title",
      render: (text, record) => (
        <span
          onClick={() =>
            onViewJob ? onViewJob(record?.id) : onOpenJob(record?.id)
          }
          style={{ color: "#1890ff", cursor: "pointer" }}
        >
          {text}
        </span>
      ),
    },
    {
      title: "Type",
      dataIndex: "companyType",
      render: (val) => <Tag color="blue">{val}</Tag>,
    },
    { title: "Client / Dept", dataIndex: "dept" },
    { title: "Location", dataIndex: "location" },
    {
      title: "Hiring Manager",
      dataIndex: "hiringManagerName",
      render: (val) => <Tag>{val}</Tag>,
    },
    { title: "Open", dataIndex: "openPositions" },
    { title: "Experience Level", dataIndex: "experienceLevel" },
    {
      title: "Status",
      dataIndex: "status",
      render: (val) => (
        <Tag color={val === "Open" ? "green" : "default"}>{val}</Tag>
      ),
    },

    {
      title: "",
      render: () => (
        <Dropdown
          menu={{
            items: [
              { key: "1", label: "Edit" },
              { key: "2", label: "Delete" },
            ],
          }}
        >
          <MoreOutlined style={{ cursor: "pointer" }} />
        </Dropdown>
      ),
    },
  ];

  return (
    <div style={wrapper}>
      <Toolbar
        view={view}
        setView={setView}
        setDrawerOpen={setDrawerOpen}
        onSearch={handleSearch}
        onReset={handleReset}
      />
      <FIlterDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        filters={filters}
        setFilters={setFilters}
        onApply={() => {
          setAppliedFilters(filters);
          setDrawerOpen(false);
        }}
      />
      <Table
        columns={columns}
        dataSource={tableData}
        pagination={false}
        rowKey="id"
      />
    </div>
  );
};

const wrapper = {
  background: "#fff",
  padding: 12,
  borderRadius: 8,
  border: "1px solid #f0f0f0",
};

export default TableView;
