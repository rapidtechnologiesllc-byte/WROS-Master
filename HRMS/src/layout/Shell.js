// Shell layout for HR/Admin screens (sidebar + content area).
import { useMemo } from "react";
import {
  BadgeDollarSign,
  Briefcase,
  Calendar,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Users
} from "lucide-react";
import cx from "../utils/cx";
import TopBar from "./TopBar";

export default function Shell({
  role,
  setRole,
  screen,
  setScreen,
  onLogout,
  children
}) {
  const nav = useMemo(
    () => [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { id: "candidateSearch", label: "Candidates", icon: Users },
      { id: "jobs", label: "Jobs", icon: Briefcase },
      { id: "interviewSchedule", label: "Interviews", icon: Calendar },
      { id: "offer", label: "Offer", icon: BadgeDollarSign },
      { id: "documents", label: "Documents", icon: FileText },
      { id: "verification", label: "Verification", icon: ClipboardCheck },
      { id: "preOnboarding", label: "Pre-Onboarding", icon: CheckCircle2 }
    ],
    []
  );

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

            <div className="mb-4 rounded-2xl border bg-gray-50 p-3">
              <div className="mb-2 text-xs font-semibold text-gray-600">Role</div>
              <div className="flex gap-2">
                {["Recruiter", "Hiring Manager", "Candidate"].map((r) => (
                  <button
                    key={r}
                    onClick={() => setRole(r)}
                    className={cx(
                      "rounded-xl px-2.5 py-1.5 text-xs font-semibold",
                      role === r
                        ? "bg-gray-900 text-white"
                        : "bg-white text-gray-800 border"
                    )}
                  >
                    {r}
                  </button>
                ))}
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
                      active ? "bg-gray-900 text-white" : "hover:bg-gray-100"
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
          />
          <div className="mt-4">{children}</div>
        </main>
      </div>
    </div>
  );
}
