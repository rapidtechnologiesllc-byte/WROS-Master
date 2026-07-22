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
    if (isSuperUser) {
      return [
        {
          path: ROUTES.DASHBOARD,
          label: "Dashboard",
          icon: LayoutDashboard,
        },
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
        {
          path: ROUTES.DASHBOARD,
          label: "Dashboard",
          icon: LayoutDashboard,
        },
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
