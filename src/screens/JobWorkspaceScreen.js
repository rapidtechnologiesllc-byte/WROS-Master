import { useEffect, useMemo, useState } from "react";
import { Button, Input, StatusBadge, Table } from "../components/ui";
import FilterDrawers from "../components/ui/FilterDrawers";
import Toolbar from "../components/ui/Toolbar";
import mockData from "../utils/mockData";
import TableView from "../components/ui/TableView";
import ReactMarkdown from "react-markdown";
import { candidateAppendedJob, removeCandidateApi } from "../services/api/jobs";
import CandidateEditModal from "./CandidateEditModal";
import AssignJobModal from "./AssignJobModal";
import CandidateAssignJobModal from "./CandidateAssignJobModal";
import { toast } from "react-toastify";
import { getCandidateById } from "../services/api/candidates";
import { UserMinus } from "lucide-react";
import MoveStageDrawer from "../components/ui/MoveStageDrawer";

const TABS = ["Candidates", "Job Info", "Job Analytics"];

const getStageLabel = (candidate) => {
  const status = String(candidate?.pipelineStatus || candidate?.status || "")
    .trim()
    .toLowerCase();
  if (status.includes("screen")) return "Recruiter Screening";
  if (status.includes("l1") || status.includes("interview"))
    return "L1 Interview";
  if (status.includes("pre")) return "Pre-Onboarding";
  if (status.includes("hire") || status.includes("onboard")) return "Hired";
  if (status.includes("archive") || status.includes("reject"))
    return "Archived";
  return "Sourced";
};

const STAGES = [
  "Sourced",
  "Recruiter Screening",
  "L1 Interview",
  "Pre-Onboarding",
  "Hired",
  "Archived",
];

const jobStages = [
  "Upcomming Interviews",
  "Time to Hire",
  "Offer Acceptance Rate",
  "Closed/Total Position",
];

const pipeline = [
  { count: 5, label: "Sourced" },
  { count: 2, label: "Screening" },
  { count: 3, label: "Interview" },
  { count: 0, label: "Pre-Onboarding" },
  { count: 1, label: "Hired" },
  { count: 0, label: "Archived" },
];

export default function JobWorkspaceScreen({
  job,
  candidates = [],
  onAddCandidate,
  onOpenCandidate,
  onFetchCandidateById,
  setSelectedCandidate,
  setScreen,
  setSelectedCandidateId,
  setCandidateDetailsDefaultTab,
  setAutoOpenSchedule,
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
  const [loading, setLoading] = useState(false);
  const [finalCandidates, setFinalCandidates] = useState([]);
  const [assignModal, setAssignModal] = useState(false);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [openMoveDrawer, setOpenMoveDrawer] = useState(false);
  const [showSubmitJobModal, setShowSubmitJobModal] = useState(false);
  const [selectedJobForSubmission, setSelectedJobForSubmission] =
    useState(null);

  const fetchCandidateJob = async () => {
    try {
      setLoading(true);

      const result = await candidateAppendedJob(job?.id);
      const applications = result?.applications || [];

      const enrichedCandidates = await Promise.all(
        applications.map(async (app) => {
          try {
            const candidateDetails = await getCandidateById(app?.candidate_id);

            return {
              ...app,
              candidate: candidateDetails,
            };
          } catch (err) {
            console.log(`Error fetching candidate ${app?.candidate_id}`, err);

            return {
              ...app,
              candidate: null,
            };
          }
        }),
      );

      setFinalCandidates(enrichedCandidates);
      setLoading(false);
    } catch (err) {
      console.log(err);
    }
  };
  useEffect(() => {
    if (!job?.id) return;
    fetchCandidateJob();
  }, [job?.id]);

  const normalizedTitle = String(job?.title || "")
    .trim()
    .toLowerCase();

  const formatDate = (date) => {
    if (!date) return "—";
    return new Date(date).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  const normalizedCandidates = useMemo(() => {
    return finalCandidates.map((c) => ({
      id: c.candidate_id,
      name: `${c?.candidate?.candidate_name || ""} ${c.candidate_last_name || ""}`.trim(),
      email: c?.candidate?.candidate_email,
      phone: c?.candidate?.candidate_mobile,
      experience: c.candidate_experience,
      location: c.candidate_current_location,
      source: "API",
      createdAt: "—",
      status: c.status || c?.candidate?.pipline_status || "Sourced",
      pipelineStatus: c?.candidate?.pipline_status || c.status || "Sourced",
      createdAt: formatDate(c.applied_at),
    }));
  }, [finalCandidates]);

  const jobCandidates = useMemo(() => {
    if (!normalizedTitle) return normalizedCandidates;
    const matched = normalizedCandidates.filter((c) =>
      String(c?.jobTitle || "")
        .toLowerCase()
        .includes(normalizedTitle),
    );
    return matched.length ? matched : normalizedCandidates;
  }, [normalizedCandidates, normalizedTitle]);

  const stageCounts = useMemo(() => {
    const counts = Object.fromEntries(STAGES.map((s) => [s, 0]));
    jobCandidates.forEach((c) => {
      const stage = getStageLabel(c);
      counts[stage] = (counts[stage] || 0) + 1;
    });
    return counts;
  }, [jobCandidates]);

  const jobAnalyticsPipeline = useMemo(() => {
    return pipeline.map((item) => ({
      ...item,
      count: stageCounts[item.label] || 0,
    }));
  }, [pipeline, stageCounts]);

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

  const filteredData = mockData.filter((item) => {
    const matchSearch =
      item.title.toLowerCase().includes(searchText.toLowerCase()) ||
      item.id.includes(searchText);

    const matchStatus = !filters.status || item.status === filters.status;

    const matchType = !filters.type || item.type === filters.type;

    return matchSearch && matchStatus && matchType;
  });

  const handleSearch = (value) => {
    setSearchText(value);
  };

  const handleReset = () => {
    setFilters({});
    setSearchText("");
  };

  const handleAssignedCandidate = (candidate) => {
    setFinalCandidates((prev) => {
      const exists = prev.some((c) => c.candidate_id === candidate.id);
      if (exists) {
        return prev.map((c) =>
          c.candidate_id === candidate.id
            ? {
                ...c,
                status: "Assigned",
                pipelineStatus: "Assigned",
              }
            : c,
        );
      }

      return [
        ...prev,
        {
          candidate_id: candidate.id,
          candidate_first_name: candidate.name?.split(" ")[0],
          candidate_last_name: candidate.name?.split(" ")[1] || "",
          candidate_email: candidate.email,
          candidate_mobile: candidate.phone,
          status: "Assigned",
          pipelineStatus: "Assigned",
        },
      ];
    });
  };

  const removeCandidateHandler = async (candidateId) => {
    if (!candidateId) {
      toast.error("Invalid Candidate");
      return;
    }
    try {
      const result = await removeCandidateApi(job?.id, candidateId);
      if (result?.status === 200) {
        toast.success("Candidate Removed");
        setFinalCandidates((prev) =>
          prev.filter((c) => c.candidate_id !== candidateId),
        );
      } else {
        toast.error("Failed to remove candidate");
      }
    } catch (err) {
      toast.error("Error Occured");
    }
  };

  const handleActiveStatus = async (status, candidateId) => {
    try {
      const result = await updateCandidateStatus(candidateId, {
        status: status,
      });
      if (result?.status === "success") {
        toast.success(`Candidate ${result?.data?.candidate_name} is Archvied`);
        const candidateStatus = await getCandidateStatus(candidateId);
        setCandidateList((prev) =>
          prev.map((c) =>
            c.id === candidateId
              ? {
                  ...c,
                  accountStatus: candidateStatus?.status,
                  pipelineStatus: candidateStatus?.pipeline_status,
                }
              : c,
          ),
        );
      }
    } catch (err) {}
  };

  const handleCandidateStatus = async (candidateId) => {
    try {
      const result = await updateCandidateStatus(candidateId, {
        status: "Active",
        pipeline_status: "Pre-Onboarding",
      });
      if (result?.status === "success") {
        toast.success(
          `Candidate ${result?.data?.candidate_name} moved to Pre-Onboarding`,
        );
        const candidateStatus = await getCandidateStatus(candidateId);
        setCandidateList((prev) =>
          prev.map((c) =>
            c.id === candidateId
              ? {
                  ...c,
                  accountStatus: candidateStatus?.status,
                  pipelineStatus: candidateStatus?.pipeline_status,
                }
              : c,
          ),
        );
      }
    } catch (err) {
      toast.error(err);
      console.log(err);
    }
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
            <Button
              onClick={() => {
                setSelectedJobForSubmission(job);
                setShowSubmitJobModal(true);
              }}
            >
              + Submit Candidate
            </Button>
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
          {showSubmitJobModal && (
            <CandidateAssignJobModal
              onClose={() => setShowSubmitJobModal(false)}
              selectedJob={selectedJobForSubmission}
              allCandidates={candidates}
              onAssignSuccess={fetchCandidateJob}
            />
          )}
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
            {loading ? (
              <div className="p-4 text-sm text-gray-500">
                Loading candidates...
              </div>
            ) : visibleCandidates.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-center text-gray-500">
                <div className="text-lg font-semibold">
                  No candidates available
                </div>
                <div className="text-sm mt-1">
                  There are no candidates for this job yet.
                </div>

                <button
                  onClick={onAddCandidate}
                  className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-white text-sm hover:bg-blue-700"
                >
                  + Add Candidate
                </button>
              </div>
            ) : (
              <Table
                columns={[
                  { key: "candidate", header: "Candidate" },
                  { key: "source", header: "Source" },
                  { key: "applied", header: "Applied / Added On" },
                  { key: "stage", header: "Stage" },
                  { key: "contact", header: "Contact" },
                  { key: "actions", header: "Actions" },
                ]}
                rows={visibleCandidates.map((c) => ({
                  candidate: (
                    <button
                      className="font-semibold text-blue-700 hover:underline"
                      onClick={async () => {
                        onOpenCandidate?.(c.id);
                        let finalCandidate = c;
                        if (onFetchCandidateById) {
                          try {
                            const fresh = await onFetchCandidateById(c.id);
                            if (fresh) {
                              finalCandidate = fresh;
                            }
                          } catch (err) {}
                        }
                        setSelectedCandidate(finalCandidate);
                        setScreen("candidateDetails");
                      }}
                    >
                      {c.name}
                    </button>
                  ),
                  source: c.source || "LinkedIn",
                  applied: c.createdAt || "—",
                  stage: <StatusBadge status={getStageLabel(c)} />,
                  contact: (
                    <div className="text-xs">
                      <div>{c.phone || "—"}</div>
                      <div className="text-slate-500">{c.email || "—"}</div>
                    </div>
                  ),
                  actions: (
                    <div className="relative">
                      <button
                        className="px-2 py-1 text-gray-600 hover:text-black"
                        onClick={() =>
                          setOpenMenuId(openMenuId === c.id ? null : c.id)
                        }
                      >
                        ⋮
                      </button>
                      {openMenuId === c.id && (
                        <div className="absolute right-0 z-10 mt-2 w-56 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg">
                          <button
                            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                            onClick={() => {
                              setSelectedCandidateId(c?.id);
                              setSelectedCandidate(c);
                              setCandidateDetailsDefaultTab?.("profile");
                              setAutoOpenSchedule?.(true);
                              setScreen("candidateDetails");
                              setOpenMenuId(null);
                            }}
                          >
                            Schedule Interview
                          </button>
                          <button
                            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                            onClick={() => {
                              const email = c?.email?.trim();

                              if (!email) {
                                return;
                              }
                              const subject = encodeURIComponent(
                                "Regarding your application",
                              );
                              const body = encodeURIComponent(
                                `Hi ${c?.name || "Candidate"},\n\n`,
                              );
                              const to = encodeURIComponent(email);
                              const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${to}&su=${subject}&body=${body}`;
                              const mailtoUrl = `mailto:${to}?subject=${subject}&body=${body}`;
                              const openedWindow = window.open(
                                gmailUrl,
                                "_blank",
                                "noopener,noreferrer",
                              );
                              if (!openedWindow) {
                                window.location.href = mailtoUrl;
                              }
                              setOpenMenuId(null);
                            }}
                          >
                            Send Email
                          </button>
                          <button
                            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!c?.phone}
                            onClick={() => {
                              if (!c?.phone) return;
                              const cleanedPhone = c.phone.replace(/\D/g, "");
                              if (!cleanedPhone) {
                                return;
                              }
                              window.open(
                                `https://wa.me/${cleanedPhone}`,
                                "_blank",
                              );
                              setOpenMenuId(null);
                            }}
                          >
                            Message on WhatsApp
                          </button>
                          <button
                            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                            onClick={async () => {
                              setSelectedCandidateId(c.id);
                              let finalCandidate = c;
                              if (onFetchCandidateById) {
                                try {
                                  const fresh = await onFetchCandidateById(
                                    c.id,
                                  );
                                  if (fresh) {
                                    finalCandidate = fresh;
                                  }
                                } catch (err) {}
                              }
                              setSelectedCandidate(finalCandidate);
                              setCandidateDetailsDefaultTab?.("feedback");
                              setScreen("candidateDetails");
                              setOpenMenuId(null);
                            }}
                          >
                            Add Feedback
                          </button>
                          <button
                            className="block w-full px-4 py-3 text-left text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                            onClick={() => {
                              handleActiveStatus("Inactive", c?.id);
                            }}
                          >
                            Archive
                          </button>
                          <button
                            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                            onClick={() => {
                              handleCandidateStatus(c?.id);
                              setOpenMenuId(null);
                            }}
                          >
                            Pre Onboarding
                          </button>
                          <button
                            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                            onClick={() => {
                              setOpenMoveDrawer(true);
                            }}
                          >
                            Move Stage
                          </button>
                          <MoveStageDrawer
                            open={openMoveDrawer}
                            onClose={() => setOpenMoveDrawer(false)}
                            onSubmit={(stage) => {
                              setCandidateList((prev) =>
                                prev.map((c) =>
                                  c.id === stage?.candidate_id
                                    ? {
                                        ...c,
                                        status: stage?.status,
                                        pipelineStatus: stage?.pipeline_status,
                                      }
                                    : c,
                                ),
                              );
                            }}
                            data={c}
                          />
                        </div>
                      )}
                    </div>
                  ),
                }))}
              />
            )}
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
      ) : activeTab === "Job Analytics" ? (
        <>
          <div className="grid gap-2 rounded-2xl border bg-white p-3 shadow-sm md:grid-cols-4">
            {jobStages.map((stage) => (
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

          <div className="rounded-2xl border bg-white p-6 text-sm text-slate-600 shadow-sm">
            <div className="flex justify-between item-center">
              <span className="font-bold">Candidate Pipeline</span>
            </div>
            <div className="flex item-center justify-between gap-100 pt-4">
              {jobAnalyticsPipeline.map((item, index) => (
                <div
                  key={index}
                  className={`flex flex-col items-center justify-center ${
                    index !== 0 ? "pt-15" : ""
                  }`}
                >
                  <div>{item.count}</div>
                  <div>{item.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div class="w-full rounded-xl border bg-gray-50 p-6 text-sm text-gray-700 shadow-sm">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="font-bold">Pending review</span>
                <span class="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-600">
                  New
                </span>
                <span class="text-gray-400 cursor-pointer">ⓘ</span>
              </div>
              <div class="flex items-center gap-1 text-blue-500 text-sm cursor-pointer"></div>
            </div>

            <div class="mt-4">
              <span class="text-3xl font-semibold text-blue-600">0</span>
              <span class="ml-2 text-gray-500 text-sm">(Last 3 months)</span>
            </div>
            <div class="mt-6 flex items-center gap-6 text-sm text-gray-600">
              <div class="flex items-center gap-2">
                <span class="h-3 w-3 rounded-full bg-purple-400"></span>
                <span>Sourced (0)</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="h-3 w-3 rounded-full bg-teal-400"></span>
                <span>Screening (0)</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="h-3 w-3 rounded-full bg-yellow-400"></span>
                <span>Interview (0)</span>
              </div>
            </div>
          </div>

          <div class="w-full rounded-xl border bg-gray-50 p-6 text-sm text-gray-700 shadow-sm">
            <div class="flex items-center justify-between">
              <h2 class="font-bold">Hiring team</h2>
            </div>
            <div class="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <p class="text-gray-500 text-sm">Recruiters</p>
                <p class="mt-2 text-gray-700 font-medium">
                  {job?.contactPerson || "-"}
                </p>
              </div>
              <div>
                <p class="text-gray-500 text-sm">Hiring managers</p>
                <div class="mt-2 flex items-center gap-2">
                  {/* <div class="flex h-6 w-6 items-center justify-center rounded-full bg-purple-500 text-white text-xs font-semibold">
                    GA
                  </div> */}
                  <span class="text-gray-800 text-sm">
                    {job?.hiringManagerName || "-"}
                  </span>
                </div>
              </div>
              <div class="text-left md:text-right">
                <p class="text-gray-500 text-sm">Interview panel members</p>
                <p class="mt-2 text-gray-700 font-medium">NA</p>
              </div>
            </div>
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
