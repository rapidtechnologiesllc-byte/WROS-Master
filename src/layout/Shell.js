import { useMemo } from "react";
import {
  BadgeDollarSign,
  Briefcase,
  BarChart3,
  Calendar,
  CheckCircle2,
  ClipboardCheck,
  ListChecks,
  FileText,
  LayoutDashboard,
  Mail,
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
} from "lucide-react";
import cx from "../utils/cx";
import TopBar from "./TopBar";
import { ROUTES } from "../utils/Routes";
import { useLocation, useNavigate } from "react-router-dom";
import { Outlet } from "react-router-dom";

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
  const isHr = normalizedRole === "HR";
  const isHR_Manager = normalizedRole === "HR MANAGER";
  const isHiringManager = normalizedRole === "HIRING MANAGER";
  const isHrOperations = normalizedRole === "HR OPERATIONS";
  const nav = useMemo(() => {
    // HRMS-1105/S-320 -- Resource Management Agent. No dedicated
    // Partner/Resource Manager role exists in this codebase's role set
    // yet, so this is scoped to the roles that already get HR/oversight
    // nav items (SUPER_USER, ADMIN, HR Manager) as the closest proxy --
    // flagged for Avinash to confirm/adjust during story review.
    const RESOURCE_MANAGEMENT_NAV_ITEM = {
      path: ROUTES.RESOURCE_MANAGEMENT,
      label: "Resource Management",
      icon: Users2,
    };
    // S-353/HRMS-0514 + S-373/HRMS-0529 -- same role scoping rationale
    // as RESOURCE_MANAGEMENT_NAV_ITEM above (no dedicated BU Head role
    // distinction exists in this nav yet).
    const CORE_PULL_NAV_ITEM = {
      path: ROUTES.CORE_PULL,
      label: "Core-Pull & Pool Guard",
      icon: ShieldAlert,
    };
    // S-372/HRMS-0528 -- same role scoping rationale as the two nav
    // items above.
    const DEMAND_CONFIRMATION_NAV_ITEM = {
      path: ROUTES.DEMAND_CONFIRMATION,
      label: "Demand Confirmation",
      icon: CalendarCheck2,
    };
    // S-245/HRMS-0501 + S-246/HRMS-0502 -- Employee Directory. Same role
    // scoping rationale as the three nav items above.
    const EMPLOYEES_NAV_ITEM = {
      path: ROUTES.EMPLOYEES,
      label: "Employees",
      icon: UserPlus,
    };
    // HRMS-0711 -- Client Submission Pipeline (also closes canonical
    // S-249). Same role scoping rationale as the four nav items above.
    const SUBMISSIONS_NAV_ITEM = {
      path: ROUTES.SUBMISSIONS,
      label: "Submissions",
      icon: Send,
    };
    // S-251/HRMS-0507 + S-252/HRMS-0508 -- same role scoping rationale
    // as the five nav items above.
    const ALLOCATIONS_NAV_ITEM = {
      path: ROUTES.ALLOCATIONS,
      label: "Allocations",
      icon: Briefcase,
    };
    // HRMS-0801/0804/0805/0806 + S-358/HRMS-0519 -- same role scoping
    // rationale as the nav items above.
    const PROJECTS_NAV_ITEM = {
      path: ROUTES.PROJECTS,
      label: "Projects",
      icon: FolderKanban,
    };
    // S-359/HRMS-P511 -- same role scoping rationale as the nav items
    // above.
    const HTD_INTAKE_NAV_ITEM = {
      path: ROUTES.HTD_INTAKE,
      label: "HTD Intake",
      icon: AlertOctagon,
    };
    // S-102/HRMS-P207 -- same role scoping rationale as the nav items
    // above.
    const HM_CANDIDATE_REVIEW_NAV_ITEM = {
      path: ROUTES.HM_CANDIDATE_REVIEW,
      label: "Candidate Review",
      icon: UserCheck,
    };
    // S-254/HRMS-0510 + S-255/HRMS-0511 -- same role scoping rationale
    // as the six nav items above.
    const UTILIZATION_DASHBOARD_NAV_ITEM = {
      path: ROUTES.UTILIZATION_DASHBOARD,
      label: "Utilization & Bench Cost",
      icon: BarChart3,
    };
    // S-220/HRMS-0901 + S-222/HRMS-0902 -- "time tracking" in Avinash's
    // MVP chain. Same role scoping rationale as the seven nav items above.
    const TIMESHEETS_NAV_ITEM = {
      path: ROUTES.TIMESHEETS,
      label: "Timesheets",
      icon: Clock,
    };
    // S-256/HRMS-0506 -- same role scoping rationale as the eight nav
    // items above.
    const FORECAST_NAV_ITEM = {
      path: ROUTES.FORECAST,
      label: "Resource Forecast",
      icon: TrendingUp,
    };
    // HRMS-0907/S-226 -- Invoicing. Same role scoping rationale as the
    // nav items above (no dedicated Finance role in this codebase yet).
    const INVOICES_NAV_ITEM = {
      path: ROUTES.INVOICES,
      label: "Invoices",
      icon: BadgeDollarSign,
    };
    // HRMS-0906/S-225 (Revenue Leakage) + HRMS-0903 (Reconciliation) +
    // HRMS-0909/S-228 (Client Revenue Dashboard). Same role scoping
    // rationale as the nav items above.
    const REVENUE_NAV_ITEM = {
      path: ROUTES.REVENUE,
      label: "Revenue",
      icon: LineChart,
    };
    // S-219/HRMS-0121 -- Multi-Continent Locale & Currency Config.
    // Tenant-wide setting, scoped alongside RBAC Settings (Admin/
    // SuperUser only) rather than the RM-proxy roles above.
    const TENANT_LOCALE_NAV_ITEM = {
      path: ROUTES.TENANT_LOCALE,
      label: "Locale & Currency",
      icon: Globe2,
    };

    if (isSuperUser) {
      return [
        {
          path: ROUTES.DASHBOARD,
          label: "Dashboard",
          icon: LayoutDashboard,
        },
        EMPLOYEES_NAV_ITEM,
        SUBMISSIONS_NAV_ITEM,
        ALLOCATIONS_NAV_ITEM,
        PROJECTS_NAV_ITEM,
        HTD_INTAKE_NAV_ITEM,
        HM_CANDIDATE_REVIEW_NAV_ITEM,
        UTILIZATION_DASHBOARD_NAV_ITEM,
        TIMESHEETS_NAV_ITEM,
        FORECAST_NAV_ITEM,
        INVOICES_NAV_ITEM,
        REVENUE_NAV_ITEM,
        RESOURCE_MANAGEMENT_NAV_ITEM,
        CORE_PULL_NAV_ITEM,
        DEMAND_CONFIRMATION_NAV_ITEM,
        {
          path: ROUTES.CANDIDATES,
          label: "Candidates",
          icon: Users,
        },
        {
          path: ROUTES.JOBS,
          label: "Jobs",
          icon: Briefcase,
        },
        {
          path: ROUTES.RBAC,
          label: "RBAC Settings",
          icon: Shield,
        },
        TENANT_LOCALE_NAV_ITEM,
        {
          path: ROUTES.HR_USERS,
          label: "HR Users",
          icon: Users,
        },
        { path: ROUTES.OFFERS, label: "Offer Letters", icon: FileTextIcon },
      ];
    }
    if (isAdmin) {
      return [
        {
          path: ROUTES.DASHBOARD,
          label: "Dashboard",
          icon: LayoutDashboard,
        },
        EMPLOYEES_NAV_ITEM,
        SUBMISSIONS_NAV_ITEM,
        ALLOCATIONS_NAV_ITEM,
        PROJECTS_NAV_ITEM,
        HTD_INTAKE_NAV_ITEM,
        HM_CANDIDATE_REVIEW_NAV_ITEM,
        UTILIZATION_DASHBOARD_NAV_ITEM,
        TIMESHEETS_NAV_ITEM,
        FORECAST_NAV_ITEM,
        INVOICES_NAV_ITEM,
        REVENUE_NAV_ITEM,
        RESOURCE_MANAGEMENT_NAV_ITEM,
        CORE_PULL_NAV_ITEM,
        DEMAND_CONFIRMATION_NAV_ITEM,
        {
          path: ROUTES.CANDIDATES,
          label: "Candidates",
          icon: Users,
        },
        {
          path: ROUTES.JOBS,
          label: "Jobs",
          icon: Briefcase,
        },
        {
          path: ROUTES.RBAC,
          label: "RBAC Settings",
          icon: Shield,
        },
        TENANT_LOCALE_NAV_ITEM,
        {
          path: ROUTES.HR_USERS,
          label: "HR Users",
          icon: Users,
        },
      ];
    }
    if (isHR_Manager) {
      return [
        EMPLOYEES_NAV_ITEM,
        SUBMISSIONS_NAV_ITEM,
        ALLOCATIONS_NAV_ITEM,
        PROJECTS_NAV_ITEM,
        HTD_INTAKE_NAV_ITEM,
        HM_CANDIDATE_REVIEW_NAV_ITEM,
        UTILIZATION_DASHBOARD_NAV_ITEM,
        TIMESHEETS_NAV_ITEM,
        FORECAST_NAV_ITEM,
        INVOICES_NAV_ITEM,
        REVENUE_NAV_ITEM,
        RESOURCE_MANAGEMENT_NAV_ITEM,
        CORE_PULL_NAV_ITEM,
        DEMAND_CONFIRMATION_NAV_ITEM,
        {
          path: ROUTES.CANDIDATES,
          label: "Candidates",
          icon: Users,
        },
        {
          path: ROUTES.OFFERS_LISTING,
          label: "Offer Letters",
          icon: FileTextIcon,
        },
      ];
    }
    if (isHiringManager) {
      return [
        {
          path: ROUTES.CANDIDATES,
          label: "Candidates",
          icon: Users,
        },
      ];
    }
    if (isHrOperations) {
      return [
        {
          path: ROUTES.CANDIDATES,
          label: "Candidates",
          icon: Users,
        },
        {
          path: ROUTES.JOBS,
          label: "Jobs",
          icon: Briefcase,
        },
      ];
    }

    return [
      {
        path: ROUTES.DASHBOARD,
        label: "Dashboard",
        icon: LayoutDashboard,
      },
    ];
  }, [isSuperUser, isAdmin, isHR_Manager, isHiringManager, isHrOperations]);

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
              {nav.map((n) => {
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
    </div>
  );
}
