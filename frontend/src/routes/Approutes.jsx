import { lazy, useCallback, useEffect, useState } from "react";
import { getAllInterviews } from "../services/api/interviews";
import {
  getAllCandidates,
  getCandidateById,
  updateCandidate,
} from "../services/api/candidates";
import {
  approveJob,
  deleteJob,
  getAllJobs,
  postJobOnLinkedIn,
} from "../services/api/jobs";
import { getAllOffers } from "../services/api/offerLetters";
import { getAllUsers } from "../services/api/users";
import { getAllCandidateStatuses } from "../services/api/candidateStatus";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Shell from "../layout/Shell";
import { adminRoutes } from "./AdminRoutes";
import { hasPermission, homeDashboard, isCandidateUser } from "../utils/permissionsRoleTemplate";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../utils/Routes";
import ConversationSearchBar from "../components/ConversationSearchBar";
import SLABreachBanner from "../components/SLABreachBanner";
import { confirmDialog, alertDialog } from "../utils/dialogs";

// Screens load when first opened (one chunk each), not all in the bundle every page downloads
const Dashboard = lazy(() => import("../screens/Dashboard"));
const JobCreate = lazy(() => import("../screens/JobCreate"));
const JobsOverview = lazy(() => import("../screens/JobsOverview"));
const TemplatesAndChecklistsScreen = lazy(() => import("../screens/TemplatesAndChecklistsScreen"));
const UsersAndAccessControl = lazy(() => import("../screens/UsersAndAccessControl"));
const UserFormPage = lazy(() => import("../screens/UserFormPage"));
const EmployeesConsolidatedScreen = lazy(() => import("../screens/EmployeesConsolidatedScreen"));
const EmployeeProfileScreen = lazy(() => import("../screens/EmployeeProfileScreen"));
const MyPerformanceScreen = lazy(() => import("../screens/MyPerformanceScreen"));
const BusinessUnitFormPage = lazy(() => import("../screens/BusinessUnitFormPage"));
const DeliveryCenterFormPage = lazy(() => import("../screens/DeliveryCenterFormPage"));
const SystemHealth = lazy(() => import("../screens/SystemHealth"));
const OfferListing = lazy(() => import("../screens/OfferListing"));
const AuthPage = lazy(() => import("../pages/AuthPage"));
const CandidateCreate = lazy(() => import("../screens/CandidateCreate"));
const CandidateSearch = lazy(() => import("../screens/CandidateSearch"));
const CandidateSelfService = lazy(() => import("../screens/CandidateSelfService"));
const CandidateDetailsWrapper = lazy(() => import("./wrappers/CandidateDetailsWrapper"));
const JobWorkspaceWrapper = lazy(() => import("./wrappers/JobWorkspaceWrapper"));
const ThunderChatScreen = lazy(() => import("../screens/ThunderChatScreen"));
const DemandVsBenchScreen = lazy(() => import("../screens/DemandVsBenchScreen"));
const CorePullScreen = lazy(() => import("../screens/CorePullScreen"));
const ClientManagementScreen = lazy(() => import("../screens/ClientManagementScreen"));
const OpportunityPipelineScreen = lazy(() => import("../screens/OpportunityPipelineScreen"));
const MyExpensesScreen = lazy(() => import("../screens/MyExpensesScreen"));
const ExecutiveRevenueDashboardScreen = lazy(() => import("../screens/ExecutiveRevenueDashboardScreen"));
const PnlFinanceScreen = lazy(() => import("../screens/PnlFinanceScreen"));
const ActivateAccount = lazy(() => import("../pages/ActivateAccount"));
const ClientTimesheetApproval = lazy(() => import("../pages/ClientTimesheetApproval"));
const DemandConfirmationScreen = lazy(() => import("../screens/DemandConfirmationScreen"));
const PipelineAndSubmissionsScreen = lazy(() => import("../screens/PipelineAndSubmissionsScreen"));
const ProjectsScreen = lazy(() => import("../screens/ProjectsScreen"));
const HtdIntakeScreen = lazy(() => import("../screens/HtdIntakeScreen"));
const HmReviewScreen = lazy(() => import("../screens/HmReviewScreen"));
const TimesheetsScreen = lazy(() => import("../screens/TimesheetsScreen"));
const ForecastVsActualScreen = lazy(() => import("../screens/ForecastVsActualScreen"));
const InvoicesScreen = lazy(() => import("../screens/InvoicesScreen"));
const RevenueScreen = lazy(() => import("../screens/RevenueScreen"));
const TenantLocaleScreen = lazy(() => import("../screens/TenantLocaleScreen"));
const PublicThunderChatScreen = lazy(() => import("../screens/PublicThunderChatScreen"));
const CandidatePortalScreen = lazy(() => import("../screens/CandidatePortalScreen"));
const APIKeysSettings = lazy(() => import("../screens/APIKeysSettings"));
const RecruiterWatchScreen = lazy(() => import("../screens/RecruiterWatchScreen"));
const BulkLaunchScreen = lazy(() => import("../screens/BulkLaunchScreen"));
const TenantAIConfigScreen = lazy(() => import("../screens/TenantAIConfigScreen"));
const MyTasksScreen = lazy(() => import("../screens/MyTasksScreen"));
const TimesheetApprovalScreen = lazy(() => import("../screens/TimesheetApprovalScreen"));
const MyTimesheetScreen = lazy(() => import("../screens/MyTimesheetScreen"));
const TicketRoutingAdminScreen = lazy(() => import("../screens/TicketRoutingAdminScreen"));
const BuddyProgramListScreen = lazy(() => import("../screens/BuddyProgramListScreen"));
const BuddyProgramScreen = lazy(() => import("../screens/BuddyProgramScreen"));
const ExecutiveSignalScreen = lazy(() => import("../screens/ExecutiveSignalScreen"));
const ErrorLogScreen = lazy(() => import("../screens/ErrorLogScreen"));
const PartnerHomeScreen = lazy(() => import("../screens/PartnerHomeScreen"));
const CEOUnifiedDashboard = lazy(() => import("../screens/CEOUnifiedDashboard"));
const CFOAgentScreen = lazy(() => import("../screens/CFOAgentScreen"));
const AgentHealthScreen = lazy(() => import("../screens/AgentHealthScreen"));
const EmployeeConversionScreen = lazy(() => import("../screens/EmployeeConversionScreen"));
const ForcePasswordReset = lazy(() => import("../pages/ForcePasswordReset"));
const CertificationManagementScreen = lazy(() => import("../screens/CertificationManagementScreen"));
const BIExplorerScreen = lazy(() => import("../screens/BIExplorerScreen"));
const BuHeadDashboardScreen = lazy(() => import("../screens/BuHeadDashboardScreen"));
const MyReferralsScreen = lazy(() => import("../screens/MyReferralsScreen"));
const LinkedInPipelineScreen = lazy(() => import("../screens/LinkedInPipelineScreen"));
const DocumentUploadScreen = lazy(() => import("../screens/DocumentUploadScreen"));


// Wrapper component that renders the appropriate dashboard based on user permissions
// RBAC-driven: Uses permissions from role templates, not hardcoded job titles
const DashboardRouter = ({ candidates, jobs, interviews, offers }) => {
  // Home dashboard by position, decided server-side (authority.home_dashboard): CEO level ->
  // CEO, C-level finance -> CFO, partner level -> Partner, BU head level -> BU Head. Holding a
  // dashboard's permission (as an admin role does) never makes it home.
  const home = homeDashboard();
  if (home === "ceo") {
    return <CEOUnifiedDashboard />;
  }
  if (home === "cfo") {
    return <CFOAgentScreen />;
  }
  if (home === "partner") {
    return <PartnerHomeScreen />;
  }
  if (home === "bu_head") {
    return <BuHeadDashboardScreen />;
  }

  // Everyone else gets the generic dashboard
  return (
    <Dashboard
      candidates={candidates}
      jobs={jobs}
      interviews={interviews}
      offers={offers}
    />
  );
};

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
    businessUnitId: c.business_unit_id || null,
    // Read by the candidate detail "Users & BU" panel
    associated_bu_id: c.associated_bu_id ?? null,
    associated_bu_name: c.associated_bu_name || null,
    submission_bu_name: c.submission_bu_name || null,
    assigned_recruiter_id: c.assigned_recruiter_id || "",
    assigned_recruiter_name: c.assigned_recruiter_name || "",
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
    clientName: j.company_name || "",
    contactPerson: j.contact_person || "",
    startDate: j.start_date || "",
    endDate: j.end_date || "",
    jobDescription: j.job_description || "",
    // Section saves on Job Details echo these back, so they must round-trip
    noOfPositions: j.no_of_positions ?? null,
    payRange: j.salary_range || "",
    businessUnitId: j.business_unit || null,
  };
};

// Candidate pipeline statuses are an optional enrichment of the candidate list:
// on failure the list still renders with its own status fields, and the error
// is logged rather than swallowed.
const loadCandidateStatusesOptional = async () => {
  try {
    return await getAllCandidateStatuses();
  } catch (err) {
    console.error("[AppRoutes] Failed to load candidate statuses:", err);
    return null;
  }
};

// NOTE: normalizeRole() REMOVED - role checking is now entirely permission-based
// Role names from role templates are not hardcoded in frontend
// Instead, check user's permissions (which come from role template assignments)

const logout = () => {
  localStorage.removeItem("hrms_token");
  localStorage.removeItem("hrms_role");
  localStorage.removeItem("hrms_authority");
  localStorage.removeItem("hrms_user_name");
  localStorage.removeItem("hrms_user_email");
  localStorage.removeItem("hrms_candidate_id");
  localStorage.removeItem("hrms_user_type");
  localStorage.removeItem("hrms_roles");
  localStorage.removeItem("hrms_permissions");
  window.location.href = "/";
};

export default function AppRoutes() {
  // Public, unauthenticated Thunder chat widget -- a real external
  // visitor (careers page / job listing) has no account and never
  // will just to talk to Thunder. Checked before the token gate below,
  // same as /auth's special-casing.
  if (window.location.pathname.startsWith("/careers-chat")) {
    return <PublicThunderChatScreen />;
  }

  // Set your own password from an emailed link (activation / forgot password).
  // Before the ?token= handling below: this token is NOT a session token.
  if (window.location.pathname.startsWith("/activate")) {
    return <ActivateAccount />;
  }

  // The client's timesheet approver from the emailed single-use link: no account, no login.
  // Before the ?token= handling below: this token is NOT a session token.
  if (window.location.pathname.startsWith("/client-timesheet-approval")) {
    return <ClientTimesheetApproval />;
  }

  // S-017/HRMS-0417 -- Candidate Self-Service Web Portal. The token in
  // the path IS the candidate's auth (a long-lived candidate JWT, see
  // candidate_portal_service's module docstring) -- checked before the
  // internal login gate below, same precedent as /careers-chat, since
  // a candidate arriving via a WhatsApp/Email link has no internal
  // account and must never see the internal login screen.
  // Portal links are /candidate/{token} (singular - candidate_portal_service.
  // generate_portal_link_url); /candidates/* is the internal recruiter UI.
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

  // ✅ NEW: Force password reset on first login for auto-created users
  if (window.location.pathname === "/force-password-reset") {
    return <ForcePasswordReset />;
  }

  // Candidates get their own self-service app (decided before any hook runs)
  if (
    isCandidateUser({
      userType: String(localStorage.getItem("hrms_user_type") || "").trim().toLowerCase(),
    })
  ) {
    return <CandidateSelfService onLogout={logout} />;
  }

  // Hooks live in AuthenticatedApp: they must run in the same order on every render,
  // which the early returns above would break (react-hooks/rules-of-hooks)
  return <AuthenticatedApp />;
}

function AuthenticatedApp() {
  const [storedRole, setStoredRole] = useState(localStorage.getItem("permission_role"));
  const [storedJobTitle, setStoredJobTitle] = useState(localStorage.getItem("job_title"));
  // Permissions cached at login render the app at once; the refresh below updates them in the
  // background. Only a session with nothing cached waits for it.
  const [permissionsLoading, setPermissionsLoading] = useState(!localStorage.getItem("hrms_permissions"));
  const [, setPermissionsVersion] = useState(0);

  // Deleting a job needs the jobs delete permission on the role template
  const canDeleteJobs = hasPermission("jobs", "delete");

  const handleLogout = logout;

  // Root cause fix: Refresh role and permissions from /hr/me on app initialization
  // CRITICAL: This runs BEFORE Shell renders to ensure fresh permissions are loaded
  useEffect(() => {
    const refreshUserData = async () => {
      try {
        const { getHrMe } = await import("../services/api/users");

        // Add 5-second timeout to prevent infinite hang
        const timeoutPromise = new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Permissions loading timeout")), 5000)
        );

        const user = await Promise.race([getHrMe(), timeoutPromise]);

        if (user) {
          // Update localStorage with fresh data from backend
          if (user.user_role) {
            localStorage.setItem("permission_role", user.user_role);
            setStoredRole(user.user_role);
          }
          if (user.job_title) {
            localStorage.setItem("job_title", user.job_title);
            setStoredJobTitle(user.job_title);
          }
          if (user.roles && Array.isArray(user.roles)) {
            localStorage.setItem("hrms_roles", JSON.stringify(user.roles));
          }
          if (user.authority) {
            // home dashboard and leadership flags follow role changes without a re-login
            localStorage.setItem("hrms_authority", JSON.stringify(user.authority));
          }
          if (user.permissions !== undefined) {
            // the role template's matrix (an object by resource); stored even when empty
            localStorage.setItem("hrms_permissions", JSON.stringify(user.permissions || {}));
            setPermissionsVersion((v) => v + 1); // re-render the menu and screens with them
          }
        }
      } catch (error) {
        // Fallback: keep the permissions cached at login so the app still renders,
        // but never hide why the refresh failed.
        console.error(
          "[AppRoutes] Failed to refresh user permissions from /hr/me; using cached permissions:",
          error,
        );
      } finally {
        // CRITICAL: Mark loading as complete so Shell can render
        setPermissionsLoading(false);
      }
    };

    if (localStorage.getItem("hrms_token")) {
      refreshUserData();
    } else {
      setPermissionsLoading(false);
    }
  }, []);

  // Candidates, jobs, interviews, offers and users are loaded on demand: by the screens that use
  // them (Home's generic dashboard, Candidates, Jobs, Offers) or the top bar search -- never on
  // every page. Once loaded they stay for the session.
  const location = useLocation();
  const [dataWanted, setDataWanted] = useState(false);
  const wantData = useCallback(() => setDataWanted(true), []);
  useEffect(() => {
    const path = location.pathname;
    const needs = ["/candidates", "/jobs", "/offers-listing"].some((prefix) => path.startsWith(prefix))
      || (path === "/" && homeDashboard() === "default");
    if (needs) setDataWanted(true);
  }, [location.pathname]);

  const [candidates, setCandidates] = useState([]);

  const [jobs, setJobs] = useState([]);
  const [interviews, setInterviews] = useState([]);
  const [offers, setOffers] = useState([]);
  const [users, setUsers] = useState([]);
  const navigate = useNavigate();

  const notify = useCallback((title, message) => {
    alertDialog(`${title}\n\n${message}`);
  }, []);

  const refreshJobs = useCallback(async () => {
    const refreshed = await getAllJobs();
    const mappedJobs = (refreshed?.jobs || []).map((j) =>
      mapJobFromApi(j, users),
    );
    setJobs(mappedJobs);
  }, [users]);

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

  const refreshCandidates = useCallback(async () => {
    try {
      const [res, statusRes] = await Promise.all([
        getAllCandidates(),
        loadCandidateStatusesOptional(),
      ]);
      let mapped = (res?.candidates || []).map(mapCandidateFromApi);
      if (statusRes) {
        mapped = mergeCandidateStatuses(mapped, statusRes);
      }
      setCandidates(mapped);
    } catch (err) {
      notify("Candidates", err.message || "Failed to refresh candidates.");
    }
  }, [notify]);

  useEffect(() => {
    if (!dataWanted) return undefined;
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
          loadCandidateStatusesOptional(),
        ]);
        if (!isMounted) return;

        setOffers(offersRes?.offers || []);
        setUsers(usersRes || []);

        let mappedCandidates = (candidateRes?.candidates || []).map(
          mapCandidateFromApi,
        );
        if (statusRes) {
          mappedCandidates = mergeCandidateStatuses(
            mappedCandidates,
            statusRes,
          );
        }

        // Deduplicate jobs by ID to prevent duplicate display
        const jobMap = {};
        (jobRes?.jobs || []).forEach((j) => {
          const mapped = mapJobFromApi(j, usersRes || []);
          jobMap[mapped.id] = mapped;  // Last one wins in case of duplicates
        });
        const mappedJobs = Object.values(jobMap);

        const mappedInterviews = mapInterviews(interviewRes);

        setCandidates(mappedCandidates);
        setJobs(mappedJobs);
        setInterviews(mappedInterviews);
      } catch (err) {
        if (!isMounted) return;
        notify("Load", err.message || "Failed to load data.");
      }
    };

    loadData();
    return () => {
      isMounted = false;
    };
  }, [notify, mapInterviews, dataWanted]);

  const fetchCandidateById = async (id) => {
    const res = await getCandidateById(id);
    return mapCandidateFromApi(res || {});
  };

  // Root cause fix: Don't render Shell until permissions are loaded from /hr/me
  if (permissionsLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        fontSize: '18px',
        color: '#666'
      }}>
        Loading permissions...
      </div>
    );
  }

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
              onSearchFocus={wantData}
            />
          }
        >
          <Route
            index
            element={
              <DashboardRouter
                jobTitle={storedJobTitle}
                candidates={candidates}
                jobs={jobs}
                interviews={interviews}
                offers={offers}
              />
            }
          />

          {/* Candidate-chat test simulator: not in the menu, reachable by URL for QA (ask-thunder) */}
          <Route path="thunder" element={hasPermission("ask-thunder", "view") ? <ThunderChatScreen /> : <Navigate to="/" replace />} />

          <Route path="resource-management" element={<Navigate to="/demand-vs-bench?view=bench" replace />} />

          <Route path="core-pull" element={<CorePullScreen />} />
          <Route path="client-management" element={<ClientManagementScreen />} />
          <Route path="demand-confirmation" element={<DemandConfirmationScreen />} />
          <Route path="employees" element={<EmployeesConsolidatedScreen />} />
          <Route path="employees/:employeeId" element={<EmployeeProfileScreen />} />
          <Route path="my-performance" element={<MyPerformanceScreen />} />
          <Route path="employee-conversion" element={<EmployeeConversionScreen />} />
          <Route path="pipeline" element={<PipelineAndSubmissionsScreen />} />
          <Route path="hiring-pipeline" element={<Navigate to="/pipeline?view=pipeline" replace />} />
          <Route path="linkedin-pipeline" element={<LinkedInPipelineScreen />} />
          <Route path="submissions" element={<Navigate to="/pipeline?view=submissions" replace />} />
          <Route path="allocations" element={<Navigate to="/employees?tab=allocations" replace />} />
          <Route path="projects" element={<ProjectsScreen />} />
          <Route path="htd-intake" element={<HtdIntakeScreen />} />
          <Route path="hm-review" element={<HmReviewScreen />} />
          <Route path="hm-candidate-review" element={<Navigate to="/hm-review?view=candidates" replace />} />
          <Route path="utilization-dashboard" element={<Navigate to="/workforce?view=utilization" replace />} />
          <Route path="timesheets" element={<TimesheetsScreen />} />
          <Route path="demand-vs-bench" element={<DemandVsBenchScreen />} />
          <Route path="forecast" element={<Navigate to="/demand-vs-bench?view=forecast" replace />} />
          <Route path="forecast-vs-actual" element={<ForecastVsActualScreen />} />
          <Route path="invoices" element={<InvoicesScreen />} />
          <Route path="invoice-management" element={<Navigate to="/invoices" replace />} />
          <Route path="revenue" element={<RevenueScreen />} />
          <Route path="opportunity-pipeline" element={<OpportunityPipelineScreen />} />
          <Route path="executive-revenue-dashboard" element={<ExecutiveRevenueDashboardScreen />} />
          <Route path="finance-operations" element={<Navigate to="/pnl?view=operations" replace />} />
          <Route path="pnl" element={<PnlFinanceScreen />} />
          <Route path="partner-roi" element={<Navigate to="/partner-dashboard" replace />} />
          <Route path="ceo-fy-progress" element={<CEOUnifiedDashboard />} />
          <Route path="cfo-dashboard" element={<CFOAgentScreen />} />
          <Route path="settings/locale" element={<TenantLocaleScreen />} />
          <Route path="settings/templates" element={<Navigate to="/checklist-templates?view=email" replace />} />
          <Route path="api-keys" element={<APIKeysSettings />} />
          <Route path="system-health" element={<SystemHealth />} />
          <Route path="recruiter/watch" element={<RecruiterWatchScreen />} />
          <Route path="recruiter/intervention-queue" element={<Navigate to="/recruiter/watch?view=queue" replace />} />
          <Route path="recruiter/rehire-approvals" element={<Navigate to="/hm-review?view=rehire" replace />} />
          <Route path="ceo-dashboard" element={<Navigate to="/" replace />} />
          <Route path="recruiter/risk-dashboard" element={<Navigate to="/recruiter/watch?view=risk" replace />} />
          <Route path="recruiter/thunder-analytics" element={<Navigate to="/recruiter/watch?view=thunder" replace />} />
          <Route path="recruiter/bulk-launch" element={<BulkLaunchScreen />} />
          <Route path="admin/ai-config" element={<TenantAIConfigScreen />} />
          <Route path="my-tasks" element={<MyTasksScreen />} />
          <Route path="my-timesheet" element={<MyTimesheetScreen />} />
          <Route path="timesheet-approvals" element={<TimesheetApprovalScreen />} />
          <Route path="timesheet-approvals/:timesheetId" element={<TimesheetApprovalScreen />} />
          <Route path="my-expenses" element={<MyExpensesScreen />} />
          <Route path="my-referrals" element={<MyReferralsScreen />} />
          <Route path="admin/ticket-routing" element={<TicketRoutingAdminScreen />} />
          <Route path="buddy-program" element={<BuddyProgramListScreen />} />
          <Route path="buddy-program/:recordId" element={<BuddyProgramScreen />} />
          <Route path="executive-signal" element={<ExecutiveSignalScreen />} />
          <Route path="admin/error-log" element={<ErrorLogScreen />} />
          <Route path="admin/agent-config" element={<Navigate to="/admin/ai-config?tab=agents" replace />} />
          <Route path="admin/users-access-control" element={<UsersAndAccessControl />} />
          <Route path="admin/users-access-control/:section" element={<UsersAndAccessControl />} />
          <Route path="admin/users-access-control/users/create" element={<UserFormPage />} />
          <Route path="admin/users-access-control/users/:userId/edit" element={<UserFormPage />} />
          {/* Business units are managed in one place: Users & Access Control > Business Units */}
          <Route path="admin/business-units" element={<Navigate to="/admin/users-access-control/business-units" replace />} />
          <Route path="admin/certifications" element={<CertificationManagementScreen />} />
          <Route path="admin/agent-health" element={<AgentHealthScreen />} />
          <Route path="admin/agent-state-dashboard" element={<Navigate to="/admin/agent-health?view=state" replace />} />
          <Route path="admin/weekly-recap" element={<Navigate to="/admin/agent-health?view=recap" replace />} />
          <Route path="admin/users-access-control/business-units/create" element={<BusinessUnitFormPage />} />
          <Route path="admin/users-access-control/business-units/:buId/edit" element={<BusinessUnitFormPage />} />
          <Route path="admin/users-access-control/delivery-centers/create" element={<DeliveryCenterFormPage />} />
          <Route path="admin/users-access-control/delivery-centers/:dcId/edit" element={<DeliveryCenterFormPage />} />

          <Route path="partner-dashboard" element={<PartnerHomeScreen />} />
          <Route path="bi-explorer" element={<BIExplorerScreen />} />
          <Route path="bu-head-dashboard" element={<BuHeadDashboardScreen />} />

          <Route
            path="candidates"
            element={
              <>
                <SLABreachBanner />
                <ConversationSearchBar />
                <CandidateSearch
                  candidates={candidates}
                  jobs={jobs}
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
                  try {
                    const fullCandidate = await fetchCandidateById(c.id);
                    setCandidates((prev) => [fullCandidate, ...prev]);
                    navigate(`/candidates/${fullCandidate.id}`);
                  } catch (err) {
                    console.error("Failed to fetch candidate after creation, adding minimal data:", err);
                    // Add the candidate with minimal data if full fetch fails
                    setCandidates((prev) => [c, ...prev]);
                    navigate(`/candidates/${c.id}`);
                  }
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
            path="candidates/:candidateId/upload-documents"
            element={
              <DocumentUploadScreen candidateId={null} />
            }
          />

          <Route
            path="jobs"
            element={
              <JobsOverview
                jobs={jobs}
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
                  canDeleteJobs
                    ? async (jobId) => {
                        const ok = await confirmDialog(`Delete job ${jobId}?`);
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
            element={<TemplatesAndChecklistsScreen />}
          />

          <Route
            path="offers-listing"
            element={
              <OfferListing />
            }
          />

          {adminRoutes}

          <Route
            path="*"
            element={
              <div className="mx-auto max-w-2xl p-12 text-center">
                <h2 className="text-lg font-semibold text-gray-900 mb-2">Page not found</h2>
                <p className="text-gray-600">This screen doesn't exist yet, or the link is out of date.</p>
              </div>
            }
          />
        </Route>
      </Routes>
      <ToastContainer position="top-right" autoClose={3000} />
    </>
  );
}
