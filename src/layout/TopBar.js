// Top navigation bar with breadcrumbs and actions.
import { useMemo } from "react";
import { Plus, Search } from "lucide-react";
import { Button } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export default function TopBar({ role, screen, setScreen, onLogout }) {
  const crumbs = useMemo(() => {
    const map = {
      dashboard: ["Dashboard"],
      candidateSearch: ["Candidates", "Search"],
      candidateCreate: ["Candidates", "Create"],
      assignments: ["My Assignments"],
      jobs: ["Jobs"],
      activeJobs: ["Jobs", "Active"],
      jobCreate: ["Jobs", "Create"],
      jobDetails: ["Jobs", "Details"],
      matchingJobs: ["Candidates", "Matching Jobs"],
      interviewSchedule: ["Interviews", "Schedule"],
      interviewStatus: ["Interviews", "Status"],
      interviewAnalytics: ["Interviews", "Analytics"],
      approval: ["Hiring Manager", "Approval"],
      offer: ["Offer"],
      documents: ["Documents", "Upload"],
      verification: ["Documents", "Verification"],
      preOnboarding: ["Pre-Onboarding"],
      checklistTemplates: ["Checklists", "Templates"],
      newsletters: ["Newsletters"],
      rbac: ["Admin", "RBAC Settings"],
      hrUsers: ["Admin", "HR Users"]
    };
    return map[screen] || ["Dashboard"];
  }, [screen]);

  return (
    <div className="rounded-2xl border bg-white px-5 py-4 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-xs font-semibold text-gray-500">Signed in as</div>
          <div className="flex items-center gap-2">
            <div className="text-base font-extrabold tracking-tight">{role}</div>
            <span className={cx(pill, "border-gray-200 bg-gray-50 text-gray-700")}>
              Active
            </span>
          </div>
          <div className="mt-1 text-xs text-gray-600">{crumbs.join("  /  ")}</div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => setScreen("candidateSearch")}
            className="hidden md:inline-flex"
          >
            <Search className="h-4 w-4" /> Search
          </Button>
          <Button
            onClick={() => setScreen("candidateCreate")}
            className="hidden md:inline-flex"
          >
            <Plus className="h-4 w-4" /> Add Candidate
          </Button>
          <Button variant="ghost" onClick={onLogout}>
            Logout
          </Button>
        </div>
      </div>
    </div>
  );
}
