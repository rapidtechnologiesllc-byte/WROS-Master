// Shell layout for HR/Admin screens (sidebar + content area).
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

export default function Shell({
  role,
  screen,
  setScreen,
  onLogout,
  children,
  candidates = [],
  jobs = [],
  setSelectedCandidateData,
  setSelectedJobId,
}) {
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
    if (isHiringManager || isHR_Manager) {
      return [
        { id: "candidateSearch", label: "Candidates", icon: Users },
        ...(isHR_Manager
          ? [
              {
                id: "offerListing",
                label: "Offer Letters",
                icon: FileTextIcon,
              },
            ]
          : []),
      ];
    }

    const items = [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { id: "candidateSearch", label: "Candidates", icon: Users },
      { id: "jobs", label: "Jobs", icon: Briefcase },
      { id: "offerLetters", label: "Offer Letters", icon: FileTextIcon },
    ];
    if (isAdmin || isSuperUser) {
      items.push({ id: "rbac", label: "RBAC Settings", icon: Shield });
      items.push({ id: "hrUsers", label: "HR Users", icon: Users });
    }
    return items;
  }, [isAdmin, isSuperUser, isHR_Manager]);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="flex w-full gap-6 px-4 py-6">
        <aside className="hidden w-64 shrink-0 md:block">
          <div className="rounded-2xl border bg-white p-4 shadow-sm">
            <div className="mb-3">
              <div className="text-xs font-semibold text-gray-500">HRMS</div>
              <div className="text-lg font-extrabold tracking-tight">
                Recruitment
              </div>
            </div>

            <nav className="space-y-1">
              {nav.map((n) => {
                const Icon = n.icon;
                const active = screen === n.id;
                return (
                  <button
                    key={n.id}
                    onClick={() => setScreen(n.id)}
                    className={cx(
                      "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
                      active ? "bg-gray-900 text-white" : "hover:bg-gray-100",
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
          <div className="mt-4">{children}</div>
        </main>
      </div>
    </div>
  );
}
