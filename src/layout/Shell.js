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
  Zap,
  Users2,
  ShieldAlert,
  CalendarCheck2,
  UserPlus,
  Send,
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
    // Thunder must be reachable by every role, first item in the list --
    // prepended to every branch below rather than gated behind a role check.
    const THUNDER_NAV_ITEM = { path: ROUTES.THUNDER, label: "Test Thunder", icon: Zap };
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

    if (isSuperUser) {
      return [
        THUNDER_NAV_ITEM,
        {
          path: ROUTES.DASHBOARD,
          label: "Dashboard",
          icon: LayoutDashboard,
        },
        EMPLOYEES_NAV_ITEM,
        SUBMISSIONS_NAV_ITEM,
        ALLOCATIONS_NAV_ITEM,
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
        THUNDER_NAV_ITEM,
        {
          path: ROUTES.DASHBOARD,
          label: "Dashboard",
          icon: LayoutDashboard,
        },
        EMPLOYEES_NAV_ITEM,
        SUBMISSIONS_NAV_ITEM,
        ALLOCATIONS_NAV_ITEM,
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
        {
          path: ROUTES.HR_USERS,
          label: "HR Users",
          icon: Users,
        },
      ];
    }
    if (isHR_Manager) {
      return [
        THUNDER_NAV_ITEM,
        EMPLOYEES_NAV_ITEM,
        SUBMISSIONS_NAV_ITEM,
        ALLOCATIONS_NAV_ITEM,
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
        THUNDER_NAV_ITEM,
        {
          path: ROUTES.CANDIDATES,
          label: "Candidates",
          icon: Users,
        },
      ];
    }
    if (isHrOperations) {
      return [
        THUNDER_NAV_ITEM,
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
      THUNDER_NAV_ITEM,
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
