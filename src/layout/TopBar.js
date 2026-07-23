import { useEffect, useMemo, useRef, useState } from "react";
import { Bell, Settings, Eye, EyeOff, Search } from "lucide-react";
import { Button } from "../components/ui";
import { getHrMe, changeHrMePassword } from "../services/api/users";
import { getNotifications, markNotificationRead } from "../services/api/notifications";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../utils/Routes";
import cx from "../utils/cx";

export default function TopBar({
  role,
  screen,
  setScreen,
  onLogout,
  candidates = [],
  jobs = [],
  setSelectedCandidateData,
  setSelectedJobId,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [profileData, setProfileData] = useState(null);

  const [showNewPassword, setShowNewPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [showSearchResults, setShowSearchResults] = useState(false);
  const dropdownRef = useRef(null);
  const searchRef = useRef(null);
  const navigate = useNavigate();

  // S-105/HRMS-P210 -- Portal Notification Center.
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);
  const notificationsRef = useRef(null);

  const loadNotifications = async () => {
    try {
      const res = await getNotifications();
      setNotifications(res?.notifications || []);
      setUnreadCount(res?.unread_count || 0);
    } catch {
      // Notification bell failures shouldn't block the rest of the shell.
    }
  };

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!showNotifications) return;
      if (notificationsRef.current && !notificationsRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showNotifications]);

  const handleMarkRead = async (notificationId) => {
    try {
      await markNotificationRead(notificationId);
      loadNotifications();
    } catch {
      // Best-effort -- the bell will just show the unread badge again next poll.
    }
  };

  const toggleProfile = () => setIsOpen(!isOpen);
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!isOpen) return;

      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);
  useEffect(() => {
    const handleSearchOutsideClick = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setShowSearchResults(false);
      }
    };

    document.addEventListener("mousedown", handleSearchOutsideClick);

    return () => {
      document.removeEventListener("mousedown", handleSearchOutsideClick);
    };
  }, []);
  useEffect(() => {
    setSearchTerm("");
    setShowSearchResults(false);
  }, [screen]);

  const handleViewProfile = async () => {
    try {
      const data = await getHrMe();
      setProfileData(data);
      setShowProfileModal(true);
    } catch {
      alert("Failed to fetch profile");
    }
  };

  const handleChangePassword = () => {
    setPasswordError("");
    setPasswordSuccess("");
    setShowPasswordModal(true);
  };
  const getSearchableText = (item, fields) =>
    fields
      .map((field) => {
        const value = item?.[field];
        if (Array.isArray(value)) {
          return value.join(" ");
        }
        return value || "";
      })
      .join(" ")
      .toLowerCase();
  const matchesSearch = (item, query, fields) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    const searchableText = getSearchableText(item, fields);
    const matchesKeyword = (keyword) => {
      const cleanKeyword = keyword.trim().toLowerCase();
      if (!cleanKeyword) return true;
      return searchableText.includes(cleanKeyword);
    };
    if (q.includes(" and ")) {
      return q.split(" and ").every((keyword) => matchesKeyword(keyword));
    }
    if (q.includes(" or ")) {
      return q.split(" or ").some((keyword) => matchesKeyword(keyword));
    }
    if (q.includes(" not ")) {
      const [includeKeyword, excludeKeyword] = q.split(" not ");
      return matchesKeyword(includeKeyword) && !matchesKeyword(excludeKeyword);
    }
    return matchesKeyword(q);
  };

  const crumbs = useMemo(() => {
    const map = {
      dashboard: ["Dashboard"],
      candidateSearch: ["Candidate Dashboard"],
      jobs: ["Jobs"],
      rbac: ["RBAC Settings"],
      hrUsers: ["List of Users"],
    };
    return map[screen] || ["Dashboard"];
  }, [screen]);
  const filteredCandidates = useMemo(() => {
    return candidates
      .filter((candidate) =>
        matchesSearch(candidate, searchTerm, [
          "name",
          "email",
          "phone",
          "jobTitle",
        ]),
      )
      .slice(0, 5);
  }, [candidates, searchTerm]);

  const filteredJobs = useMemo(() => {
    return jobs
      .filter((job) => matchesSearch(job, searchTerm, ["title", "location"]))
      .slice(0, 5);
  }, [jobs, searchTerm]);

  return (
    <>
      <div className="rounded-2xl border bg-white px-5 py-4 shadow-sm">
        <div className="flex justify-between items-center">
          <div className="flex w-full items-center">
            <div className="min-w-fit">
              <div className="text-base font-bold">
                {crumbs[crumbs.length - 1]}
              </div>
            </div>

            <div ref={searchRef} className="relative ml-6 flex-1 max-w-2xl">
              <Search className="absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setShowSearchResults(true);
                }}
                onFocus={() => setShowSearchResults(true)}
                placeholder="Search candidates or jobs..."
                className="
        w-full
        rounded-xl
        border
        border-gray-200
        bg-gray-50
        pl-10 pr-4
        py-2.5
        text-sm
        outline-none
        transition-all
        duration-200
       focus:border-black focus:ring-2 focus:ring-gray-200
        focus:bg-white
      "
              />

              {showSearchResults && searchTerm && (
                <div className="absolute top-14 z-50 max-h-96 w-full overflow-y-auto rounded-2xl border bg-white shadow-xl">
                  {filteredCandidates.length > 0 && (
                    <div className="border-b p-2">
                      <div className="px-3 py-2 text-xs font-semibold text-gray-500">
                        CANDIDATES
                      </div>

                      {filteredCandidates.map((candidate) => (
                        <button
                          key={candidate.id}
                          onClick={() => {
                            navigate(`/candidates/${candidate.id}`);
                            setShowSearchResults(false);
                            setSearchTerm("");
                          }}
                          className="flex w-full flex-col rounded-xl px-3 py-2 text-left hover:bg-gray-50"
                        >
                          <span className="text-sm font-medium">
                            {candidate.name}
                          </span>

                          {candidate.jobTitle && (
                            <span className="text-xs text-gray-600">
                              {candidate.jobTitle}
                            </span>
                          )}

                          <span className="text-xs text-gray-500">
                            {candidate.email}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}

                  {filteredJobs.length > 0 && (
                    <div className="p-2">
                      <div className="px-3 py-2 text-xs font-semibold text-gray-500">
                        JOBS
                      </div>

                      {filteredJobs.map((job) => (
                        <button
                          key={job.id}
                          onClick={() => {
                            navigate(`/jobs/${job.id}/workspace`);
                            setShowSearchResults(false);
                            setSearchTerm("");
                          }}
                          className="flex w-full flex-col rounded-xl px-3 py-2 text-left hover:bg-gray-50"
                        >
                          <span className="text-sm font-medium">
                            {job.title}
                          </span>

                          <span className="text-xs text-gray-500">
                            {job.location}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                  {filteredCandidates.length === 0 &&
                    filteredJobs.length === 0 && (
                      <div className="px-4 py-6 text-center text-sm text-gray-500">
                        No matching candidates or jobs found
                      </div>
                    )}
                </div>
              )}
            </div>

            <div className="ml-auto flex items-center gap-3">
              <div className="relative" ref={notificationsRef}>
                <button
                  onClick={() => setShowNotifications((v) => !v)}
                  className="relative"
                  aria-label="Notifications"
                >
                  <Bell className="h-5 w-5 cursor-pointer text-gray-500 hover:text-black transition" />
                  {unreadCount > 0 ? (
                    <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold text-white">
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                  ) : null}
                </button>

                {showNotifications ? (
                  <div className="absolute right-0 top-10 z-[9999] max-h-96 w-80 overflow-y-auto rounded-2xl border bg-white shadow-xl">
                    <div className="border-b px-4 py-2 text-xs font-semibold text-gray-500">
                      NOTIFICATIONS {unreadCount > 0 ? `(${unreadCount} unread)` : ""}
                    </div>
                    {notifications.length === 0 ? (
                      <div className="px-4 py-6 text-center text-sm text-gray-500">No notifications.</div>
                    ) : (
                      notifications.map((n) => (
                        <div
                          key={n.id}
                          className={cx(
                            "border-b px-4 py-2.5 text-sm last:border-b-0",
                            n.read_at ? "bg-white" : "bg-blue-50",
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-gray-800">{n.message}</span>
                            {!n.read_at ? (
                              <button
                                onClick={() => handleMarkRead(n.id)}
                                className="shrink-0 text-xs font-semibold text-blue-600 hover:underline"
                              >
                                Mark read
                              </button>
                            ) : null}
                          </div>
                          <div className="mt-0.5 text-[11px] text-gray-400">
                            {n.created_at ? new Date(n.created_at).toLocaleString() : ""}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ) : null}
              </div>

              <Settings className="h-5 w-5 cursor-pointer text-gray-500 hover:text-black transition" />

              <div className="relative" ref={dropdownRef}>
                <div
                  onClick={toggleProfile}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <div className="w-8 h-8 rounded-full bg-bx-navy text-white flex items-center justify-center">
                    {localStorage.getItem("hrms_user_name")?.[0] || "U"}
                  </div>

                  <span>{localStorage.getItem("hrms_user_name")}</span>
                </div>

                {isOpen && (
                  <div className="absolute right-0 top-10 z-[9999] bg-white border rounded-lg shadow-md w-48">
                    <p
                      onClick={() => {
                        handleViewProfile();
                        setIsOpen(false);
                      }}
                      className="p-2 hover:bg-gray-100 cursor-pointer"
                    >
                      View Profile
                    </p>

                    <p
                      onClick={() => {
                        handleChangePassword();
                        setIsOpen(false);
                      }}
                      className="p-2 hover:bg-gray-100 cursor-pointer"
                    >
                      Change Password
                    </p>

                    <p
                      onClick={onLogout}
                      className="p-2 text-red-500 hover:bg-gray-100 cursor-pointer"
                    >
                      Logout
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {showProfileModal && (
        <div
          onClick={() => setShowProfileModal(false)}
          className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white p-6 rounded-2xl w-96 shadow-2xl"
          >
            <h2 className="text-xl font-semibold mb-5">User Profile</h2>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Name</span>
                <span className="font-medium">{profileData?.user_name}</span>
              </div>

              <div className="flex justify-between">
                <span className="text-gray-500">Email</span>
                <span className="font-medium">{profileData?.user_email}</span>
              </div>

              <div className="flex justify-between">
                <span className="text-gray-500">Role</span>
                <span className="font-medium">{profileData?.user_role}</span>
              </div>
            </div>

            <button
              onClick={() => setShowProfileModal(false)}
              className="mt-6 w-full bg-bx-orange text-white py-2 rounded-xl hover:bg-bx-orange-hover transition"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {showPasswordModal && (
        <div
          onClick={() => setShowPasswordModal(false)}
          className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white p-6 rounded-2xl w-96 shadow-2xl"
          >
            <h2 className="text-xl font-semibold mb-5">Change Password</h2>

            <input
              id="current"
              type="text"
              placeholder="Current Password"
              className="w-full border border-gray-200 px-3 py-2 rounded-lg mb-3"
            />

            <div className="relative mb-3">
              <input
                id="new"
                type={showNewPassword ? "text" : "password"}
                placeholder="New Password"
                className="w-full border border-gray-200 px-3 py-2 rounded-lg pr-10"
              />

              <span
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-2.5 cursor-pointer text-gray-500"
              >
                {showNewPassword ? (
                  <EyeOff className="h-5 w-5" />
                ) : (
                  <Eye className="h-5 w-5" />
                )}
              </span>
            </div>

            {passwordError && (
              <p className="text-red-500 text-sm mb-2">{passwordError}</p>
            )}

            {passwordSuccess && (
              <p className="text-green-600 text-sm mb-2">{passwordSuccess}</p>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => setShowPasswordModal(false)}
                className="w-1/2 border border-gray-300 py-2 rounded-xl hover:bg-gray-100"
              >
                Cancel
              </button>

              <button
                onClick={async () => {
                  const current = document.getElementById("current").value;
                  const newPass = document.getElementById("new").value;

                  if (!current || !newPass) {
                    setPasswordError("Please fill all fields");
                    return;
                  }

                  try {
                    await changeHrMePassword({
                      current_password: current,
                      new_password: newPass,
                    });

                    setPasswordError("");
                    setPasswordSuccess("Password updated successfully");

                    setTimeout(() => {
                      setShowPasswordModal(false);
                      setPasswordSuccess("");
                    }, 1500);
                  } catch (error) {
                    setPasswordError(
                      error.message || "Current password is incorrect",
                    );
                    setPasswordSuccess("");
                  }
                }}
                className="w-1/2 bg-bx-orange text-white py-2 rounded-xl hover:bg-bx-orange-hover"
              >
                Update
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
