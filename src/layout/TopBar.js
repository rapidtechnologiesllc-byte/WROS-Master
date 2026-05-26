import { useEffect, useMemo, useRef, useState } from "react";
import { Bell, Settings, Eye, EyeOff, Search } from "lucide-react";
import { Button } from "../components/ui";
import { getHrMe, changeHrMePassword } from "../services/api/users";

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
  const filteredCandidates = candidates
    .filter((candidate) => {
      const query = searchTerm.trim().toLowerCase();

      return (
        candidate.name?.toLowerCase().includes(query) ||
        candidate.email?.toLowerCase().includes(query) ||
        candidate.phone?.toLowerCase().includes(query)
      );
    })
    .slice(0, 5);

  const filteredJobs = jobs
    .filter((job) => {
      const query = searchTerm.trim().toLowerCase();

      return (
        job.title?.toLowerCase().includes(query) ||
        job.location?.toLowerCase().includes(query) ||
        job.skills?.some((skill) => skill.toLowerCase().includes(query))
      );
    })
    .slice(0, 5);

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
                            setSelectedCandidateData(candidate);
                            setScreen("candidateDetails");
                            setShowSearchResults(false);
                            setSearchTerm("");
                          }}
                          className="flex w-full flex-col rounded-xl px-3 py-2 text-left hover:bg-gray-50"
                        >
                          <span className="text-sm font-medium">
                            {candidate.name}
                          </span>

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
                            setSelectedJobId(job.id);
                            setScreen("jobWorkspace");
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
              <Bell className="h-5 w-5 cursor-pointer text-gray-500 hover:text-black transition" />

              <Settings className="h-5 w-5 cursor-pointer text-gray-500 hover:text-black transition" />

              <div className="relative" ref={dropdownRef}>
                <div
                  onClick={toggleProfile}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center">
                    {localStorage.getItem("hrms_user_name")?.[0] || "U"}
                  </div>

                  <span>{localStorage.getItem("hrms_user_name")}</span>
                </div>

                {isOpen && (
                  <div className="absolute right-0 top-10 bg-white border rounded-lg shadow-md w-48">
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
              className="mt-6 w-full bg-gray-900 text-white py-2 rounded-xl hover:bg-gray-800 transition"
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
                className="w-1/2 bg-gray-900 text-white py-2 rounded-xl hover:bg-gray-800"
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
