import {
  BadgeDollarSign,
  Briefcase,
  Calendar,
  LayoutDashboard,
  Plus,
  Search,
  Users,
} from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { Button, Card, StatusBadge } from "../components/ui";
import { useNavigate } from "react-router-dom";
import InterventionQueueWidget from "../components/intervention/InterventionQueueWidget";
import { getRoles } from "../utils/permissions";
import { getHrMe } from "../services/api/users";
import { hasPermission } from "../utils/permissionsRoleTemplate";

function StatCard({ title, value, icon, onClick }) {
  return (
    <button
      onClick={onClick}
      className="rounded-2xl border bg-white p-5 text-left shadow-sm transition hover:shadow"
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-gray-600">{title}</div>
        <div className="text-gray-700">{icon}</div>
      </div>
      <div className="mt-2 text-3xl font-extrabold tracking-tight">{value}</div>
    </button>
  );
}

export default function Dashboard({
  candidates,
  jobs,
  interviews,
  offers = [],
  onGo,
}) {
  const navigate = useNavigate();
  const navigationAttemptedRef = useRef(false);

  useEffect(() => {
    if (navigationAttemptedRef.current) return;

    const checkPermissionsAndRedirect = async () => {
      try {
        // RBAC-driven: Check specific permissions instead of hardcoded role names
        // Each dashboard is gated by specific permission requirements
        const perms = JSON.parse(localStorage.getItem('hrms_permissions') || '[]');
        navigationAttemptedRef.current = true;

        // Permission-based routing (not role-based hardcoding)
        // If user has CEO/CFO/Partner permissions, redirect to their dashboard
        // The role template name is NOT used for routing
        if (perms.includes('*.*')) {
          // Wildcard permission = SuperUser/CEO
          window.location.replace("/ceo-fy-progress");
          return;
        }
        if (perms.includes('finance.manage')) {
          // Finance management permission
          window.location.replace("/cfo-dashboard");
          return;
        }
        if (perms.includes('business_unit.manage')) {
          // BU Head permission
          window.location.replace("/bu-head-dashboard");
          return;
        }
        if (perms.includes('recruitment.manage')) {
          // Recruiter/Hiring Manager permission
          window.location.replace("/recruitment-dashboard");
          return;
        }

        // Default: stay on general dashboard if no special permissions
        console.log("No special dashboard permissions found, showing general dashboard");
      } catch (err) {
        console.error("Failed to check permissions and redirect:", err);
        // Default: stay on general dashboard on error
      }
    };

    checkPermissionsAndRedirect();
  }, []);

  // Get user's BU for filtering
  const userBuId = parseInt(localStorage.getItem("hrms_business_unit_id") || "0", 10);

  // ZERO-HARDCODING: Get permission from role template, not hardcoded roles
  // Check if user has org-level view permission (not BU-scoped)
  const canViewAllData = hasPermission("candidates", "view") || hasPermission("system", "manage");

  // Filter data based on user permission
  const filteredCandidates = canViewAllData
    ? candidates
    : candidates.filter((c) => !c.businessUnitId || c.businessUnitId === userBuId);

  const filteredJobs = canViewAllData
    ? jobs
    : jobs.filter((j) => !j.businessUnitId || j.businessUnitId === userBuId);

  const openJobs = filteredJobs.filter(
    (j) => j.status === "Open" || j.status === "Public",
  ).length;
  const inPipeline = filteredCandidates.filter((c) => {
    const p = (c.pipelineStatus || "").trim();
    if (p === "Rejected") return false;
    const a = (c.accountStatus || "").trim();
    if (a === "Inactive") return false;
    return true;
  }).length;
  const scheduled = interviews.filter((i) => i.status === "Scheduled").length;
  const pendingOffers = offers.filter(
    (o) => o.offer_status === "Pending",
  ).length;
  const latestOffer = offers.length ? offers[offers.length - 1] : null;

  return (
    <div className="space-y-4">
      <Card title="Dashboard" icon={<LayoutDashboard className="h-4 w-4" />} />

      <InterventionQueueWidget />

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Open Jobs"
          value={String(openJobs)}
          icon={<Briefcase className="h-4 w-4" />}
          onClick={() => navigate("/jobs")}
        />
        <StatCard
          title="Candidates in Pipeline"
          value={String(inPipeline)}
          icon={<Users className="h-4 w-4" />}
          onClick={() => navigate("/candidates")}
        />
        <StatCard
          title="Interviews Scheduled"
          value={String(scheduled)}
          icon={<Calendar className="h-4 w-4" />}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card
          title="Quick actions"
          icon={<LayoutDashboard className="h-4 w-4" />}
        >
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate("/candidates/create")}>
              <Plus className="h-4 w-4" /> Add New Candidate
            </Button>
            <Button variant="secondary" onClick={() => navigate("/candidates")}>
              <Search className="h-4 w-4" /> Search Candidate
            </Button>
            <Button variant="secondary" onClick={() => navigate("/jobs/create")}>
              <Plus className="h-4 w-4" /> Create Job
            </Button>
          </div>
        </Card>

        <Card
          title="Offer snapshot"
          icon={<BadgeDollarSign className="h-4 w-4" />}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-gray-900">
                {pendingOffers ? `${pendingOffers} pending` : "No offers"}
              </div>
              {latestOffer ? (
                <>
                  <div className="mt-1 text-xs text-gray-600">
                    Latest:{" "}
                    <span className="font-semibold">
                      {latestOffer.position}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-gray-600">
                    Salary:{" "}
                    <span className="font-semibold">
                      ${String(latestOffer.salary || 0)}
                    </span>
                  </div>
                </>
              ) : null}
            </div>
            {latestOffer ? (
              <StatusBadge status={latestOffer.offer_status} />
            ) : null}
          </div>
          <Button
            variant="secondary"
            className="mt-3 w-full"
            onClick={() => navigate("/offers")}
          >
            Manage Offers
          </Button>
        </Card>
      </div>
    </div>
  );
}
