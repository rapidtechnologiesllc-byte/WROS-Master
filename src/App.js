// App entry: auth guard, role routing, and screen orchestration.
import { useCallback, useEffect, useMemo, useState } from "react";
import AuthPage from "./pages/AuthPage";
import Shell from "./layout/Shell";
import Approval from "./screens/Approval";
import CandidateCreate from "./screens/CandidateCreate";
import CandidateSearch from "./screens/CandidateSearch";
import CandidateSelfService from "./screens/CandidateSelfService";
import Dashboard from "./screens/Dashboard";
import Documents from "./screens/Documents";
import InterviewSchedule from "./screens/InterviewSchedule";
import InterviewStatus from "./screens/InterviewStatus";
import JobCreate from "./screens/JobCreate";
import JobDetails from "./screens/JobDetails";
import JobsOverview from "./screens/JobsOverview";
import MatchingJobs from "./screens/MatchingJobs";
import OfferScreen from "./screens/OfferScreen";
import PreOnboarding from "./screens/PreOnboarding";
import Verification from "./screens/Verification";
import { getAllInterviews, updateInterview } from "./services/api/interviews";
import { getAllCandidates } from "./services/api/candidates";
import { deleteJob, getAllJobs, updateJob } from "./services/api/jobs";

export default function App() {
  const token = localStorage.getItem("hrms_token");
  // Auth guard: unauthenticated users or auth routes land on AuthPage.
  if (!token || window.location.pathname.startsWith("/auth")) {
    return <AuthPage />;
  }

  const storedRole = localStorage.getItem("hrms_role");
  const normalizedRole = storedRole ? storedRole.toUpperCase() : "RECRUITER";

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
    id: "O-4001",
    candidateId: "C-1001",
    jobId: "J-2001",
    salary: 120000,
    startDate: "2026-02-15",
    state: "Draft"
  });

  const [selectedCandidateId, setSelectedCandidateId] = useState(
    candidates[0]?.id || ""
  );
  const [selectedJobId, setSelectedJobId] = useState(jobs[0]?.id || "");

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
    const mappedJobs = (refreshed?.jobs || []).map((j) => ({
      id: j.job_id,
      title: j.job_title,
      dept: "",
      location: j.job_location || "",
      skills: String(j.job_skills || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      hiringManager: j.hiring_manager_id || "",
      status: j.job_status || "Draft",
      experienceLevel: j.job_experience || "",
      companyType: j.company_type || "",
      companyClient: j.company_name || "",
      contactPerson: j.contact_person || "",
      startDate: j.start_date || "",
      endDate: j.end_date || "",
      jobDescription: j.job_description || ""
    }));
    setJobs(mappedJobs);
    if (!selectedJobId && mappedJobs.length) {
      setSelectedJobId(mappedJobs[0].id);
    }
  }, [selectedJobId]);

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

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      try {
        const [candidateRes, jobRes, interviewRes] = await Promise.all([
          getAllCandidates(),
          getAllJobs(),
          getAllInterviews()
        ]);

        if (!isMounted) return;

        const mappedCandidates = (candidateRes?.candidates || []).map((c) => ({
          id: c.candidate_id,
          name: c.candidate_name,
          email: c.candidate_email,
          phone: c.candidate_mobile || "",
          skills: [],
          status: c.candidate_is_verified ? "Verified" : "New"
        }));

        const mappedJobs = (jobRes?.jobs || []).map((j) => ({
          id: j.job_id,
          title: j.job_title,
          dept: "",
          location: j.job_location || "",
          skills: String(j.job_skills || "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          hiringManager: j.hiring_manager_id || "",
          status: j.job_status || "Draft",
          experienceLevel: j.job_experience || "",
          companyType: j.company_type || "",
          companyClient: j.company_name || "",
          contactPerson: j.contact_person || "",
          startDate: j.start_date || "",
          endDate: j.end_date || "",
          jobDescription: j.job_description || ""
        }));

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
    if (hmOnly.includes(next) && role !== "Hiring Manager") {
      notify("Access", "Switch role to Hiring Manager to open this screen.");
      return;
    }
    setScreen(next);
  };

  return (
    <Shell
      role={role}
      setRole={setRole}
      screen={screen}
      setScreen={safeSetScreen}
      onLogout={handleLogout}
    >
      {screen === "dashboard" && (
        <Dashboard
          candidates={candidates}
          jobs={jobs}
          interviews={interviews}
          offer={offer}
          onGo={(s) => safeSetScreen(s)}
        />
      )}

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
          onCreate={() => safeSetScreen("jobCreate")}
          onOpenJob={(jobId) => {
            setSelectedJobId(jobId);
            safeSetScreen("jobDetails");
          }}
          onDeleteJob={async (jobId) => {
            const ok = window.confirm(`Delete job ${jobId}?`);
            if (!ok) return;
            try {
              await deleteJob(jobId);
              await refreshJobs();
              notify("Job", `Deleted job ${jobId}.`);
            } catch (err) {
              notify("Job", err.message || "Failed to delete job.");
            }
          }}
        />
      )}

      {screen === "jobCreate" && (
        <JobCreate
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
                job_status: next.jobStatus || next.status,
                no_of_positions: next.noOfPositions,
                start_date: next.startDate,
                end_date: next.endDate
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
          onApply={(jobId) => {
            setSelectedJobId(jobId);
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id ? { ...c, status: "Applied" } : c
              )
            );
            notify("Applied", "Candidate applied with single click Apply (simulated).");
          }}
        />
      )}

      {screen === "interviewSchedule" && selectedCandidate && selectedJob && (
        <InterviewSchedule
          candidate={selectedCandidate}
          job={selectedJob}
          onSchedule={(i) => {
            setInterviews((prev) => [i, ...prev]);
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id
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
          offer={offer}
          setOffer={setOffer}
          onSend={() => {
            setOffer((o) => ({ ...o, state: "Sent" }));
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id ? { ...c, status: "Offer Sent" } : c
              )
            );
            notify("Offer", "Offer letter initiated and sent (simulated).");
          }}
          onNegotiate={() => setOffer((o) => ({ ...o, state: "Negotiation" }))}
          onAccept={() => {
            setOffer((o) => ({ ...o, state: "Accepted" }));
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
            setOffer((o) => ({ ...o, state: "Declined" }));
            setCandidates((prev) =>
              prev.map((c) =>
                c.id === selectedCandidate.id ? { ...c, status: "Offer Declined" } : c
              )
            );
            notify("Offer", "Offer declined. Workflow ended (No Hire).");
            safeSetScreen("dashboard");
          }}
        />
      )}

      {screen === "documents" && selectedCandidate && (
        <Documents
          candidate={selectedCandidate}
          onSubmit={() => {
            notify("Documents", "Documents uploaded. Sent for verification.");
            safeSetScreen("verification");
          }}
        />
      )}

      {screen === "verification" && (
        <Verification
          onApprove={() => {
            notify("Verification", "Documents verified. Pre-onboarding started.");
            safeSetScreen("preOnboarding");
          }}
          onReject={() => {
            notify("Verification", "Documents marked Pending/Rejected.");
          }}
        />
      )}

      {screen === "preOnboarding" && (
        <PreOnboarding
          onFinish={() => {
            notify("Hire", "Hire completed. Workflow ended.");
            safeSetScreen("dashboard");
          }}
        />
      )}
    </Shell>
  );
}
