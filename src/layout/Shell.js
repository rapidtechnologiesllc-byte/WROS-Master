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
} from "../utils/permissions";

// Dynamic navigation driven by role template permissions from backend
// Navigation structure is fetched from /hr/me/navigation endpoint
// which returns groups and items filtered by user's actual permissions (175 resources)

// Icon mapping for resource names AND module/group icons (by name string)
const ICON_MAP_BY_RESOURCE = {
  "candidates": Users,
  "jobs": Briefcase,
  "interviews": Users,
  "offers": FileTextIcon,
  "employees": Users2,
  "timesheets": Clock,
  "invoices": Receipt,
  "reports": BarChart3,
  "users": Shield,
  "roles": Shield,
  "role_templates": Settings,
  "dashboard": LayoutDashboard,
  "my_tasks": UserCheck,
  "my_timesheet": Clock,
  "my_expenses": BadgeDollarSign,
  "profile": UserPlus,
};

// Map icon names (strings from backend) to icon components
const ICON_COMPONENTS_BY_NAME = {
  "Users": Users,
  "Users2": Users2,
  "Briefcase": Briefcase,
  "Video": Users,
  "FileText": FileTextIcon,
  "Clock": Clock,
  "Receipt": Receipt,
  "BarChart3": BarChart3,
  "BarChart2": BarChart3,
  "BadgeDollarSign": BadgeDollarSign,
  "Shield": Shield,
  "Lock": Shield,
  "Settings": Settings,
  "Home": LayoutDashboard,
  "TrendingUp": TrendingUp,
  "MessageCircle": MessageSquareText,
  "Bell": AlertOctagon,
  "CheckSquare": UserCheck,
  "DollarSign": BadgeDollarSign,
  "Eye": UserCheck,
  "Calendar": CalendarCheck2,
  "MessageSquare": MessageSquareText,
  "CheckCircle": UserCheck,
  "Building": LayoutDashboard,
  "AlertCircle": AlertOctagon,
  "File": FileTextIcon,
  "Award": UserPlus,
};

// Fetch pre-built navigation from backend (already filtered by permissions)
async function fetchNavigationFromBackend() {
  try {
    const { apiRequest } = await import("../services/api/client");
    const response = await apiRequest("/hr/me/navigation", { method: "GET" });

    // apiRequest returns { data, response } structure - extract the actual data
    const navData = response?.data || response;

    if (!navData || !navData.groups) {
      console.warn("Invalid navigation response:", response);
      return [];
    }

    // Backend returns: { groups: [ { label, icon, items: [{key, label, icon, route}] } ] }
    // Transform items to use route instead of path for navigation
    const groups = navData.groups.map(group => ({
      ...group,
      items: group.items.map(item => ({
        key: item.key,
        label: item.label,
        icon: ICON_MAP_BY_RESOURCE[item.key] || Briefcase,
        path: item.route || `/${item.key.replace(/_/g, "-")}`, // Fallback path if route not provided
      }))
    }));

    console.debug("Navigation fetched from backend:", {
      groupCount: groups.length,
      totalItems: groups.reduce((sum, g) => sum + g.items.length, 0),
      modules: groups.map(g => `${g.label}(${g.items.length})`).join(", "),
    });

    return groups;
  } catch (error) {
    console.error("Failed to fetch navigation from backend:", error);
    return [];
  }
}

// Permission-based navigation builder (2026-08-12)
// Maps nav keys to their required permissions
// NOTE: Updated to match actual permission names from CEO role in database
const NAV_PERMISSIONS = {
  // Recruitment Module (using actual permission names from database)
  candidates: "candidates",
  jobs: "jobs",
  candidateReview: "candidate_review.view",
  offerLetters: "offer-letters",
  offerLettersListing: "offer-letters",
  submissions: "submissions.view",
  interventionQueue: "intervention_queue.view",
  rehireApprovals: "rehire_approvals.view",
  riskDashboard: "risk_dashboard.view",
  thunderAnalytics: "thunder_analytics.view",
  bulkLaunch: "bulk_launch.view",

  // Sales/Client Module
  clientManagement: "clients",
  demandConfirmation: "demand.view",
  opportunityPipeline: "opportunities",
  partnerRoi: "partner_roi.view",

  // Workforce/HR Module
  employees: "employees",
  employeeConversion: "employees",  // convert uses employee.view permission
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
  usersAccessControl: "users",
  certifications: "certifications.view",
  tenantLocale: "locale.view",
  tenantAiConfig: "ai_config.view",
  messageQueueDashboard: "message_queue.view",
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
    const maxRetries = 12; // Retry every 5s for up to 60 seconds (0s, 5s, 10s, ..., 55s)
    const retryInterval = 5000; // 5 seconds
    let timeoutId = null;

    const refreshPermissions = async () => {
      try {
        const { getHrMe } = await import("../services/api/users");
        const user = await getHrMe();
        if (user) {
          // Update localStorage with fresh permissions (even if empty array)
          if (user.roles && Array.isArray(user.roles)) {
            localStorage.setItem("hrms_roles", JSON.stringify(user.roles));
          }
          if (user.permissions !== undefined) {
            // Store permissions even if empty - means we got a response
            localStorage.setItem("hrms_permissions", JSON.stringify(user.permissions || []));
            setPermissionsLoaded(true); // Trigger re-render with new permissions
            console.debug(`Permissions loaded: ${(user.permissions || []).length} permissions`);
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

  // Fetch navigation structure from backend based on role template permissions (all 175 resources)
  const [nav, setNav] = useState({
    standalone: [],
    groups: []
  });

  useEffect(() => {
    const loadNavigation = async () => {
      // Fetch pre-built navigation from backend (already filtered by user permissions)
      const navGroups = await fetchNavigationFromBackend();
      setNav({ standalone: [], groups: navGroups });
      console.debug("Navigation loaded:", { groupCount: navGroups.length });
    };

    loadNavigation();
  }, []); // Load once on component mount - backend already filters permissions

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
    // Handle both component and string icon formats
    const Icon = typeof n.icon === 'string'
      ? (ICON_COMPONENTS_BY_NAME[n.icon] || Briefcase)
      : (n.icon || Briefcase);
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
              {nav.standalone.map((n, idx) => (
                <div key={`standalone-${n.key || n.label || idx}`}>
                  {renderLink(n)}
                </div>
              ))}

              {nav.groups.map((group) => {
                // Backend returns icon as string name (e.g., "Users2"), convert to component
                const GroupIcon = ICON_COMPONENTS_BY_NAME[group.icon] || LayoutDashboard;
                // Use first item's route as the module's main page route
                const moduleRoute = group.items?.[0]?.path || `/${group.label.toLowerCase().replace(/\s+/g, '-')}`;
                const active = location.pathname.startsWith(moduleRoute.split('/')[1]);
                return (
                  <div key={group.label}>
                    <button
                      onClick={() => navigate(moduleRoute)}
                      className={cx(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
                        active
                          ? "bg-bx-orange text-white"
                          : "text-white/80 hover:bg-white/10 hover:text-white",
                      )}
                    >
                      <GroupIcon className="h-4 w-4" />
                      <span className="flex-1 text-left">{group.label}</span>
                    </button>
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
