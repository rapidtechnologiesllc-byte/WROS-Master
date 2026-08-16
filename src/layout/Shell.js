import { useEffect, useMemo, useState } from "react";
import {
  BadgeDollarSign,
  Briefcase,
  BarChart3,
  ChevronDown,
  LayoutDashboard,
  Shield,
  UserCheck,
  Users,
  FileTextIcon,
  Users2,
  ShieldAlert,
  CalendarCheck2,
  UserPlus,
  Send,
  Clock,
  TrendingUp,
  LineChart,
  Globe2,
  Bot,
  FolderKanban,
  AlertOctagon,
  MessageSquareText,
  Receipt,
  Settings,
} from "lucide-react";
import cx from "../utils/cx";
import TopBar from "./TopBar";
import FlashWidget from "../components/FlashWidget";
import { ROUTES } from "../utils/Routes";
import { NAV_ITEMS } from "./navItems";
import { useLocation, useNavigate } from "react-router-dom";
import { Outlet } from "react-router-dom";
import {
  hasPermission,
  getPermissions,
  getRoles,
  isSuperUser,
  isAdmin,
  canViewModule,
} from "../utils/permissionsRbac";

// Nav reorganized 2026-08-12 -- business-focused sections for clarity.
// Sales (deal pipeline) / Project Management (execution) / Finance (billing)
// + Recruitment (hiring) + Admin. Collapsible so the common case stays
// short, with the group containing your current screen auto-expanded.
const GROUP_DEFS = [
  {
    label: "Executive",
    icon: BarChart3,
    keys: ["ceoFyProgress", "executiveRevenueDashboard", "cfoDashboard", "buHeadDashboard", "partnerRoi"],
  },
  {
    label: "Recruitment",
    icon: Users,
    keys: ["candidates", "jobs", "candidateReview", "offerLetters", "offerLettersListing", "submissions", "interventionQueue", "rehireApprovals", "riskDashboard", "thunderAnalytics", "bulkLaunch"],
  },
  {
    label: "Sales",
    icon: TrendingUp,
    keys: ["clientManagement", "demandConfirmation", "opportunityPipeline"],
  },
  {
    label: "Workforce",
    icon: Users2,
    keys: ["employees", "htdIntake", "buddyProgram", "corePull"],
  },
  {
    label: "Project Management",
    icon: FolderKanban,
    keys: [
      "projects", "allocations", "resourceManagement",
      "utilization", "forecast",
    ],
  },
  {
    label: "Finance",
    icon: BadgeDollarSign,
    // 2026-08-12, Avinash: "anything monetary stays in finance" -- myExpenses
    // moved in from standalone. Finance owns billing, invoicing, and revenue reporting.
    keys: ["myExpenses", "timesheets", "invoices", "revenue", "forecastVsActual", "financeOperations"],
  },
  {
    label: "Admin",
    icon: Shield,
    keys: ["usersAccessControl", "certifications", "tenantLocale", "tenantAiConfig", "messageTemplates", "ticketRoutingAdmin", "executiveSignal", "errorLog", "adminSettings", "adminWeeklyRecap"],
  },
];

function buildGroups(includedKeys) {
  const included = new Set(includedKeys);
  return GROUP_DEFS.map((g) => ({
    ...g,
    items: g.keys.filter((k) => included.has(k)).map((k) => NAV_ITEMS[k]),
  })).filter((g) => g.items.length > 0);
}

// Permission-based navigation builder (2026-08-12)
// Maps nav keys to their required permissions
// NOTE: Updated to match actual permission names from CEO role in database
const NAV_PERMISSIONS = {
  // Recruitment Module (using actual permission names from database)
  candidates: "candidates.view",
  jobs: "jobs.view",
  candidateReview: "candidate_review.view",
  offerLetters: "offers.view",
  offerLettersListing: "offers.view",
  submissions: "submissions.view",
  interventionQueue: "intervention_queue.view",
  rehireApprovals: "rehire_approvals.view",
  riskDashboard: "risk_dashboard.view",
  thunderAnalytics: "thunder_analytics.view",
  bulkLaunch: "bulk_launch.view",

  // Sales/Client Module
  clientManagement: "clients.view",
  demandConfirmation: "demand.view",
  opportunityPipeline: "opportunities.view",
  partnerRoi: "partner_roi.view",

  // Workforce/HR Module
  employees: "employees.view",
  employeeConversion: "employees.view",  // convert uses employee.view permission
  htdIntake: "htd_intake.view",
  buddyProgram: "buddy_program.view",
  buHeadDashboard: "business_unit.view",

  // Resource Management Module
  corePull: "core_pull.view",
  projects: "projects.view",
  allocations: "allocations.view",
  resourceManagement: "resource_management.view",
  utilization: "utilization.view",
  forecast: "forecast.view",

  // Finance Module
  myExpenses: "expenses.view",
  timesheets: "timesheets.view",
  invoices: "invoices.view",
  invoiceManagement: "invoices.view",
  revenue: "revenue.view",
  forecastVsActual: "forecast.view",
  executiveRevenueDashboard: "reports.view",
  financeOperations: "finance_operations.view",

  // Admin Module
  usersAccessControl: "users.view",
  certifications: "certifications.view",
  tenantLocale: "locale.view",
  tenantAiConfig: "ai_config.view",
  messageTemplates: "message_templates.view",
  ticketRoutingAdmin: "ticket_routing.view",
  executiveSignal: "executive_signal.view",
  errorLog: "error_log.view",
  adminSettings: "admin_settings.view",
  adminWeeklyRecap: "admin_weekly_recap.view",

  // Dashboard/Agent Screens
  ceoFyProgress: "reports.view",
  cfoDashboard: "reports.view",
};

function buildGroupsByPermissions() {
  const permissions = getPermissions() || [];
  const isSuperUserFlag = isSuperUser();

  const getIncludedKeys = () => {
    if (isSuperUserFlag) {
      // Super users see everything
      return Object.keys(NAV_PERMISSIONS);
    }

    // Filter by permission
    return Object.keys(NAV_PERMISSIONS).filter(key => {
      const requiredPerm = NAV_PERMISSIONS[key];
      return hasPermission(requiredPerm);
    });
  };

  return buildGroups(getIncludedKeys());
}

export default function Shell({
  role,
  screen,
  setScreen,
  onLogout,
  candidates = [],
  jobs = [],
  setSelectedCandidateData,
  setSelectedJobId,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const [permissionsLoaded, setPermissionsLoaded] = useState(false);

  // Root cause fix: Refresh permissions from /hr/me on app load with retries
  useEffect(() => {
    let retryCount = 0;
    const maxRetries = 6; // Retry at 0s, 5s, 10s, 15s, 20s, 25s (stop at 30s)
    const retryInterval = 5000; // 5 seconds
    let timeoutId = null;

    const refreshPermissions = async () => {
      try {
        const { getHrMe } = await import("../services/api/users");
        const user = await getHrMe();
        if (user) {
          // Update localStorage with fresh permissions
          if (user.roles && Array.isArray(user.roles)) {
            localStorage.setItem("hrms_roles", JSON.stringify(user.roles));
          }
          if (user.permissions && Array.isArray(user.permissions)) {
            localStorage.setItem("hrms_permissions", JSON.stringify(user.permissions));
            setPermissionsLoaded(true); // Trigger re-render with new permissions
            return true; // Success, stop retrying
          }
        }
      } catch (error) {
        console.debug(`Permission refresh attempt ${retryCount + 1} failed:`, error);
      }
      return false; // Failed, continue retrying
    };

    const attemptRefresh = async () => {
      if (!localStorage.getItem("hrms_token")) {
        return; // No token, stop
      }

      const success = await refreshPermissions();
      if (success) {
        return; // Permissions loaded successfully
      }

      retryCount++;
      if (retryCount < maxRetries) {
        // Schedule next retry
        timeoutId = setTimeout(attemptRefresh, retryInterval);
      }
    };

    // Start the first attempt immediately
    attemptRefresh();

    // Cleanup timeouts on unmount
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, []); // Run once on mount

  const normalizedRole = String(role || "")
    .trim()
    .toUpperCase();
  const isSuperUser = ["SUPER USER", "SUPER_USER", "SUPERUSER"].includes(
    normalizedRole,
  );
  const isAdmin = normalizedRole === "ADMIN";
  const isHR_Manager = normalizedRole === "HR MANAGER";
  const isHiringManager = normalizedRole === "HIRING MANAGER";
  const isHrOperations = normalizedRole === "HR OPERATIONS";

  const nav = useMemo(() => {
    // 2026-08-12: Permission-based navigation (new RBAC system)
    const permissions = getPermissions();
    const rolesArray = getRoles();

    // Use permission-based navigation if permissions are available
    if (Array.isArray(permissions) && permissions.length > 0) {
      const permissionGroups = buildGroupsByPermissions();
      const standalone = [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myReferrals];
      return { standalone, groups: permissionGroups };
    }

    // Fallback: Legacy role-based navigation for backward compatibility
    if (isSuperUser) {
      // Super User gets ALL navigation items
      return {
        standalone: [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myReferrals],
        groups: buildGroups(Object.keys(NAV_PERMISSIONS)),
      };
    }
    if (isAdmin) {
      return {
        standalone: [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myReferrals],
        groups: buildGroups([
          "candidates", "jobs",
          "employees", "resourceManagement", "allocations", "corePull", "clientManagement",
          "demandConfirmation", "utilization", "forecast", "htdIntake", "projects", "buddyProgram",
          "myExpenses", "timesheets", "invoices", "revenue", "opportunityPipeline", "forecastVsActual", "executiveRevenueDashboard", "financeOperations", "partnerRoi", "ceoFyProgress", "cfoDashboard",
          "usersAccessControl", "certifications", "tenantLocale", "tenantAiConfig", "messageTemplates", "ticketRoutingAdmin", "executiveSignal", "errorLog", "adminSettings",
        ]),
      };
    }
    if (isHR_Manager) {
      return {
        standalone: [NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myReferrals],
        groups: buildGroups([
          "candidates", "offerLettersListing",
          "employees", "resourceManagement", "allocations", "corePull", "clientManagement",
          "demandConfirmation", "utilization", "forecast", "htdIntake", "projects", "buddyProgram",
          // financeOperations deliberately excluded -- Avinash's explicit
          // "finance & HR manager (no actual p&l)" rule. executiveRevenueDashboard
          // stays (revenue.view-level content, backend gates the P&L bits
          // separately at revenue.view_pnl). Agent dashboards (CEO FY Progress,
          // CFO Agent, Partner ROI) follow the same RBAC gates as executiveRevenueDashboard.
          "myExpenses", "timesheets", "invoices", "revenue", "opportunityPipeline", "forecastVsActual", "executiveRevenueDashboard", "ceoFyProgress", "cfoDashboard",
        ]),
      };
    }
    if (isHiringManager) {
      return { standalone: [NAV_ITEMS.candidates, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myExpenses], groups: [] };
    }
    if (isHrOperations) {
      return { standalone: [NAV_ITEMS.candidates, NAV_ITEMS.jobs, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myExpenses], groups: [] };
    }
    return { standalone: [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myExpenses, NAV_ITEMS.myReferrals], groups: [] };
  }, [isSuperUser, isAdmin, isHR_Manager, isHiringManager, isHrOperations, getPermissions, buildGroupsByPermissions, permissionsLoaded]);

  const [openGroups, setOpenGroups] = useState(() => new Set());

  // Auto-expand whichever group contains the current route -- so
  // navigating in (e.g. a deep link, or a redirect after an action)
  // never leaves you looking at a collapsed group with no indication
  // of where you are.
  useEffect(() => {
    const activeGroup = nav.groups.find((g) =>
      g.items.some((item) => item.path === location.pathname),
    );
    if (activeGroup) {
      setOpenGroups((prev) => new Set(prev).add(activeGroup.label));
    }
  }, [location.pathname, nav.groups]);

  const toggleGroup = (label) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const renderLink = (n) => {
    const Icon = n.icon;
    const active = location.pathname === n.path;
    return (
      <button
        key={n.path}
        onClick={() => navigate(n?.path)}
        className={cx(
          "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
          active
            ? "bg-bx-orange text-white"
            : "text-white/80 hover:bg-white/10 hover:text-white",
        )}
      >
        <Icon className="h-4 w-4" />
        {n.label}
      </button>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="flex w-full gap-6 px-4 py-6">
        <aside className="hidden w-64 shrink-0 md:block">
          <div className="rounded-2xl bg-bx-navy p-4 shadow-sm">
            <div className="mb-3">
              <div className="text-xs font-semibold text-white/60">BlitzenX</div>
              <div className="text-lg font-extrabold tracking-tight text-white">
                WROS
              </div>
            </div>

            <nav className="space-y-1">
              {nav.standalone.map((n) => renderLink(n))}

              {nav.groups.map((group) => {
                const GroupIcon = group.icon;
                const isOpen = openGroups.has(group.label);
                const hasActiveItem = group.items.some(
                  (item) => item.path === location.pathname,
                );
                return (
                  <div key={group.label}>
                    <button
                      onClick={() => toggleGroup(group.label)}
                      className={cx(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
                        hasActiveItem && !isOpen
                          ? "text-white"
                          : "text-white/80 hover:bg-white/10 hover:text-white",
                      )}
                    >
                      <GroupIcon className="h-4 w-4" />
                      <span className="flex-1 text-left">{group.label}</span>
                      <ChevronDown
                        className={cx(
                          "h-3.5 w-3.5 text-white/50 transition-transform",
                          isOpen ? "rotate-180" : "",
                        )}
                      />
                    </button>
                    {isOpen && (
                      <div className="ml-3 mt-1 space-y-1 border-l border-white/10 pl-3">
                        {group.items.map((item) => {
                          const ItemIcon = item.icon;
                          const active = location.pathname === item.path;
                          return (
                            <button
                              key={item.path}
                              onClick={() => navigate(item.path)}
                              className={cx(
                                "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition",
                                active
                                  ? "bg-bx-orange text-white"
                                  : "text-white/70 hover:bg-white/10 hover:text-white",
                              )}
                            >
                              <ItemIcon className="h-3.5 w-3.5" />
                              {item.label}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </nav>
          </div>
        </aside>

        <main className="flex-1">
          <TopBar
            role={role}
            screen={screen}
            setScreen={setScreen}
            onLogout={onLogout}
            candidates={candidates}
            jobs={jobs}
            setSelectedCandidateData={setSelectedCandidateData}
            setSelectedJobId={setSelectedJobId}
            hideTitle={true}
          />
          <div className="mt-4">
            <Outlet />
          </div>
        </main>
      </div>
      <FlashWidget />
    </div>
  );
}
