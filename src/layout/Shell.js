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
  FolderKanban,
  AlertOctagon,
  MessageSquareText,
} from "lucide-react";
import cx from "../utils/cx";
import TopBar from "./TopBar";
import AskThunderWidget from "../components/AskThunderWidget";
import { ROUTES } from "../utils/Routes";
import { useLocation, useNavigate } from "react-router-dom";
import { Outlet } from "react-router-dom";

// Nav reorganized 2026-07-24 -- Avinash's direct feedback: the sidebar
// was a flat list of up to 21 items for Super User/Admin, which reads
// as unplanned rather than "feature driven." Grouped into four
// feature-oriented sections (Recruitment/Workforce/Finance/Admin) plus
// Dashboard standalone, collapsible so the common case (a handful of
// items you actually use) stays short, with the group containing your
// current screen auto-expanded.
const NAV_ITEMS = {
  dashboard: { path: ROUTES.DASHBOARD, label: "Dashboard", icon: LayoutDashboard },
  candidates: { path: ROUTES.CANDIDATES, label: "Candidates", icon: Users },
  jobs: { path: ROUTES.JOBS, label: "Jobs", icon: Briefcase },
  candidateReview: { path: ROUTES.HM_CANDIDATE_REVIEW, label: "Candidate Review", icon: UserCheck },
  offerLetters: { path: ROUTES.OFFERS, label: "Offer Letters", icon: FileTextIcon },
  offerLettersListing: { path: ROUTES.OFFERS_LISTING, label: "Offer Letters", icon: FileTextIcon },
  submissions: { path: ROUTES.SUBMISSIONS, label: "Submissions", icon: Send },
  employees: { path: ROUTES.EMPLOYEES, label: "Employees", icon: UserPlus },
  // HRMS-1105/S-320 -- Resource Management Agent. No dedicated
  // Partner/Resource Manager role exists in this codebase's role set
  // yet, so this is scoped to the roles that already get HR/oversight
  // nav items (SUPER_USER, ADMIN, HR Manager) as the closest proxy --
  // flagged for Avinash to confirm/adjust during story review.
  resourceManagement: { path: ROUTES.RESOURCE_MANAGEMENT, label: "Resource Management", icon: Users2 },
  allocations: { path: ROUTES.ALLOCATIONS, label: "Allocations", icon: Briefcase },
  // S-353/HRMS-0514 + S-373/HRMS-0529 -- same role scoping rationale.
  corePull: { path: ROUTES.CORE_PULL, label: "Core-Pull & Pool Guard", icon: ShieldAlert },
  // S-372/HRMS-0528 -- same role scoping rationale.
  demandConfirmation: { path: ROUTES.DEMAND_CONFIRMATION, label: "Demand Confirmation", icon: CalendarCheck2 },
  utilization: { path: ROUTES.UTILIZATION_DASHBOARD, label: "Utilization & Bench Cost", icon: BarChart3 },
  forecast: { path: ROUTES.FORECAST, label: "Resource Forecast", icon: TrendingUp },
  htdIntake: { path: ROUTES.HTD_INTAKE, label: "HTD Intake", icon: AlertOctagon },
  projects: { path: ROUTES.PROJECTS, label: "Projects", icon: FolderKanban },
  timesheets: { path: ROUTES.TIMESHEETS, label: "Timesheets", icon: Clock },
  invoices: { path: ROUTES.INVOICES, label: "Invoices", icon: BadgeDollarSign },
  revenue: { path: ROUTES.REVENUE, label: "Revenue", icon: LineChart },
  rbac: { path: ROUTES.RBAC, label: "RBAC Settings", icon: Shield },
  hrUsers: { path: ROUTES.HR_USERS, label: "HR Users", icon: Users },
  // S-219/HRMS-0121 -- tenant-wide setting, grouped under Admin.
  tenantLocale: { path: ROUTES.TENANT_LOCALE, label: "Locale & Currency", icon: Globe2 },
  // S-014/HRMS-0414 -- template.manage-gated activate action lives on
  // the screen itself; the nav entry is visible to anyone who can see
  // the Admin group (recruiters can create/preview, just not activate).
  messageTemplates: { path: ROUTES.MESSAGE_TEMPLATES, label: "Message Templates", icon: MessageSquareText },
  // S-062/HRMS-0462 -- candidates that need a human right now (escalations,
  // high drop risk, SLA breaches, etc.), same recruiter-facing grouping as
  // the rest of Recruitment.
  interventionQueue: { path: ROUTES.INTERVENTION_QUEUE, label: "Intervention Queue", icon: AlertOctagon },
};

const GROUP_DEFS = [
  {
    label: "Recruitment",
    icon: Users,
    keys: ["candidates", "jobs", "candidateReview", "offerLetters", "offerLettersListing", "submissions", "interventionQueue"],
  },
  {
    label: "Workforce",
    icon: Users2,
    keys: [
      "employees", "resourceManagement", "allocations", "corePull",
      "demandConfirmation", "utilization", "forecast", "htdIntake", "projects",
    ],
  },
  {
    label: "Finance",
    icon: BadgeDollarSign,
    keys: ["timesheets", "invoices", "revenue"],
  },
  {
    label: "Admin",
    icon: Shield,
    keys: ["rbac", "hrUsers", "tenantLocale", "messageTemplates"],
  },
];

function buildGroups(includedKeys) {
  const included = new Set(includedKeys);
  return GROUP_DEFS.map((g) => ({
    ...g,
    items: g.keys.filter((k) => included.has(k)).map((k) => NAV_ITEMS[k]),
  })).filter((g) => g.items.length > 0);
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
    if (isSuperUser) {
      return {
        standalone: [NAV_ITEMS.dashboard],
        groups: buildGroups([
          "candidates", "jobs", "candidateReview", "offerLetters", "submissions",
          "employees", "resourceManagement", "allocations", "corePull",
          "demandConfirmation", "utilization", "forecast", "htdIntake", "projects",
          "timesheets", "invoices", "revenue",
          "rbac", "hrUsers", "tenantLocale", "messageTemplates",
        ]),
      };
    }
    if (isAdmin) {
      return {
        standalone: [NAV_ITEMS.dashboard],
        groups: buildGroups([
          "candidates", "jobs",
          "employees", "resourceManagement", "allocations", "corePull",
          "demandConfirmation", "utilization", "forecast", "htdIntake", "projects",
          "timesheets", "invoices", "revenue",
          "rbac", "hrUsers", "tenantLocale", "messageTemplates",
        ]),
      };
    }
    if (isHR_Manager) {
      return {
        standalone: [],
        groups: buildGroups([
          "candidates", "offerLettersListing",
          "employees", "resourceManagement", "allocations", "corePull",
          "demandConfirmation", "utilization", "forecast", "htdIntake", "projects",
          "timesheets", "invoices", "revenue",
        ]),
      };
    }
    if (isHiringManager) {
      return { standalone: [NAV_ITEMS.candidates], groups: [] };
    }
    if (isHrOperations) {
      return { standalone: [NAV_ITEMS.candidates, NAV_ITEMS.jobs], groups: [] };
    }
    return { standalone: [NAV_ITEMS.dashboard], groups: [] };
  }, [isSuperUser, isAdmin, isHR_Manager, isHiringManager, isHrOperations]);

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
          />
          <div className="mt-4">
            <Outlet />
          </div>
        </main>
      </div>
      <AskThunderWidget />
    </div>
  );
}
