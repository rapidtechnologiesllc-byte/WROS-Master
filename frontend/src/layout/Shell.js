import { useEffect, useState } from "react";
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
  Building2,
  MapPin,
  Network,
  Award,
  Target,
  KeyRound,
  Linkedin,
} from "lucide-react";
import cx from "../utils/cx";
import TopBar from "./TopBar";
import FlashWidget from "../components/FlashWidget";
import { useLocation, useNavigate } from "react-router-dom";
import { Outlet } from "react-router-dom";

// Constants

// MODULE_CONFIG removed: backend permission system filters navigation items

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
  "my_performance": Target,
  "profile": UserPlus,
  "users_access_control": Shield,
  "certifications": Award,
  "business_units": Building2,
  "delivery_centers": MapPin,
  "organizational_hierarchy": Network,
  "goals": Target,
  "api_keys": KeyRound,
  "executive_revenue_dashboard": LineChart,
  "revenue": TrendingUp,
  "agents": Bot,
  "projects": FolderKanban,
  "clients": Globe2,
  "opportunities": TrendingUp,
  "offer_letters": FileTextIcon,
  "submissions": Send,
  "allocations": CalendarCheck2,
  "expenses": BadgeDollarSign,
  "notifications": MessageSquareText,
  "error_logs": AlertOctagon,
  "audit_logs": ShieldAlert,
  "configuration": Settings,
};

// Nav item keys arrive as resource names ("role-templates"); the map uses underscores.
const iconForResource = (key) => ICON_MAP_BY_RESOURCE[String(key || "").replace(/-/g, "_")] || Briefcase;

// Map icon names (strings from backend) to icon components
const ICON_COMPONENTS_BY_NAME = {
  "Linkedin": Linkedin,
  "LayoutDashboard": LayoutDashboard,
  "Bot": Bot,
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

// Menu from the backend (already filtered by the role template's permissions); each item
// carries its route, so the client keeps no path table of its own.
async function fetchNavigationFromBackend() {
  const { getNavigationGroups } = await import("../services/api/navigation");
  const groups = await getNavigationGroups();
  return groups.map((group) => ({
    ...group,
    items: group.items.map((item) => ({
      key: item.key,
      label: item.label,
      icon: iconForResource(item.key),
      path: item.route,
    })),
  }));
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
  const [, setPermissionsLoaded] = useState(false);

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
          if (user.authority) {
            // home dashboard and leadership flags follow role changes without a re-login
            localStorage.setItem("hrms_authority", JSON.stringify(user.authority));
          }
          if (user.permissions !== undefined) {
            // Store permissions even if empty - means we got a response
            localStorage.setItem("hrms_permissions", JSON.stringify(user.permissions || []));
            setPermissionsLoaded(true); // Trigger re-render with new permissions
            return true; // Success, stop retrying
          }
        }
      } catch (error) {
        if (retryCount >= maxRetries - 1) {
          throw new Error(`Failed to refresh permissions after ${maxRetries} attempts: ${error.message}`);
        }
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


  // Fetch navigation structure from backend based on role template permissions (all 175 resources)
  const [nav, setNav] = useState({
    standalone: [],
    groups: []
  });

  useEffect(() => {
    const loadNavigation = async () => {
      try {
        // Fetch pre-built navigation from backend (already filtered by user permissions)
        // Backend returns only items the user has permission to see - no frontend filtering needed
        const navGroups = await fetchNavigationFromBackend();

        setNav({ standalone: [], groups: navGroups });} catch (error) {
        console.error("Failed to load navigation:", error);
        // Fallback: try loading again with no special handling
        try {
          const navGroups = await fetchNavigationFromBackend();
          setNav({ standalone: [], groups: navGroups });
        } catch (retryError) {
          console.error("Navigation reload failed:", retryError);
          // CRITICAL FIX: Show error banner instead of empty navigation
          setNav({
            standalone: [],
            groups: [{
              label: "Error",
              icon: "AlertCircle",
              items: [{
                key: "nav-error",
                label: `Navigation failed to load: ${retryError.message}. Please refresh the page.`,
                icon: "AlertOctagon",
                path: "#"
              }]
            }]
          });
        }
      }
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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <div className="flex w-full gap-6 px-4 py-6">
        <aside className="hidden w-64 shrink-0 md:block">
          <div className="rounded-2xl bg-bx-navy dark:bg-gray-800 p-4 shadow-sm">
            {/* The logo is Home ("/"): Home is not a menu item (CEO 2026-10-24) */}
            <button type="button" onClick={() => navigate("/")} aria-label="Home"
              className="mb-3 block rounded-lg text-left focus:outline-none focus:ring-2 focus:ring-white/40">
              <div className="text-xs font-semibold text-white/60">BlitzenX</div>
              <div className="text-lg font-extrabold tracking-tight text-white">
                WROS
              </div>
            </button>

            <nav className="space-y-1">
              {nav.standalone && nav.standalone.length > 0 && nav.standalone.map((n, idx) => (
                <div key={`standalone-${n.key || n.label || idx}`}>
                  {renderLink(n)}
                </div>
              ))}

              {nav.groups && nav.groups.length > 0 && nav.groups.map((group) => {
                // Backend returns icon as string name (e.g., "Users2"), convert to component
                const GroupIcon = ICON_COMPONENTS_BY_NAME[group.icon] || LayoutDashboard;
                const isOpen = openGroups.has(group.label);
                // Check if any item in this group matches current path
                const hasActiveItem = group.items?.some(
                  (item) => location.pathname === item.path || location.pathname.startsWith(item.path + '/')
                );

                return (
                  <div key={group.label}>
                    <button
                      onClick={() => toggleGroup(group.label)}
                      className={cx(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
                        hasActiveItem || isOpen
                          ? "text-white bg-bx-orange/20"
                          : "text-white/80 hover:bg-white/10 hover:text-white",
                      )}
                    >
                      <GroupIcon className="h-4 w-4" />
                      <span className="flex-1 text-left">{group.label}</span>
                      {group.items && group.items.length > 0 && (
                        <ChevronDown
                          className={cx(
                            "h-3.5 w-3.5 text-white/50 transition-transform",
                            isOpen ? "rotate-180" : "",
                          )}
                        />
                      )}
                    </button>

                    {isOpen && group.items && group.items.length > 0 && (
                      <div className="ml-3 mt-1 space-y-1 border-l border-white/10 pl-3">
                        {group.items.map((item, idx) => {
                          const ItemIcon = typeof item.icon === 'string'
                            ? (ICON_COMPONENTS_BY_NAME[item.icon] || Briefcase)
                            : (item.icon || Briefcase);
                          const itemActive = location.pathname === item.path;
                          const uniqueKey = `${group.label}-${item.key}-${idx}`;

                          return (
                            <button
                              key={uniqueKey}
                              onClick={() => navigate(item.path)}
                              className={cx(
                                "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition",
                                itemActive
                                  ? "bg-bx-orange text-white"
                                  : "text-white/70 hover:bg-white/10 hover:text-white",
                              )}
                            >
                              <ItemIcon className="h-3.5 w-3.5 flex-shrink-0" />
                              <span className="flex-1 truncate text-left" title={item.label}>{item.label}</span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}

              {(!nav.standalone || nav.standalone.length === 0) && (!nav.groups || nav.groups.length === 0) && (
                <div className="rounded-lg bg-yellow-50/10 border border-yellow-200/30 p-3 mt-4">
                  <div className="text-xs font-semibold text-yellow-200 mb-2">No Access</div>
                  <p className="text-xs text-white/70 leading-relaxed">
                    You don't have permission to access any modules yet. Contact your administrator to assign roles or permissions.
                  </p>
                  <button
                    onClick={onLogout}
                    className="mt-3 text-xs px-2 py-1 bg-yellow-600/30 hover:bg-yellow-600/50 text-yellow-100 rounded border border-yellow-200/30 transition"
                  >
                    Logout & Try Again
                  </button>
                </div>
              )}
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
      <FlashWidget />
    </div>
  );
}
