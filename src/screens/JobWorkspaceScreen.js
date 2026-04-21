import { useMemo, useState } from "react";
import { Button, Input, StatusBadge, Table } from "../components/ui";
import FilterDrawers from "../components/ui/FilterDrawers";
import Toolbar from "../components/ui/Toolbar";
import mockData from "../utils/mockData";
import TableView from "../components/ui/TableView";
import ReactMarkdown from "react-markdown";

const TABS = [
  "Checklist",
  "Dashboard",
  "Candidates",
  "Job Info",
  "Hiring Setup",
  "Workflow Automation",
  "Publish Options",
];

const getStageLabel = (candidate) => {
  const status = String(candidate?.pipelineStatus || candidate?.status || "")
    .trim()
    .toLowerCase();
  if (status.includes("screen")) return "Recruiter Screening";
  if (status.includes("l1") || status.includes("interview"))
    return "L1 Interview";
  if (status.includes("pre")) return "Preboarding";
  if (status.includes("hire") || status.includes("onboard")) return "Hired";
  if (status.includes("archive") || status.includes("reject"))
    return "Archived";
  return "Sourced";
};

const STAGES = [
  "Sourced",
  "Recruiter Screening",
  "L1 Interview",
  "Preboarding",
  "Hired",
  "Archived",
];

export default function JobWorkspaceScreen({
  job,
  candidates = [],
  onAddCandidate,
  onOpenCandidate,
}) {
  const [activeTab, setActiveTab] = useState("Candidates");
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [experienceFilter, setExperienceFilter] = useState("");
  const [salaryFilter, setSalaryFilter] = useState("");
  const [joinDaysFilter, setJoinDaysFilter] = useState("");
  const [selectedStage, setSelectedStage] = useState("All");
  const [view, setView] = useState("table");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [filters, setFilters] = useState({});
  const [searchText, setSearchText] = useState("");

  const normalizedTitle = String(job?.title || "")
    .trim()
    .toLowerCase();
  const jobCandidates = useMemo(() => {
    if (!normalizedTitle) return candidates;
    const matched = candidates.filter((c) =>
      String(c?.jobTitle || "")
        .trim()
        .toLowerCase()
        .includes(normalizedTitle),
    );
    return matched.length ? matched : candidates;
  }, [candidates, normalizedTitle]);

  const stageCounts = useMemo(() => {
    const counts = Object.fromEntries(STAGES.map((s) => [s, 0]));
    jobCandidates.forEach((c) => {
      const stage = getStageLabel(c);
      counts[stage] = (counts[stage] || 0) + 1;
    });
    return counts;
  }, [jobCandidates]);

  const visibleCandidates = useMemo(() => {
    return jobCandidates.filter((c) => {
      const stage = getStageLabel(c);
      const q = query.trim().toLowerCase();
      const matchesQuery =
        !q ||
        String(c?.name || "")
          .toLowerCase()
          .includes(q) ||
        String(c?.email || "")
          .toLowerCase()
          .includes(q) ||
        String(c?.phone || "")
          .toLowerCase()
          .includes(q);
      const matchesStage = selectedStage === "All" || stage === selectedStage;
      const matchesSource =
        !sourceFilter ||
        String(c?.source || "")
          .toLowerCase()
          .includes(sourceFilter.toLowerCase());
      const matchesExp =
        !experienceFilter ||
        String(c?.experience || "")
          .toLowerCase()
          .includes(experienceFilter.toLowerCase());
      const matchesSalary =
        !salaryFilter ||
        String(c?.expectedSalary || "")
          .toLowerCase()
          .includes(salaryFilter.toLowerCase());
      const matchesJoinDays =
        !joinDaysFilter ||
        String(c?.joiningDate || "")
          .toLowerCase()
          .includes(joinDaysFilter.toLowerCase());
      return (
        matchesQuery &&
        matchesStage &&
        matchesSource &&
        matchesExp &&
        matchesSalary &&
        matchesJoinDays
      );
    });
  }, [
    jobCandidates,
    query,
    selectedStage,
    sourceFilter,
    experienceFilter,
    salaryFilter,
    joinDaysFilter,
  ]);

  const filteredData = mockData.filter(item => {
    const matchSearch =
      item.title.toLowerCase().includes(searchText.toLowerCase()) ||
      item.id.includes(searchText);

    const matchStatus =
      !filters.status || item.status === filters.status;

    const matchType =
      !filters.type || item.type === filters.type;

    return matchSearch && matchStatus && matchType;
  });

  const handleSearch = (value) => {
    setSearchText(value);
  };

  const handleReset = () => {
    setFilters({});
    setSearchText('');
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xl font-bold text-slate-900">
              {job?.title || "Job Workspace"}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {job?.location || "—"} - {job?.experienceLevel || "—"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={job?.status || "Open"} />
            <Button onClick={onAddCandidate}>+ Add Candidate</Button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border bg-white px-2 py-2 shadow-sm">
        <div className="flex min-w-max items-center gap-1">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`rounded-lg px-3 py-2 text-xs font-semibold ${
                activeTab === tab
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "Candidates" ? (
        <>
          <div className="grid gap-2 rounded-2xl border bg-white p-3 shadow-sm md:grid-cols-6">
            {STAGES.map((stage) => (
              <button
                key={stage}
                type="button"
                onClick={() => setSelectedStage(stage)}
                className={`rounded-xl border px-3 py-2 text-left ${
                  selectedStage === stage
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "bg-slate-50"
                }`}
              >
                <div className="text-xs">{stage}</div>
                <div className="text-lg font-bold">
                  {stageCounts[stage] || 0}
                </div>
              </button>
            ))}
          </div>

          <div className="rounded-2xl border bg-white p-3 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Button
                variant={selectedStage === "All" ? "primary" : "secondary"}
                onClick={() => setSelectedStage("All")}
              >
                All Candidates
              </Button>
              <Input
                label="Source"
                value={sourceFilter}
                onChange={setSourceFilter}
              />
              <Input
                label="Experience"
                value={experienceFilter}
                onChange={setExperienceFilter}
              />
              <Input
                label="Expected Salary"
                value={salaryFilter}
                onChange={setSalaryFilter}
              />
              <Input
                label="Available To Join (Days)"
                value={joinDaysFilter}
                onChange={setJoinDaysFilter}
              />
              <Input
                label="Search"
                value={query}
                onChange={setQuery}
                placeholder="Name/email/phone"
              />
            </div>

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
              rows={visibleCandidates.map((c) => ({
                candidate: (
                  <button
                    className="font-semibold text-blue-700 hover:underline"
                    onClick={() => onOpenCandidate?.(c.id)}
                  >
                    {c.name}
                  </button>
                ),
                source: c.source || "LinkedIn",
                applied: c.createdAt || "—",
                owner:
                  c.assignedHrManagerId || c.assignedReportManagerId || "—",
                stage: <StatusBadge status={getStageLabel(c)} />,
                contact: (
                  <div className="text-xs">
                    <div>{c.phone || "—"}</div>
                    <div className="text-slate-500">{c.email || "—"}</div>
                  </div>
                ),
                actions: <span className="text-xs text-slate-500">•••</span>,
              }))}
            />
          </div>
        </>
      ) : activeTab === "Job Info" ? (
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="mb-3 text-lg font-bold text-slate-900">
            Job Description
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border bg-slate-50 p-3">
              <div className="text-xs font-semibold text-slate-500">Job ID</div>
              <div className="mt-1 text-sm font-semibold text-slate-900">
                {job?.id || "—"}
              </div>
            </div>
            <div className="rounded-xl border bg-slate-50 p-3">
              <div className="text-xs font-semibold text-slate-500">
                Job Title
              </div>
              <div className="mt-1 text-sm font-semibold text-slate-900">
                {job?.title || "—"}
              </div>
            </div>
          </div>
          <div className="mt-4 rounded-xl border bg-white p-4">
            <div className="mb-2 text-xs font-semibold text-slate-500">
              Description
            </div>
            <div className="whitespace-pre-wrap text-sm leading-6 text-slate-700">
              <ReactMarkdown>
              {job?.jobDescription || "No job description available."}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      ) : activeTab === "Dashboard" ? (
        <>
          <div className="rounded-2xl border bg-white p-6 shadow-sm">
            <div className="mb-3 text-lg font-bold text-slate-900">
              Job Dashboard
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="flex justify-between items-center rounded-xl border bg-slate-50 p-3">
                <div className="flex-col">
                  <div className="text-xs font-semibold text-slate-500">
                    My Open Jobs
                  </div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">
                    {job?.id || "—"}
                  </div>
                </div>
                <div>12</div>
              </div>
              <div className="rounded-xl border bg-slate-50 p-3">
                <div className="text-xs font-semibold text-slate-500">
                  My Aging Jobs
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-900">
                  {job?.title || "—"}
                </div>
              </div>
              <div className="rounded-xl border bg-slate-50 p-3">
                <div className="text-xs font-semibold text-slate-500">
                  Critical Jobs
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-900">
                  {job?.title || "—"}
                </div>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border bg-white p-6 shadow-sm">
            <Toolbar
              view={view}
              setView={setView}
              setDrawerOpen={setDrawerOpen}
              onSearch={handleSearch}
              onReset={handleReset}
            />
            <FilterDrawers
              open={drawerOpen}
              onClose={() => setDrawerOpen(false)}
              filters={filters}
              setFilters={setFilters}
            />
            <TableView data={filteredData} />
          </div>
        </>
      ) : (
        <div className="rounded-2xl border bg-white p-6 text-sm text-slate-600 shadow-sm">
          {activeTab} section will be wired next.
        </div>
      )}
    </div>
  );
}
