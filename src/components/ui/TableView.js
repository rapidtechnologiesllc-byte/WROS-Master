import React, { useEffect, useMemo, useState } from "react";
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
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = searchText?.trim()?.toLowerCase();
    if (!q) return job;
    return job?.filter((c) => c?.title?.toLowerCase()?.includes(q));
  }, [job, searchText]);

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
          id: item?.job_id,
          title: item?.job_title,
          companyType: item?.company_type || item?.positionType || "Full Time",
          clientName: item?.company_name || item?.companyName || "-",
          dept: item?.department_name || item?.dept || (item?.department_id ? `Dept ${item?.department_id}` : "-"),
          location: item?.job_location,
          hiringManagerName: item?.hiring_manager_name || item?.hiringManager || item?.hiring_manager_id || "-",
          openPositions: item?.no_of_positions,
          experienceLevel: item?.job_experience,
          status: item?.job_status || item?.jobStatus || "Draft",
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
      title: "Client",
      dataIndex: "clientName",
      render: (val, record) => <span>{val || record?.dept || "-"}</span>,
    },
    { title: "Location", dataIndex: "location" },
    {
      title: "Hiring Manager",
      dataIndex: "hiringManagerName",
      render: (val) => <Tag>{val}</Tag>,
    },
    { title: "Experience Level", dataIndex: "experienceLevel" },
    {
      title: "Status",
      dataIndex: "status",
      render: (val) => (
        <Tag color={val === "Open" ? "green" : "default"}>{val}</Tag>
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
      {view === "table" ? (
        <Table
          columns={columns}
          dataSource={filtered ? filtered : tableData}
          pagination={false}
          rowKey="id"
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(filtered || tableData)?.map((job) => (
            <div
              key={job?.id}
              className="rounded-lg border border-gray-200 bg-white p-4 hover:shadow-md transition cursor-pointer"
              onClick={() => (onViewJob ? onViewJob(job?.id) : onOpenJob(job?.id))}
            >
              <h3 className="font-semibold text-gray-900">{job?.title}</h3>
              <p className="text-sm text-gray-600 mt-1">{job?.location}</p>
              <div className="mt-3 flex justify-between text-xs">
                <span className="text-gray-600">Type: {job?.companyType || "-"}</span>
                <span className="text-gray-600">Exp: {job?.experienceLevel}</span>
              </div>
              <div className="mt-2 text-xs">
                <p className="text-gray-600">Manager: {job?.hiringManagerName}</p>
                <p className="text-gray-600 mt-1">Status: <span className={job?.status === "Open" ? "text-green-600 font-semibold" : ""}>{job?.status}</span></p>
              </div>
            </div>
          ))}
        </div>
      )}
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
