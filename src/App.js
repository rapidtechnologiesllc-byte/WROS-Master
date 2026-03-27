// App entry: auth guard, role routing, and screen orchestration.
import { useCallback, useEffect, useMemo, useState } from "react";
import AuthPage from "./pages/AuthPage";
import Shell from "./layout/Shell";
import Approval from "./screens/Approval";
import AssignmentsScreen from "./screens/AssignmentsScreen";
import CandidateCreate from "./screens/CandidateCreate";
import CandidateSearch from "./screens/CandidateSearch";
import CandidateSelfService from "./screens/CandidateSelfService";
import Dashboard from "./screens/Dashboard";
import Documents from "./screens/Documents";
import ActiveJobs from "./screens/ActiveJobs";
import InterviewSchedule from "./screens/InterviewSchedule";
import InterviewStatus from "./screens/InterviewStatus";
import InterviewAnalytics from "./screens/InterviewAnalytics";
import HrUserManagement from "./screens/HrUserManagement";
import JobCreate from "./screens/JobCreate";
import JobDetails from "./screens/JobDetails";
import JobsOverview from "./screens/JobsOverview";
import MatchingJobs from "./screens/MatchingJobs";
import NewsletterScreen from "./screens/NewsletterScreen";
import OfferScreen from "./screens/OfferScreen";
import PreOnboarding from "./screens/PreOnboarding";
import RbacSettingsScreen from "./screens/RbacSettingsScreen";
import Verification from "./screens/Verification";
import { getAllInterviews, updateInterview } from "./services/api/interviews";
import {
  getAllCandidates,
  getCandidateById,
  updateCandidate,
  deleteCandidate
} from "./services/api/candidates";
import {
  approveJob,
  deleteJob,
  getAllJobs,
  updateJob,
  postJobOnLinkedIn
} from "./services/api/jobs";
import { applyForJob } from "./services/api/jobs";
import {
  createOfferLetter,
  getAllOffers,
  getOfferById,
  updateOfferLetter,
  cancelOfferLetter
} from "./services/api/offerLetters";
import { getAllUsers } from "./services/api/users";

// Helpers to normalize API responses into UI-friendly models
const mapCandidateFromApi = (c) => {
  const parseSkills = (raw) => {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.map((s) => String(s).trim()).filter(Boolean);
    return String(raw)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  };

  return {
    id: c.candidate_id,
    name: c.candidate_name,
    email: c.candidate_email,
    phone: c.candidate_mobile || "",
    skills: parseSkills(c.candidate_skills),
    status: c.candidate_is_verified ? "Verified" : "New",
    jobTitle: c.candidate_job_title || "",

    // Extra fields for edit form prefill (best-effort).
    gender: c.candidate_gender || "",
    dob: c.candidate_date_of_birth || "",
    source: c.candidate_source || "",
    experience: c.candidate_experience || "",
    joiningDate: c.candidate_joining_date || "",
    expectedSalary: c.candidate_expected_salary || "",
    currentSalary: c.candidate_current_salary || "",
    currentLocation: c.candidate_current_location || "",
    assignedHrManagerId: c.assigned_hr_manager_id || "",
    assignedReportManagerId: c.assigned_report_manager_id || ""
  };
};

const mapJobFromApi = (j, users = []) => {
  const usersList = Array.isArray(users) ? users : [];
  const hmId = j?.hiring_manager_id || "";
  const hmUser = usersList.find(
    (u) => String(u?.user_id || "") === String(hmId || "")
  );
  const hiringManagerName =
    hmUser?.user_name || hmUser?.user_email || (hmId ? String(hmId) : "");

  return ({
  id: j.job_id,
  title: j.job_title,
  dept: "",
  location: j.job_location || "",
  skills: String(j.job_skills || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  hiringManager: hmId,
  hiringManagerName,
  status: (() => {
    const raw = String(j.job_status || "").trim().toLowerCase();
    if (raw === "active") return "Open";
    if (raw === "public") return "Public";
    if (raw === "draft") return "Draft";
    if (raw === "submitted") return "Submitted";
    if (raw === "pending_approval") return "Pending Approval";
    if (raw === "closed") return "Closed";
    // Keep unknown statuses as-is (but preserve original casing from API if possible).
    return j.job_status || "Draft";
  })(),
  experienceLevel: j.job_experience || "",
  companyType: j.company_type || "",
  companyClient: j.company_name || "",
  contactPerson: j.contact_person || "",
  startDate: j.start_date || "",
  endDate: j.end_date || "",
  jobDescription: j.job_description || ""
  });
};

const normalizeJobStatusForApi = (uiStatus) => {
  const raw = String(uiStatus || "").trim();
  const lower = raw.toLowerCase();
  if (lower === "open") return "active";
  if (lower === "public") return "public";
  if (lower === "draft") return "draft";
  if (lower === "submitted") return "submitted";
  if (lower === "closed") return "closed";
  return lower;
};

const normalizeRole = (rawRole) => {
  const upper = String(rawRole || "").trim().toUpperCase();
  if (["SUPER USER", "SUPER_USER", "SUPERUSER"].includes(upper)) {
    return "SUPER_USER";
  }
  if (["ADMIN", "HR", "RECRUITER", "CANDIDATE"].includes(upper)) {
    return upper;
  }
  return upper || "RECRUITER";
};

export default function App() {
  const token = localStorage.getItem("hrms_token");
  // Auth guard: unauthenticated users or auth routes land on AuthPage.
  if (!token || window.location.pathname.startsWith("/auth")) {
    return <AuthPage />;
  }

  const storedRole = localStorage.getItem("hrms_role");
  const normalizedRole = normalizeRole(storedRole);
  const isAdminOrSuperUser = normalizedRole === "ADMIN" || normalizedRole === "SUPER_USER";
  const isSuperUser = normalizedRole === "SUPER_USER";

  const handleLogout = () => {
    // Clear all identity context from storage on logout.
    localStorage.removeItem("hrms_token");
    localStorage.removeItem("hrms_role");
    localStorage.removeItem("hrms_user_name");
    localStorage.removeItem("hrms_user_email");
    localStorage.removeItem("hrms_candidate_id");
    window.location.href = "/";
  };

  // Candidate users bypass the HR shell and land on their portal.
  if (normalizedRole === "CANDIDATE") {
    return <CandidateSelfService onLogout={handleLogout} />;
  }

  const [role, setRole] = useState(normalizedRole);
  const [screen, setScreen] = useState("dashboard");

  const [candidates, setCandidates] = useState([
    {
      id: "C-1001",
      name: "Asha Reddy",
      email: "asha@example.com",
      phone: "+1 555 0101",
      skills: ["React", "TypeScript", "Node"],
      status: "Applied"
    },
    {
      id: "C-1002",
      name: "Rahul Verma",
      email: "rahul@example.com",
      phone: "+1 555 0102",
      skills: ["Java", "Spring", "SQL"],
      status: "Interview Scheduled"
    }
  ]);

  const [jobs, setJobs] = useState([
    {
      id: "J-2001",
      title: "Frontend Engineer",
      dept: "Digital",
      location: "Remote",
      skills: ["React", "TypeScript"],
      hiringManager: "Sanjay",
      status: "Open"
    },
    {
      id: "J-2002",
      title: "Backend Engineer",
      dept: "Platform",
      location: "Kansas City",
      skills: ["Java", "Spring"],
      hiringManager: "Avinash",
      status: "Submitted"
    }
  ]);

  const [interviews, setInterviews] = useState([
    {
      id: 3001,
      panelId: 1,
      panelRoundName: "Technical",
      candidateId: "C-1002",
      startTime: "2026-01-25T10:00:00",
      endTime: "2026-01-25T11:00:00",
      meetingLink: "",
      status: "Scheduled"
    }
  ]);

  const [offer, setOffer] = useState({
    candidateId: "",
    jobId: "",
    hiringManagerId: "",
    reportingManagerId: "",
    position: "",
    salary: 0,
    startDate: "",
    joiningDate: "",
    state: "Draft"
  });

  const [offers, setOffers] = useState([]);
  const [users, setUsers] = useState([]);
  const [offerLoading, setOfferLoading] = useState(false);
  const [offerError, setOfferError] = useState("");

  const [selectedCandidateId, setSelectedCandidateId] = useState(
    candidates[0]?.id || ""
  );
  const [selectedJobId, setSelectedJobId] = useState(jobs[0]?.id || "");
  const [jobDetailsMode, setJobDetailsMode] = useState("view");
  const [jobCreateMode, setJobCreateMode] = useState("create");

  const selectedCandidate = useMemo(
    () => candidates.find((c) => c.id === selectedCandidateId) || candidates[0],
    [candidates, selectedCandidateId]
  );
  const selectedJob = useMemo(
    () => jobs.find((j) => j.id === selectedJobId) || jobs[0],
    [jobs, selectedJobId]
  );

  const notify = useCallback((title, message) => {
    alert(`${title}\n\n${message}`);
  }, []);

  const refreshJobs = useCallback(async () => {
    const refreshed = await getAllJobs();
    const mappedJobs = (refreshed?.jobs || []).map((j) => mapJobFromApi(j, users));
    setJobs(mappedJobs);
    if (!selectedJobId && mappedJobs.length) {
      setSelectedJobId(mappedJobs[0].id);
    }
  }, [selectedJobId, users]);

  const mapInterviews = useCallback((interviewRes) => {
    return (interviewRes || []).map((i) => ({
      id: i.id,
      panelId: i.panel_id,
      panelRoundName: i.panel_round_name,
      candidateId: i.candidate_id,
      startTime: i.start_time,
      endTime: i.end_time,
      meetingLink: i.meeting_link || "",
      outlookEventId: i.outlook_event_id || "",
      status: i.status
    }));
  }, []);

  const refreshInterviews = useCallback(async () => {
    const refreshed = await getAllInterviews();
    setInterviews(mapInterviews(refreshed));
  }, [mapInterviews]);

  const refreshOffers = useCallback(async () => {
    try {
      const res = await getAllOffers();
      setOffers(res?.offers || []);
    } catch (err) {
      setOffers([]);
    }
  }, []);

  const refreshCandidates = useCallback(async () => {
    try {
      const res = await getAllCandidates();
      const mapped = (res?.candidates || []).map(mapCandidateFromApi);
      setCandidates(mapped);
    } catch (err) {
      notify("Candidates", err.message || "Failed to refresh candidates.");
    }
  }, [notify]);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      try {
        const [candidateRes, jobRes, interviewRes, offersRes, usersRes] =
          await Promise.all([
            getAllCandidates(),
            getAllJobs(),
            getAllInterviews(),
            getAllOffers(),
            getAllUsers()
          ]);

        if (!isMounted) return;

        setOffers(offersRes?.offers || []);
        setUsers(usersRes?.users || []);

        const mappedCandidates = (candidateRes?.candidates || []).map(
          mapCandidateFromApi
        );

        const mappedJobs = (jobRes?.jobs || []).map((j) =>
          mapJobFromApi(j, usersRes?.users || [])
        );

        const mappedInterviews = mapInterviews(interviewRes);

        setCandidates(mappedCandidates);
        setJobs(mappedJobs);
        setInterviews(mappedInterviews);

        if (!selectedCandidateId && mappedCandidates.length) {
          setSelectedCandidateId(mappedCandidates[0].id);
        }
        if (!selectedJobId && mappedJobs.length) {
          setSelectedJobId(mappedJobs[0].id);
        }
      } catch (err) {
        if (!isMounted) return;
        notify("Load", err.message || "Failed to load data.");
      }
    };

    loadData();
    return () => {
      isMounted = false;
    };
  }, [notify, mapInterviews]);

  const safeSetScreen = (next) => {
    const hmOnly = ["approval"];
    const normalizedCurrentRole = normalizeRole(role);
    const canUseHrScreens =
      normalizedCurrentRole === "HR" ||
      normalizedCurrentRole === "ADMIN" ||
      normalizedCurrentRole === "SUPER_USER";
    const canUseAdminScreens =
      normalizedCurrentRole === "ADMIN" || normalizedCurrentRole === "SUPER_USER";

    if (hmOnly.includes(next) && !canUseHrScreens) {
      notify("Access", "Approval screen requires HR or Admin role.");
      return;
    }
    if (next === "rbac" && !canUseAdminScreens) {
      notify("Access", "RBAC Settings requires Admin role.");
      return;
    }
    if ((next === "activeJobs" || next === "interviewAnalytics") && !canUseHrScreens) {
      notify("Access", "This screen requires HR or Admin role.");
      return;
    }
    if (next === "hrUsers" && !canUseAdminScreens) {
      notify("Access", "HR Users requires Admin role.");
      return;
    }
    setScreen(next);
    if (next === "offer" && selectedCandidate && selectedJob) {
      const existing = offers.find(
        (o) =>
          o.candidate_id === selectedCandidate.id &&
          o.job_id === selectedJob.id &&
          o.offer_status === "Pending"
      );
      if (existing) {
        setOffer((prev) => ({
          ...prev,
          candidateId: selectedCandidate.id,
          jobId: selectedJob.id,
          hiringManagerId: existing.hiring_manager_id,
          reportingManagerId: existing.reporting_manager_id,
          position: existing.position,
          salary: Number(existing.salary) || 0,
          startDate: existing.joining_date || "",
          joiningDate: existing.joining_date || ""
        }));
      } else {
        setOffer((prev) => ({
          ...prev,
          candidateId: selectedCandidate.id,
          jobId: selectedJob.id,
          hiringManagerId: selectedJob.hiringManager || "",
          reportingManagerId: prev.reportingManagerId || selectedJob.hiringManager || "",
          position: selectedJob.title || "",
          salary: prev.salary || 0,
          startDate: prev.startDate || "",
          joiningDate: prev.startDate || ""
        }));
      }
      setOfferError("");
    }
  };

  return (
    <Shell
      role={role}
      screen={screen}
      setScreen={safeSetScreen}
      onLogout={handleLogout}
    >
      {screen === "dashboard" && (
        <Dashboard
          candidates={candidates}
          jobs={jobs}
          interviews={interviews}
          offers={offers}
          onGo={(s) => safeSetScreen(s)}
        />
      )}

      {screen === "assignments" && <AssignmentsScreen />}

      {screen === "candidateSearch" && (
        <CandidateSearch
          candidates={candidates}
          jobs={jobs}
          selectedCandidateId={selectedCandidateId}
          setSelectedCandidateId={setSelectedCandidateId}
          selectedJobId={selectedJobId}
          setSelectedJobId={setSelectedJobId}
          onCreateCandidate={() => safeSetScreen("candidateCreate")}
          onMatchingJobs={() => safeSetScreen("matchingJobs")}
          onInterviewSchedule={() => safeSetScreen("interviewSchedule")}
          onUpdateCandidate={async (candidateId, payload) => {
            try {
              await updateCandidate(candidateId, payload);
              await refreshCandidates();
              notify("Candidate", "Candidate updated.");
            } catch (err) {
              notify("Candidate", err.message || "Failed to update candidate.");
            }
          }}
          onDeleteCandidate={async (candidateId) => {
            if (!window.confirm(`Delete candidate ${candidateId}?`)) return;
            try {
              await deleteCandidate(candidateId);
              await refreshCandidates();
              setSelectedCandidateId(candidates.find((c) => c.id !== candidateId)?.id || "");
              notify("Candidate", "Candidate deleted.");
            } catch (err) {
              notify("Candidate", err.message || "Failed to delete candidate.");
            }
          }}
          onFetchCandidateById={async (candidateId) => {
            const res = await getCandidateById(candidateId);
            return mapCandidateFromApi(res || {});
          }}
        />
      )}

      {screen === "candidateCreate" && (
        <CandidateCreate
          onBack={() => safeSetScreen("candidateSearch")}
          onSave={(c) => {
            setCandidates((prev) => [c, ...prev]);
            setSelectedCandidateId(c.id);
            notify("Candidate", `Created ${c.name} (${c.id})`);
            safeSetScreen("candidateSearch");
          }}
        />
      )}

      {screen === "jobs" && (
        <JobsOverview
          jobs={jobs}
          onCreate={() => {
            setJobCreateMode("create");
            safeSetScreen("jobCreate");
          }}
          onViewJob={(jobId) => {
            setSelectedJobId(jobId);
            setJobCreateMode("view");
            safeSetScreen("jobCreate");
          }}
          onOpenJob={(jobId) => {
            setSelectedJobId(jobId);
            setJobDetailsMode("edit");
            safeSetScreen("jobDetails");
          }}
          onPostToLinkedIn={async (jobId) => {
            try {
              const res = await postJobOnLinkedIn(jobId);
              notify("LinkedIn", res?.message || "Job posted to LinkedIn.");
            } catch (err) {
              notify("LinkedIn", err.message || "Failed to post to LinkedIn.");
            }
          }}
          onApproveJob={async (jobId) => {
            try {
              const response = await approveJob(jobId);
              await refreshJobs();
              notify("Job", response?.message || `Approved job ${jobId}.`);
            } catch (err) {
              notify("Job", err.message || "Failed to approve job.");
            }
          }}
          onDeleteJob={
            isSuperUser
              ? async (jobId) => {
                  const ok = window.confirm(`Delete job ${jobId}?`);
                  if (!ok) return;
                  try {
                    await deleteJob(jobId);
                    await refreshJobs();
                    notify("Job", `Deleted job ${jobId}.`);
                  } catch (err) {
                    notify("Job", err.message || "Failed to delete job.");
                  }
                }
              : undefined
          }
        />
      )}

      {screen === "activeJobs" && (
        <ActiveJobs
          onCreate={() => {
            setJobCreateMode("create");
            safeSetScreen("jobCreate");
          }}
          onViewJob={(jobId) => {
            setSelectedJobId(jobId);
            setJobCreateMode("view");
            safeSetScreen("jobCreate");
          }}
          onOpenJob={(jobId) => {
            setSelectedJobId(jobId);
            setJobDetailsMode("edit");
            safeSetScreen("jobDetails");
          }}
          onPostToLinkedIn={async (jobId) => {
            try {
              const res = await postJobOnLinkedIn(jobId);
              notify("LinkedIn", res?.message || "Job posted to LinkedIn.");
            } catch (err) {
              notify("LinkedIn", err.message || "Failed to post to LinkedIn.");
            }
          }}
          onDeleteJob={
            isSuperUser
              ? async (jobId) => {
                  const ok = window.confirm(`Delete job ${jobId}?`);
                  if (!ok) return;
                  try {
                    await deleteJob(jobId);
                    await refreshJobs();
                    notify("Job", `Deleted job ${jobId}.`);
                  } catch (err) {
                    notify("Job", err.message || "Failed to delete job.");
                  }
                }
              : undefined
          }
        />
      )}

      {screen === "interviewAnalytics" && (
        <InterviewAnalytics candidates={candidates} users={users} />
      )}

      {screen === "hrUsers" && <HrUserManagement />}

      {screen === "jobCreate" && (
        <JobCreate
          mode={jobCreateMode}
          initialJob={jobCreateMode === "view" ? selectedJob : null}
          onSave={(j) => {
            setJobs((prev) => [j, ...prev]);
            setSelectedJobId(j.id);
            notify("Job", `Created job ${j.title} (${j.id})`);
            safeSetScreen("jobDetails");
          }}
        />
      )}

      {screen === "jobDetails" && selectedJob && (
        <JobDetails
          job={selectedJob}
          mode={jobDetailsMode}
          onUpdate={async (next) => {
            try {
              const payload = {
                job_title: next.title,
                job_description: next.internalJD || next.jobDescription,
                job_skills: (next.skills || []).join(", "),
                job_experience: next.experienceLevel,
                job_location: next.location,
                company_type: next.companyType,
                company_name: next.companyClient,
                contact_person: next.contactPerson,
                job_status: normalizeJobStatusForApi(next.jobStatus || next.status),
                no_of_positions: Number(next.noOfPositions ?? 0),
                // Only include hiring_manager_id when we have a non-empty value.
                ...(next.hiringManager || selectedJob?.hiringManager
                  ? { hiring_manager_id: next.hiringManager || selectedJob?.hiringManager }
                  : {}),
                // Only send dates if they have values; backend schema expects Optional[date].
                ...((next.startDate || "").trim() ? { start_date: next.startDate } : {}),
                ...((next.endDate || "").trim() ? { end_date: next.endDate } : {})
              };
              await updateJob(selectedJob.id, payload);
              await refreshJobs();
              notify("Job", `Updated job ${next.title} (${selectedJob.id})`);
            } catch (err) {
              notify("Job", err.message || "Failed to update job.");
            }
          }}
          onSubmit={() => {
            setJobs((prev) =>
              prev.map((x) =>
                x.id === selectedJob.id ? { ...x, status: "Submitted" } : x
              )
            );
            notify("Submitted", "Submitted to internal hiring team (simulated).");
          }}
          onGoApproval={() => safeSetScreen("approval")}
        />
      )}

      {screen === "matchingJobs" && selectedCandidate && (
        <MatchingJobs
          candidate={selectedCandidate}
          jobs={jobs}
          onApply={async (jobId) => {
            try {
              if (!selectedCandidate.phone) {
                throw new Error("Candidate phone is missing. Add phone number before applying.");
              }
              const res = await applyForJob({
                jobId,
                fullName: selectedCandidate.name,
                email: selectedCandidate.email,
                phone: selectedCandidate.phone
              });

              setSelectedJobId(jobId);
              setCandidates((prev) =>
                prev.map((c) =>
                  c.id === selectedCandidate.id ? { ...c, status: "Applied" } : c
                )
              );
              notify("Applied", res?.message || "Candidate applied successfully.");
            } catch (err) {
              notify("Applied", err.message || "Failed to apply for the job.");
            }
          }}
        />
      )}

      {screen === "interviewSchedule" && selectedCandidate && selectedJob && (
        <InterviewSchedule
          candidate={selectedCandidate}
          job={selectedJob}
          candidates={candidates}
          jobs={jobs}
          selectedCandidateId={selectedCandidateId}
          selectedJobId={selectedJobId}
          onChangeCandidate={setSelectedCandidateId}
          onChangeJob={setSelectedJobId}
          onSchedule={(i) => {
            setInterviews((prev) => [i, ...prev]);
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === i.candidateId
                  ? { ...c, status: "Interview Scheduled" }
                  : c
              )
            );
            notify(
              "Interview",
              "Interview scheduled. Candidate + recruiter notified (simulated)."
            );
            safeSetScreen("interviewStatus");
          }}
          onViewStatus={() => safeSetScreen("interviewStatus")}
        />
      )}

      {screen === "interviewStatus" && (
        <InterviewStatus
          interviews={interviews}
          candidates={candidates}
          onMarkCompleted={async (interview) => {
            try {
              await updateInterview({
                interviewId: interview.id,
                status: "Completed"
              });
              await refreshInterviews();
            } catch (err) {
              notify("Interview", err.message || "Failed to update interview.");
            }
          }}
          onRefreshInterviews={refreshInterviews}
          onGoApproval={() => safeSetScreen("approval")}
        />
      )}

      {screen === "approval" && selectedCandidate && (
        <Approval
          candidate={selectedCandidate}
          onApprove={() => {
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id ? { ...c, status: "Selected" } : c
              )
            );
            notify("Approved", "Candidate approved for hire. Proceed to offer.");
            safeSetScreen("offer");
          }}
          onReject={() => {
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id ? { ...c, status: "Rejected" } : c
              )
            );
            notify("Rejected", "Candidate marked as No Hire.");
            safeSetScreen("dashboard");
          }}
        />
      )}

      {screen === "offer" && selectedCandidate && selectedJob && (
        <OfferScreen
          candidate={selectedCandidate}
          job={selectedJob}
          candidates={candidates}
          jobs={jobs}
          selectedCandidateId={selectedCandidateId}
          selectedJobId={selectedJobId}
          onChangeCandidate={setSelectedCandidateId}
          onChangeJob={setSelectedJobId}
          offer={offer}
          setOffer={setOffer}
          users={users}
          existingOffer={offers.find(
            (o) =>
              o.candidate_id === selectedCandidate.id &&
              o.job_id === selectedJob.id &&
              o.offer_status === "Pending"
          )}
          onCreate={async () => {
            setOfferError("");
            setOfferLoading(true);
            try {
              const hiringManagerId =
                offer.hiringManagerId || selectedJob.hiringManager;
              const reportingManagerId =
                offer.reportingManagerId || offer.hiringManagerId || selectedJob.hiringManager;
              if (!hiringManagerId || !reportingManagerId) {
                throw new Error("Please select Hiring Manager and Reporting Manager.");
              }
              await createOfferLetter({
                candidateId: selectedCandidate.id,
                jobId: selectedJob.id,
                hiringManagerId,
                reportingManagerId,
                position: offer.position || selectedJob.title,
                salary: offer.salary || 0,
                joiningDate: offer.startDate || offer.joiningDate
              });
              await refreshOffers();
              setCandidates((prev) =>
                prev.map((c) =>
                  c.id === selectedCandidate.id ? { ...c, status: "Offer Sent" } : c
                )
              );
              notify("Offer", "Offer letter created and sent.");
            } catch (err) {
              setOfferError(err.message || "Failed to create offer.");
            } finally {
              setOfferLoading(false);
            }
          }}
          onUpdate={async () => {
            const existing = offers.find(
              (o) =>
                o.candidate_id === selectedCandidate.id &&
                o.job_id === selectedJob.id &&
                o.offer_status === "Pending"
            );
            if (!existing) return;
            setOfferError("");
            setOfferLoading(true);
            try {
              await updateOfferLetter(existing.id, {
                position: offer.position || selectedJob.title,
                salary: String(offer.salary ?? 0),
                joiningDate: offer.startDate || offer.joiningDate
              });
              await refreshOffers();
              notify("Offer", "Offer updated.");
            } catch (err) {
              setOfferError(err.message || "Failed to update offer.");
            } finally {
              setOfferLoading(false);
            }
          }}
          onReloadDetails={async () => {
            const existing = offers.find(
              (o) =>
                o.candidate_id === selectedCandidate.id &&
                o.job_id === selectedJob.id &&
                o.offer_status === "Pending"
            );
            if (!existing) return;
            setOfferError("");
            setOfferLoading(true);
            try {
              const fresh = await getOfferById(existing.id);
              setOffers((prev) =>
                (prev || []).map((o) => (o.id === fresh.id ? fresh : o))
              );
              notify("Offer", "Offer details reloaded from server.");
            } catch (err) {
              setOfferError(err.message || "Failed to reload offer.");
            } finally {
              setOfferLoading(false);
            }
          }}
          onCancel={async () => {
            const existing = offers.find(
              (o) =>
                o.candidate_id === selectedCandidate.id &&
                o.job_id === selectedJob.id &&
                o.offer_status === "Pending"
            );
            if (!existing) return;
            if (!window.confirm("Cancel this offer?")) return;
            setOfferError("");
            setOfferLoading(true);
            try {
              await cancelOfferLetter(existing.id);
              await refreshOffers();
              setCandidates((prev) =>
                prev.map((c) =>
                  c.id === selectedCandidate.id
                    ? { ...c, status: "Offer Cancelled" }
                    : c
                )
              );
              notify("Offer", "Offer cancelled.");
              safeSetScreen("dashboard");
            } catch (err) {
              setOfferError(err.message || "Failed to cancel offer.");
            } finally {
              setOfferLoading(false);
            }
          }}
          onAccept={() => {
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id
                  ? { ...c, status: "Offer Accepted" }
                  : c
              )
            );
            safeSetScreen("documents");
          }}
          onDecline={() => {
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id
                  ? { ...c, status: "Offer Declined" }
                  : c
              )
            );
            notify("Offer", "Offer declined. Workflow ended (No Hire).");
            safeSetScreen("dashboard");
          }}
          loading={offerLoading}
          error={offerError}
        />
      )}

      {screen === "documents" && selectedCandidate && (
        <Documents
          candidate={selectedCandidate}
          candidates={candidates}
          selectedCandidateId={selectedCandidateId}
          onChangeCandidate={setSelectedCandidateId}
          onSubmit={() => {
            notify("Documents", "Documents uploaded. Sent for verification.");
            safeSetScreen("verification");
          }}
        />
      )}

      {screen === "verification" && selectedCandidate && (
        <Verification
          candidate={selectedCandidate}
          candidates={candidates}
          selectedCandidateId={selectedCandidateId}
          onChangeCandidate={setSelectedCandidateId}
          onApprove={() => {
            notify("Verification", "Documents verified. Pre-onboarding started.");
            safeSetScreen("preOnboarding");
          }}
          onReject={() => {
            notify("Verification", "Documents marked Pending/Rejected.");
          }}
        />
      )}

      {screen === "preOnboarding" && selectedCandidate && (
        <PreOnboarding
          candidate={selectedCandidate}
          candidates={candidates}
          selectedCandidateId={selectedCandidateId}
          onChangeCandidate={setSelectedCandidateId}
          onFinish={() => {
            notify("Hire", "Hire completed. Workflow ended.");
            safeSetScreen("dashboard");
          }}
        />
      )}

      {screen === "newsletters" && <NewsletterScreen />}
      {screen === "rbac" && <RbacSettingsScreen />}
    </Shell>
  );
}
