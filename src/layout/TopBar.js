// Top navigation bar with breadcrumbs and actions.
import { useMemo,useState  } from "react";
import { Plus, Search, Bell, Settings } from "lucide-react";
import { Button } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";
import { getHrMe, changeHrMePassword } from "../services/api/users";

export default function TopBar({ role, screen, setScreen, onLogout }) {
  const [isOpen, setIsOpen] = useState(false);

const toggleProfile = () => {
  setIsOpen(!isOpen);
};
const handleViewProfile = async () => {
  try {
    const data = await getHrMe();

    alert(
      `Name: ${data.user_name}\nEmail: ${data.user_email}\nRole: ${data.user_role}`
    );
  } catch (error) {
    alert("Failed to fetch profile");
  }
};
const handleChangePassword = async () => {
  try {
    const currentPassword = prompt("Enter current password");
    const newPassword = prompt("Enter new password");

    if (!currentPassword || !newPassword) {
      alert("Both fields are required");
      return;
    }

    await changeHrMePassword({
      current_password: currentPassword,
      new_password: newPassword
    });

    alert("Password changed successfully");
  } catch (error) {
    alert("Failed to change password");
  }
};
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
      
      {/* LEFT SIDE */}
      <div>
        <div className="text-base font-extrabold tracking-tight">
          {crumbs[crumbs.length - 1]}
        </div>
        <div className="mt-1 text-xs text-gray-600">
          {crumbs.join("  /  ")}
        </div>
      </div>

      {/* RIGHT SIDE */}
      <div className="flex items-center gap-3">

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

        {/* Notification */}
        <button className="p-2 rounded-full hover:bg-gray-100 transition">
          <Bell className="h-5 w-5 text-gray-600" />
        </button>

        {/* Settings */}
        <button className="p-2 rounded-full hover:bg-gray-100 transition">
          <Settings className="h-5 w-5 text-gray-600" />
        </button>

        {/* USER SECTION */}
        <div className="relative">

  {/* USER SECTION */}
  <div
    onClick={toggleProfile}
    className="flex items-center gap-3 rounded-2xl bg-gradient-to-r from-gray-50 to-gray-100 px-3 py-2 shadow-sm hover:shadow-md transition cursor-pointer border border-gray-200"
  >
    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-gray-800 to-gray-600 text-white text-sm font-bold shadow">
      {localStorage.getItem("hrms_user_name")?.[0] || "U"}
    </div>

    <div className="leading-tight">
      <p className="text-sm font-semibold text-gray-800">
        {localStorage.getItem("hrms_user_name") || "User"}
      </p>
      <p className="text-xs text-gray-500">{role}</p>
    </div>
  </div>

  {/* DROPDOWN */}
  {isOpen && (
  <div className="absolute right-0 top-12 w-52 bg-white border border-gray-200 rounded-2xl shadow-lg z-50 overflow-hidden">

    {/* Header */}
    <div className="px-4 py-3 border-b bg-gray-50">
      <p className="text-sm font-semibold text-gray-800">
        {localStorage.getItem("hrms_user_name") || "User"}
      </p>
      <p className="text-xs text-gray-500">{role}</p>
    </div>

    {/* Actions */}
    <div className="py-1">
      <p
        onClick={() => {
          handleViewProfile();
          setIsOpen(false);
        }}
        className="px-4 py-2 text-sm hover:bg-gray-100 cursor-pointer transition"
      >
        View Profile
      </p>

      <p
        onClick={() => {
          handleChangePassword();
          setIsOpen(false);
        }}
        className="px-4 py-2 text-sm hover:bg-gray-100 cursor-pointer transition"
      >
        Change Password
      </p>

      <p
        onClick={onLogout}
        className="px-4 py-2 text-sm text-red-500 hover:bg-red-50 cursor-pointer transition"
      >
        Logout
      </p>
    </div>

  </div>
)}

</div>
      </div>
    </div>
  </div>
  );
}
