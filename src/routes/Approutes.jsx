import { useCallback, useEffect, useMemo, useState } from "react";
import Dashboard from "../screens/Dashboard";
import Documents from "../screens/Documents";
import ActiveJobs from "../screens/ActiveJobs";
import InterviewSchedule from "../screens/InterviewSchedule";
import InterviewStatus from "../screens/InterviewStatus";
import InterviewAnalytics from "../screens/InterviewAnalytics";
import HrUserManagement from "../screens/HrUserManagement";
import JobCreate from "../screens/JobCreate";
import JobDetails from "../screens/JobDetails";
import JobsOverview from "../screens/JobsOverview";
import JobWorkspaceScreen from "../screens/JobWorkspaceScreen";
import MatchingJobs from "../screens/MatchingJobs";
import NewsletterScreen from "../screens/NewsletterScreen";
import OfferScreen from "../screens/OfferScreen";
import PreOnboarding from "../screens/PreOnboardingOld";
import PreOnboardingPage from "../screens/PreOnboarding";
import ChecklistTemplatesScreen from "../screens/ChecklistTemplatesScreen";
import RbacSettingsScreen from "../screens/RbacSettingsScreen";
import Verification from "../screens/Verification";
import MyWorkspace from "../screens/MyWorkspace";
import { getAllInterviews, updateInterview } from "../services/api/interviews";
import {
  getAllCandidates,
  getCandidateById,
  updateCandidate,
  deleteCandidate,
} from "../services/api/candidates";
import {
  approveJob,
  deleteJob,
  getAllJobs,
  updateJob,
  postJobOnLinkedIn,
} from "../services/api/jobs";
import { applyForJob } from "../services/api/jobs";
import {
  createOfferLetter,
  getAllOffers,
  getOfferById,
  updateOfferLetter,
  cancelOfferLetter,
} from "../services/api/offerLetters";
import { getAllUsers } from "../services/api/users";
import {
  getAllCandidateStatuses,
  updateCandidateStatus,
} from "../services/api/candidateStatus";
import CandidateDetailsScreen from "../screens/CandidateDetailsScreen";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import OfferListing from "../screens/OfferListing";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import AuthPage from "../pages/AuthPage";
import Shell from "../layout/Shell";
import AssignmentsScreen from "../screens/AssignmentsScreen";
import CandidateCreate from "../screens/CandidateCreate";
import CandidateSearch from "../screens/CandidateSearch";
import CandidateSelfService from "../screens/CandidateSelfService";
import { canAccessMyWorkspace, isCandidateUser } from "../utils/permissions";
import { useNavigate } from "react-router-dom";
import CandidateDetailsWrapper from "./wrappers/CandidateDetailsWrapper";
import JobWorkspaceWrapper from "./wrappers/JobWorkspaceWrapper";
import { ROUTES } from "../utils/Routes";
import OfferLettersScreen from "../screens/OfferLettersScreen";
import ThunderChatScreen from "../screens/ThunderChatScreen";
import ResourceManagementScreen from "../screens/ResourceManagementScreen";
import CorePullScreen from "../screens/CorePullScreen";
import DemandConfirmationScreen from "../screens/DemandConfirmationScreen";
import EmployeeDirectoryScreen from "../screens/EmployeeDirectoryScreen";
import SubmissionsScreen from "../screens/SubmissionsScreen";
import AllocationsScreen from "../screens/AllocationsScreen";
import ProjectsScreen from "../screens/ProjectsScreen";
import HtdIntakeScreen from "../screens/HtdIntakeScreen";
import HmCandidateReviewScreen from "../screens/HmCandidateReviewScreen";
import UtilizationDashboardScreen from "../screens/UtilizationDashboardScreen";
import TimesheetsScreen from "../screens/TimesheetsScreen";
import ForecastScreen from "../screens/ForecastScreen";
import InvoicesScreen from "../screens/InvoicesScreen";
import RevenueScreen from "../screens/RevenueScreen";
import TenantLocaleScreen from "../screens/TenantLocaleScreen";
import PublicThunderChatScreen from "../screens/PublicThunderChatScreen";
import CandidatePortalScreen from "../screens/CandidatePortalScreen";
import MessageTemplatesScreen from "../screens/MessageTemplatesScreen";
import InterventionQueueScreen from "../screens/InterventionQueueScreen";
import RiskDashboardScreen from "../screens/RiskDashboardScreen";
import ThunderAnalyticsScreen from "../screens/ThunderAnalyticsScreen";
import BulkLaunchScreen from "../screens/BulkLaunchScreen";
import TenantAIConfigScreen from "../screens/TenantAIConfigScreen";
import MyTasksScreen from "../screens/MyTasksScreen";
import MyTimesheetScreen from "../screens/MyTimesheetScreen";
import TicketRoutingAdminScreen from "../screens/TicketRoutingAdminScreen";
import BuddyProgramListScreen from "../screens/BuddyProgramListScreen";
import BuddyProgramScreen from "../screens/BuddyProgramScreen";
import ExecutiveSignalScreen from "../screens/ExecutiveSignalScreen";
import ErrorLogScreen from "../screens/ErrorLogScreen";
import AdminSettingsScreen from "../screens/AdminSettingsScreen";
import ConversationSearchBar from "../components/ConversationSearchBar";
import SLABreachBanner from "../components/SLABreachBanner";

const mapCandidateFromApi = (c) => {
  const parseSkills = (raw) => {
    if (!raw) return [];
    if (Array.isArray(raw))
      return raw.map((s) => String(s).trim()).filter(Boolean);
    return String(raw)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  };

  return {
    id: c.candidate_id,
    name: c.candidate_name,
    email: c.candidate_email,
    phone: c.candidate_mobile || "",
    skills: parseSkills(c.candidate_skills),
    status: c.candidate_is_verified ? "Verified" : "New",
    jobTitle: c.candidate_job_title || "",
    gender: c.candidate_gender || "",
    dob: c.candidate_date_of_birth || "",
    source: c.candidate_source || "",
    experience: c.candidate_experience || "",
    joiningDate: c.candidate_joining_date || "",
    expectedSalary: c.candidate_expected_salary || "",
    currentSalary: c.candidate_current_salary || "",
    currentLocation: c.candidate_current_location || "",
    assignedHrManagerId: c.assigned_hr_manager_id || "",
    assignedReportManagerId: c.assigned_report_manager_id || "",
    pipelineStatus: c.pipline_status || c.pipeline_status || "",
    accountStatus: c.status || "",
  };
};

const mergeCandidateStatuses = (candidates, statusRes) => {
  const rows = statusRes?.candidates || [];
  const byId = new Map(rows.map((r) => [r.candidate_id, r]));
  return candidates.map((c) => {
    const s = byId.get(c.id);
    if (!s) return c;
    return {
      ...c,
      pipelineStatus: s.pipeline_status || c.pipelineStatus || "",
      accountStatus: s.status || c.accountStatus || "",
    };
  });
};

export const mapJobFromApi = (j, users = []) => {
  const usersList = Array.isArray(users) ? users : [];
  const hmId = j?.hiring_manager_id || "";
  const hmUser = usersList.find(
    (u) => String(u?.user_id || "") === String(hmId || ""),
  );
  const hiringManagerName =
    hmUser?.user_name || hmUser?.user_email || (hmId ? String(hmId) : "");

  return {
    id: j.job_id,
    title: j.job_title,
    dept: "",
    location: j.job_location || "",
    skills: String(j.job_skills || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    hiringManager: hmId,
    hiringManagerName,
    status: (() => {
      const raw = String(j.job_status || "")
        .trim()
        .toLowerCase();
      if (raw === "active") return "Open";
      if (raw === "public") return "Public";
      if (raw === "draft") return "Draft";
      if (raw === "submitted") return "Submitted";
      if (raw === "pending_approval") return "Pending Approval";
      if (raw === "closed") return "Closed";
      return j.job_status || "Draft";
    })(),
    experienceLevel: j.job_experience || "",
    companyType: j.company_type || "",
    companyClient: j.company_name || "",
    contactPerson: j.contact_person || "",
    startDate: j.start_date || "",
    endDate: j.end_date || "",
    jobDescription: j.job_description || "",
  };
};

const normalizeJobStatusForApi = (uiStatus) => {
  const raw = String(uiStatus || "").trim();
  const lower = raw.toLowerCase();
  if (lower === "open") return "active";
  if (lower === "public") return "public";
  if (lower === "draft") return "draft";
  if (lower === "submitted") return "submitted";
  if (lower === "closed") return "closed";
  return lower;
};

const normalizeRole = (rawRole) => {
  const upper = String(rawRole || "")
    .trim()
    .toUpperCase();
  if (["SUPER USER", "SUPER_USER", "SUPERUSER"].includes(upper)) {
    return "SUPER_USER";
  }
  if (["ADMIN", "HR", "RECRUITER", "CANDIDATE"].includes(upper)) {
    return upper;
  }
  return upper || "RECRUITER";
};

export default function AppRoutes() {
  // Public, unauthenticated Thunder chat widget -- a real external
  // visitor (careers page / job listing) has no account and never
  // will just to talk to Thunder. Checked before the token gate below,
  // same as /auth's special-casing.
  if (window.location.pathname.startsWith("/careers-chat")) {
    return <PublicThunderChatScreen />;
  }

  // S-017/HRMS-0417 -- Candidate Self-Service Web Portal. The token in
  // the path IS the candidate's auth (a long-lived candidate JWT, see
  // candidate_portal_service's module docstring) -- checked before the
  // internal login gate below, same precedent as /careers-chat, since
  // a candidate arriving via a WhatsApp/Email link has no internal
  // account and must never see the internal login screen.
  if (window.location.pathname.startsWith("/candidate/")) {
    const portalToken = window.location.pathname.split("/candidate/")[1]?.split("/")[0];
    return <CandidatePortalScreen token={portalToken} />;
  }

  const url = new URL(window.location.href);
  const tokenFromQuery = url.searchParams.get("token");
  if (tokenFromQuery) {
    localStorage.setItem("hrms_token", tokenFromQuery);
    if (!localStorage.getItem("hrms_user_type")) {
      localStorage.setItem("hrms_user_type", "employee");
    }
    url.searchParams.delete("token");
    const cleanedUrl = `${url.pathname}${url.search}${url.hash}`;
    window.history.replaceState({}, "", cleanedUrl || "/");
  }

  const token = localStorage.getItem("hrms_token");
  if (!token || window.location.pathname.startsWith("/auth")) {
    return <AuthPage />;
  }

  const storedRole = localStorage.getItem("permission_role");
  const storedUserType = String(localStorage.getItem("hrms_user_type") || "")
    .trim()
    .toLowerCase();
  const normalizedRole = normalizeRole(storedRole);
  const isAdminOrSuperUser =
    normalizedRole === "ADMIN" || normalizedRole === "SUPER_USER";
  const isSuperUser = normalizedRole === "SUPER_USER";

  const handleLogout = () => {
    localStorage.removeItem("hrms_token");
    localStorage.removeItem("hrms_role");
    localStorage.removeItem("hrms_user_name");
    localStorage.removeItem("hrms_user_email");
    localStorage.removeItem("hrms_candidate_id");
    localStorage.removeItem("hrms_user_type");
    window.location.href = "/";
  };

  if (
    isCandidateUser({
      role: storedRole,
      userType: storedUserType,
    })
  ) {
    return <CandidateSelfService onLogout={handleLogout} />;
  }

  const [role, setRole] = useState(normalizedRole);
  const [candidateRecord, setCandidateRecord] = useState(null);
  const [candidates, setCandidates] = useState([]);

  const [jobs, setJobs] = useState([]);
  const [interviews, setInterviews] = useState([]);
  const [offers, setOffers] = useState([]);
  const [users, setUsers] = useState([]);
  const [offerLoading, setOfferLoading] = useState(false);
  const [offerError, setOfferError] = useState("");

  const [selectedCandidateId, setSelectedCandidateId] = useState(
    candidates[0]?.id || "",
  );
  const [selectedJobId, setSelectedJobId] = useState(jobs[0]?.id || "");
  const [jobDetailsMode, setJobDetailsMode] = useState("view");
  const [jobCreateMode, setJobCreateMode] = useState("create");
  const [selectedCandidateData, setSelectedCandidateData] = useState(null);
  const [candidateDetailsDefaultTab, setCandidateDetailsDefaultTab] =
    useState("profile");
  const [autoOpenSchedule, setAutoOpenSchedule] = useState(false);
  const [apiState, setApiState] = useState();
  const navigate = useNavigate();
  const selectedCandidate = useMemo(
    () => candidates.find((c) => c.id === selectedCandidateId) || candidates[0],
    [candidates, selectedCandidateId],
  );

  const selectedJob = useMemo(
    () => jobs.find((j) => j.id === selectedJobId) || jobs[0],
    [jobs, selectedJobId],
  );

  const notify = useCallback((title, message) => {
    alert(`${title}\n\n${message}`);
  }, []);

  const refreshJobs = useCallback(async () => {
    const refreshed = await getAllJobs();
    const mappedJobs = (refreshed?.jobs || []).map((j) =>
      mapJobFromApi(j, users),
    );
    setJobs(mappedJobs);
    if (!selectedJobId && mappedJobs.length) {
      setSelectedJobId(mappedJobs[0].id);
    }
  }, [selectedJobId, users]);

  const mapInterviews = useCallback((interviewRes) => {
    return (interviewRes || []).map((i) => ({
      id: i.id,
      panelId: i.panel_id,
      panelRoundName: i.panel_round_name,
      candidateId: i.candidate_id,
      startTime: i.start_time,
      endTime: i.end_time,
      meetingLink: i.meeting_link || "",
      outlookEventId: i.outlook_event_id || "",
      status: i.status,
    }));
  }, []);

  const refreshInterviews = useCallback(async () => {
    const refreshed = await getAllInterviews();
    setInterviews(mapInterviews(refreshed));
  }, [mapInterviews]);

  const refreshOffers = useCallback(async () => {
    try {
      const res = await getAllOffers();
      setOffers(res?.offers || []);
    } catch (err) {
      setOffers([]);
    }
  }, []);

  const refreshCandidates = useCallback(async () => {
    try {
      const [res, statusRes] = await Promise.all([
        getAllCandidates(),
        getAllCandidateStatuses().catch(() => null),
      ]);
      let mapped = (res?.candidates || []).map(mapCandidateFromApi);
      if (statusRes) {
        mapped = mergeCandidateStatuses(mapped, statusRes);
      }
      setCandidates(mapped);
      setSelectedCandidateData((prev) => {
        if (!prev?.id) return prev;
        const updatedCandidate = mapped.find(
          (candidate) => candidate.id === prev.id,
        );
        return updatedCandidate || prev;
      });
    } catch (err) {
      notify("Candidates", err.message || "Failed to refresh candidates.");
    }
  }, [notify]);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      try {
        const [
          candidateRes,
          jobRes,
          interviewRes,
          offersRes,
          usersRes,
          statusRes,
        ] = await Promise.all([
          getAllCandidates(),
          getAllJobs(),
          getAllInterviews(),
          getAllOffers(),
          getAllUsers(),
          getAllCandidateStatuses().catch(() => null),
        ]);
        if (!isMounted) return;

        setOffers(offersRes?.offers || []);
        setUsers(usersRes?.users || []);

        let mappedCandidates = (candidateRes?.candidates || []).map(
          mapCandidateFromApi,
        );
        if (statusRes) {
          mappedCandidates = mergeCandidateStatuses(
            mappedCandidates,
            statusRes,
          );
        }

        const mappedJobs = (jobRes?.jobs || []).map((j) =>
          mapJobFromApi(j, usersRes?.users || []),
        );

        const mappedInterviews = mapInterviews(interviewRes);

        setCandidates(mappedCandidates);
        setJobs(mappedJobs);
        setInterviews(mappedInterviews);

        if (!selectedCandidateId && mappedCandidates.length) {
          setSelectedCandidateId(mappedCandidates[0].id);
        }
        if (!selectedJobId && mappedJobs.length) {
          setSelectedJobId(mappedJobs[0].id);
        }
      } catch (err) {
        if (!isMounted) return;
        notify("Load", err.message || "Failed to load data.");
      }
    };

    loadData();
    return () => {
      isMounted = false;
    };
  }, [notify, mapInterviews]);

  const fetchCandidateById = async (id) => {
    const res = await getCandidateById(id);
    return mapCandidateFromApi(res || {});
  };

  const hasWorkspaceAccess = canAccessMyWorkspace({
    permissionRole: storedRole,
  });

  if (hasWorkspaceAccess) {
    return (
      <>
        <Routes>
          <Route
            path="/"
            element={
              <Shell
                role={storedRole}
                onLogout={handleLogout}
                candidates={candidates}
                jobs={jobs}
                setSelectedCandidateData={setSelectedCandidateData}
                setSelectedJobId={setSelectedJobId}
              />
            }
          >
            <Route index element={<MyWorkspace onLogout={handleLogout} />} />

            <Route path="thunder" element={<ThunderChatScreen />} />

            <Route
              path="resource-management"
              element={<ResourceManagementScreen />}
            />

            <Route path="core-pull" element={<CorePullScreen />} />
            <Route path="demand-confirmation" element={<DemandConfirmationScreen />} />
            <Route path="employees" element={<EmployeeDirectoryScreen />} />
            <Route path="submissions" element={<SubmissionsScreen />} />
            <Route path="allocations" element={<AllocationsScreen />} />
            <Route path="projects" element={<ProjectsScreen />} />
            <Route path="htd-intake" element={<HtdIntakeScreen />} />
            <Route path="hm-candidate-review" element={<HmCandidateReviewScreen />} />
            <Route path="utilization-dashboard" element={<UtilizationDashboardScreen />} />
            <Route path="timesheets" element={<TimesheetsScreen />} />
            <Route path="forecast" element={<ForecastScreen />} />
            <Route path="invoices" element={<InvoicesScreen />} />
            <Route path="revenue" element={<RevenueScreen />} />
            <Route path="settings/locale" element={<TenantLocaleScreen />} />
            <Route path="settings/templates" element={<MessageTemplatesScreen />} />
            <Route path="recruiter/intervention-queue" element={<InterventionQueueScreen />} />
            <Route path="recruiter/risk-dashboard" element={<RiskDashboardScreen />} />
            <Route path="recruiter/thunder-analytics" element={<ThunderAnalyticsScreen />} />
            <Route path="recruiter/bulk-launch" element={<BulkLaunchScreen />} />
            <Route path="admin/ai-config" element={<TenantAIConfigScreen />} />
            <Route path="my-tasks" element={<MyTasksScreen />} />
            <Route path="my-timesheet" element={<MyTimesheetScreen />} />
            <Route path="admin/ticket-routing" element={<TicketRoutingAdminScreen />} />
            <Route path="buddy-program" element={<BuddyProgramListScreen />} />
            <Route path="buddy-program/:recordId" element={<BuddyProgramScreen />} />
            <Route path="executive-signal" element={<ExecutiveSignalScreen />} />
            <Route path="admin/error-log" element={<ErrorLogScreen />} />
            <Route path="admin/settings" element={<AdminSettingsScreen />} />

            <Route
              path="candidates"
              element={
                <>
                  <SLABreachBanner />
                  <ConversationSearchBar />
                  <CandidateSearch
                    candidates={candidates}
                    jobs={jobs}
                    setAutoOpenSchedule={setAutoOpenSchedule}
                    onRefreshCandidates={refreshCandidates}
                    onCreateCandidate={() => navigate("/candidates/create")}
                  />
                </>
              }
            />

            <Route
              path="candidates/create"
              element={
                <CandidateCreate
                  onSave={async (c) => {
                    const fullCandidate = await fetchCandidateById(c.id);
                    setCandidates((prev) => [fullCandidate, ...prev]);
                    navigate(`/candidates/${fullCandidate.id}`);
                  }}
                />
              }
            />

            <Route
              path="candidates/:candidateId"
              element={
                <CandidateDetailsWrapper
                  refreshCandidates={refreshCandidates}
                  fetchCandidateById={fetchCandidateById}
                  updateCandidate={updateCandidate}
                />
              }
            />

            <Route
              path="/jobs"
              element={
                <JobsOverview
                  jobs={jobs}
                  onCreate={() => {
                    setJobCreateMode("create");
                  }}
                  onViewJob={(jobId) => {
                    navigate(`/jobs/${jobId}/workspace`);
                  }}
                  onOpenJob={(jobId) => {
                    navigate(`/jobs/${jobId}`);
                  }}
                  onPostToLinkedIn={async (jobId) => {
                    try {
                      const res = await postJobOnLinkedIn(jobId);
                      notify(
                        "LinkedIn",
                        res?.message || "Job posted to LinkedIn.",
                      );
                    } catch (err) {
                      notify(
                        "LinkedIn",
                        err.message || "Failed to post to LinkedIn.",
                      );
                    }
                  }}
                  onApproveJob={async (jobId) => {
                    try {
                      const response = await approveJob(jobId);
                      await refreshJobs();
                      notify(
                        "Job",
                        response?.message || `Approved job ${jobId}.`,
                      );
                    } catch (err) {
                      notify("Job", err.message || "Failed to approve job.");
                    }
                  }}
                  onDeleteJob={
                    isSuperUser
                      ? async (jobId) => {
                          const ok = window.confirm(`Delete job ${jobId}?`);
                          if (!ok) return;

                          try {
                            await deleteJob(jobId);
                            await refreshJobs();
                            notify("Job", `Deleted job ${jobId}.`);
                          } catch (err) {
                            notify(
                              "Job",
                              err.message || "Failed to delete job.",
                            );
                          }
                        }
                      : undefined
                  }
                />
              }
            />

            <Route
              path="jobs/create"
              element={
                <JobCreate
                  onSave={(j) => {
                    setJobs((prev) => [
                      {
                        ...j,
                        hiringManagerName: j?.hiringManager || "-",
                      },
                      ...prev,
                    ]);
                    setSelectedJobId(j.id);
                    toast.success(`Created job ${j.title}`);
                    navigate(ROUTES.JOBS);
                  }}
                />
              }
            />

            <Route
              path="jobs/:jobId/workspace"
              element={
                <JobWorkspaceWrapper
                  users={users}
                  candidates={candidates}
                  notify={notify}
                />
              }
            />

            <Route
              path="checklist-templates"
              element={<ChecklistTemplatesScreen />}
            />

            <Route
              path="offers-listing"
              element={
                <OfferListing
                  onFetchCandidateById={async (candidateId) => {
                    const res = await getCandidateById(candidateId);
                    return mapCandidateFromApi(res || {});
                  }}
                />
              }
            />
          </Route>
        </Routes>
        <ToastContainer position="top-right" autoClose={3000} />
      </>
    );
  }

  return (
    <>
      <Routes>
        <Route
          path="/"
          element={
            <Shell
              role={role}
              onLogout={handleLogout}
              candidates={candidates}
              jobs={jobs}
              setSelectedCandidateData={setSelectedCandidateData}
              setSelectedJobId={setSelectedJobId}
            />
          }
        >
          <Route
            index
            element={
              <Dashboard
                candidates={candidates}
                jobs={jobs}
                interviews={interviews}
                offers={offers}
              />
            }
          />
          <Route path="thunder" element={<ThunderChatScreen />} />
          <Route
            path="resource-management"
            element={<ResourceManagementScreen />}
          />
          <Route path="core-pull" element={<CorePullScreen />} />
            <Route path="demand-confirmation" element={<DemandConfirmationScreen />} />
            <Route path="employees" element={<EmployeeDirectoryScreen />} />
            <Route path="submissions" element={<SubmissionsScreen />} />
            <Route path="allocations" element={<AllocationsScreen />} />
            <Route path="projects" element={<ProjectsScreen />} />
            <Route path="htd-intake" element={<HtdIntakeScreen />} />
            <Route path="hm-candidate-review" element={<HmCandidateReviewScreen />} />
            <Route path="utilization-dashboard" element={<UtilizationDashboardScreen />} />
            <Route path="timesheets" element={<TimesheetsScreen />} />
            <Route path="forecast" element={<ForecastScreen />} />
            <Route path="invoices" element={<InvoicesScreen />} />
            <Route path="revenue" element={<RevenueScreen />} />
            <Route path="settings/locale" element={<TenantLocaleScreen />} />
            <Route path="settings/templates" element={<MessageTemplatesScreen />} />
            <Route path="recruiter/intervention-queue" element={<InterventionQueueScreen />} />
            <Route path="recruiter/risk-dashboard" element={<RiskDashboardScreen />} />
            <Route path="recruiter/thunder-analytics" element={<ThunderAnalyticsScreen />} />
            <Route path="recruiter/bulk-launch" element={<BulkLaunchScreen />} />
            <Route path="admin/ai-config" element={<TenantAIConfigScreen />} />
            <Route path="my-tasks" element={<MyTasksScreen />} />
            <Route path="my-timesheet" element={<MyTimesheetScreen />} />
            <Route path="admin/ticket-routing" element={<TicketRoutingAdminScreen />} />
            <Route path="buddy-program" element={<BuddyProgramListScreen />} />
            <Route path="buddy-program/:recordId" element={<BuddyProgramScreen />} />
            <Route path="executive-signal" element={<ExecutiveSignalScreen />} />
            <Route path="admin/error-log" element={<ErrorLogScreen />} />
            <Route path="admin/settings" element={<AdminSettingsScreen />} />
          <Route
            path="candidates"
            element={
              <>
                <SLABreachBanner />
                <ConversationSearchBar />
                <CandidateSearch
                  candidates={candidates}
                  jobs={jobs}
                  setAutoOpenSchedule={setAutoOpenSchedule}
                  onRefreshCandidates={refreshCandidates}
                  onCreateCandidate={() => navigate("/candidates/create")}
                />
              </>
            }
          />

          <Route
            path="candidates/create"
            element={
              <CandidateCreate
                onSave={async (c) => {
                  const fullCandidate = await fetchCandidateById(c.id);
                  setCandidates((prev) => [fullCandidate, ...prev]);
                  navigate(`/candidates/${fullCandidate.id}`);
                }}
              />
            }
          />

          <Route
            path="candidates/:candidateId"
            element={
              <CandidateDetailsWrapper
                fetchCandidateById={fetchCandidateById}
                onRefreshCandidates={refreshCandidates}
                updateCandidate={updateCandidate}
                notify={notify}
              />
            }
          />

          <Route
            path="jobs"
            element={
              <JobsOverview
                jobs={jobs}
                onCreate={() => {
                  setJobCreateMode("create");
                }}
                onViewJob={(jobId) => {
                  navigate(`/jobs/${jobId}/workspace`);
                }}
                onOpenJob={(jobId) => {
                  navigate(`/jobs/${jobId}`);
                }}
                onPostToLinkedIn={async (jobId) => {
                  try {
                    const res = await postJobOnLinkedIn(jobId);
                    notify(
                      "LinkedIn (Simulated -- not yet integrated)",
                      res?.message ||
                        "Simulated only. No LinkedIn integration is connected yet, so nothing was actually posted.",
                    );
                  } catch (err) {
                    notify(
                      "LinkedIn (Simulated -- not yet integrated)",
                      err.message || "Failed to simulate LinkedIn post.",
                    );
                  }
                }}
                onApproveJob={async (jobId) => {
                  try {
                    const response = await approveJob(jobId);
                    await refreshJobs();
                    notify(
                      "Job",
                      response?.message || `Approved job ${jobId}.`,
                    );
                  } catch (err) {
                    notify("Job", err.message || "Failed to approve job.");
                  }
                }}
                onDeleteJob={
                  isSuperUser
                    ? async (jobId) => {
                        const ok = window.confirm(`Delete job ${jobId}?`);
                        if (!ok) return;

                        try {
                          await deleteJob(jobId);
                          await refreshJobs();
                          notify("Job", `Deleted job ${jobId}.`);
                        } catch (err) {
                          notify("Job", err.message || "Failed to delete job.");
                        }
                      }
                    : undefined
                }
              />
            }
          />

          <Route
            path="jobs/create"
            element={
              <JobCreate
                onSave={(j) => {
                  setJobs((prev) => [
                    {
                      ...j,
                      hiringManagerName: j?.hiringManager || "-",
                    },
                    ...prev,
                  ]);
                  setSelectedJobId(j.id);
                  toast.success(`Created job ${j.title}`);
                  navigate(ROUTES.JOBS);
                }}
              />
            }
          />

          <Route
            path="jobs/:jobId/workspace"
            element={
              <JobWorkspaceWrapper
                users={users}
                candidates={candidates}
                notify={notify}
              />
            }
          />
          <Route path="/offers" element={<OfferLettersScreen />} />
          <Route path="hr-users" element={<HrUserManagement />} />
          <Route path="rbac" element={<RbacSettingsScreen />} />
        </Route>
      </Routes>
      <ToastContainer position="top-right" autoClose={3000} />
    </>
  );
}
