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
    label: "Recruitment",
    icon: Users,
    keys: ["candidates", "jobs", "candidateReview", "offerLetters", "offerLettersListing", "submissions", "interventionQueue", "rehireApprovals", "riskDashboard", "thunderAnalytics", "bulkLaunch"],
  },
  {
    label: "Sales",
    icon: TrendingUp,
    keys: ["clientManagement", "demandConfirmation", "opportunityPipeline", "partnerRoi"],
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
    keys: ["myExpenses", "timesheets", "invoices", "revenue", "forecastVsActual", "executiveRevenueDashboard", "financeOperations", "ceoFyProgress", "cfoDashboard"],
  },
  {
    label: "Admin",
    icon: Shield,
    keys: ["usersAccessControl", "tenantLocale", "tenantAiConfig", "messageTemplates", "ticketRoutingAdmin", "executiveSignal", "errorLog", "adminSettings", "adminWeeklyRecap"],
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
const NAV_PERMISSIONS = {
  candidates: "recruitment.view",
  jobs: "recruitment.view",
  candidateReview: "recruitment.view",
  offerLetters: "recruitment.view",
  offerLettersListing: "recruitment.view",
  submissions: "recruitment.view",
  interventionQueue: "recruitment.view",
  rehireApprovals: "recruitment.view",
  riskDashboard: "recruitment.view",
  thunderAnalytics: "recruitment.view",
  bulkLaunch: "recruitment.view",

  clientManagement: "business_unit.manage",
  demandConfirmation: "recruitment.view",
  opportunityPipeline: "business_unit.manage",
  partnerRoi: "business_unit.manage",

  employees: "employee.view",
  employeeConversion: "employee.manage",
  htdIntake: "recruitment.view",
  buddyProgram: "employee.manage",
  corePull: "resource_management.view",

  projects: "project.manage",
  allocations: "project.manage",
  resourceManagement: "resource_management.view",
  utilization: "project.view",
  forecast: "project.view",

  myExpenses: "invoice.view",
  timesheets: "timesheet.view",
  invoices: "invoice.view",
  revenue: "reports.financial",
  forecastVsActual: "reports.financial",
  executiveRevenueDashboard: "reports.financial",
  financeOperations: "finance.view",
  ceoFyProgress: "reports.view",
  cfoDashboard: "reports.view",

  usersAccessControl: "user.manage",
  tenantLocale: "tenant.manage",
  tenantAiConfig: "agent.manage",
  messageTemplates: "communication.manage",
  ticketRoutingAdmin: "ticket.manage",
  executiveSignal: "reports.view",
  errorLog: "system.view",
  adminSettings: "system.manage",
  adminWeeklyRecap: "reports.view",
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
      const standalone = [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet];
      return { standalone, groups: permissionGroups };
    }

    // Fallback: Legacy role-based navigation for backward compatibility
    if (isSuperUser) {
      return {
        standalone: [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet],
        groups: buildGroups([
          "candidates", "jobs", "candidateReview", "offerLetters", "submissions",
          "employees", "resourceManagement", "allocations", "corePull", "clientManagement",
          "demandConfirmation", "utilization", "forecast", "htdIntake", "projects", "buddyProgram",
          "myExpenses", "timesheets", "invoices", "revenue", "opportunityPipeline", "forecastVsActual", "executiveRevenueDashboard", "financeOperations", "partnerRoi", "ceoFyProgress", "cfoDashboard",
          "usersAccessControl", "tenantLocale", "tenantAiConfig", "messageTemplates", "ticketRoutingAdmin", "executiveSignal", "errorLog", "adminSettings",
        ]),
      };
    }
    if (isAdmin) {
      return {
        standalone: [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet],
        groups: buildGroups([
          "candidates", "jobs",
          "employees", "resourceManagement", "allocations", "corePull", "clientManagement",
          "demandConfirmation", "utilization", "forecast", "htdIntake", "projects", "buddyProgram",
          "myExpenses", "timesheets", "invoices", "revenue", "opportunityPipeline", "forecastVsActual", "executiveRevenueDashboard", "financeOperations", "partnerRoi", "ceoFyProgress", "cfoDashboard",
          "usersAccessControl", "tenantLocale", "tenantAiConfig", "messageTemplates", "ticketRoutingAdmin", "executiveSignal", "errorLog", "adminSettings",
        ]),
      };
    }
    if (isHR_Manager) {
      return {
        standalone: [NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet],
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
    return { standalone: [NAV_ITEMS.dashboard, NAV_ITEMS.myTasks, NAV_ITEMS.myTimesheet, NAV_ITEMS.myExpenses], groups: [] };
  }, [isSuperUser, isAdmin, isHR_Manager, isHiringManager, isHrOperations, getPermissions, buildGroupsByPermissions]);

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
