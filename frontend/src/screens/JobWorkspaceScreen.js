import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, StatusBadge } from "../components/ui";
import { candidateAppendedJob, getJobHistory } from "../services/api/jobs";
import CandidateAssignJobModal from "./CandidateAssignJobModal";
import { getCandidateById } from "../services/api/candidates";
import { AlertCircle, CheckCircle, X } from "lucide-react";
import { Link } from "react-router-dom";
import JobDetails from "./JobDetails";
import JobHistory from "../components/JobHistory";

const TABS = ["Job Details", "Candidates", "Job Analytics", "History"];

const getStageLabel = (candidate) => {
  const status = String(candidate?.pipelineStatus || candidate?.status || "")
    .trim()
    .toLowerCase();
  if (status.includes("screen")) return "Recruiter Screening";
  if (status.includes("l1") || status.includes("interview"))
    return "L1 Interview";
  if (status.includes("pre")) return "Pre-Onboarding";
  if (status.includes("hire") || status.includes("onboard")) return "Hired";
  if (status.includes("archive") || status.includes("reject"))
    return "Archived";
  return "Sourced";
};

const STAGES = [
  "Sourced",
  "Recruiter Screening",
  "L1 Interview",
  "Pre-Onboarding",
  "Hired",
  "Archived",
];

// The job's figures come from its own records (GET /jobs/{id}/history); "—" until there is something to measure
const jobFigures = (summary) => [
  ["Upcoming Interviews", summary?.upcoming_interviews ?? "—"],
  ["Days to First Accepted Offer", summary?.days_to_first_accepted_offer ?? "—"],
  ["Offer Acceptance Rate", summary?.offer_acceptance_pct != null ? `${summary.offer_acceptance_pct}%` : "—"],
  ["Filled / Total Positions", summary ? `${summary.positions_filled} / ${summary.positions}` : "—"],
];

export default function JobWorkspaceScreen({
  job,
  candidates = [],
  onAddCandidate,
  onOpenCandidate,
  onFetchCandidateById,
  setSelectedCandidate,
  setScreen,
  setSelectedCandidateId,
  setCandidateDetailsDefaultTab,
  setAutoOpenSchedule,
  onUpdateJob,
}) {
  const [activeTab, setActiveTab] = useState("Candidates");
  const [finalCandidates, setFinalCandidates] = useState([]);
  const [showSubmitJobModal, setShowSubmitJobModal] = useState(false);
  const [selectedJobForSubmission, setSelectedJobForSubmission] =
    useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const jobId = job?.id;

  const fetchCandidateJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const result = await candidateAppendedJob(jobId);
      const applications = result?.applications || [];
      let failedLookups = 0;

      const enrichedCandidates = await Promise.all(
        applications.map(async (app) => {
          try {
            const candidateDetails = await getCandidateById(app?.candidate_id);

            return {
              ...app,
              candidate: candidateDetails,
            };
          } catch (err) {
            // Keep the application row (it exists on the job) but flag the
            // missing profile instead of silently dropping the failure.
            failedLookups += 1;
            console.error(
              `[JobWorkspaceScreen] Failed to load candidate ${app?.candidate_id}:`,
              err,
            );
            return {
              ...app,
              candidate: null,
            };
          }
        }),
      );

      setFinalCandidates(enrichedCandidates);
      if (failedLookups > 0) {
        setActionError(
          `Could not load details for ${failedLookups} candidate(s) on this job.`,
        );
      }
    } catch (err) {
      console.error("[JobWorkspaceScreen] Failed to load job candidates:", err);
      setActionError(
        `Failed to load candidates for this job: ${err?.message || "Unknown error"}`,
      );
    }
  }, [jobId]);

  useEffect(() => {
    fetchCandidateJob();
  }, [fetchCandidateJob]);

  const normalizedTitle = String(job?.title || "")
    .trim()
    .toLowerCase();

  const formatDate = (date) => {
    if (!date) return "—";
    return new Date(date).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  const normalizedCandidates = useMemo(() => {
    return finalCandidates.map((c) => ({
      id: c.candidate_id,
      job_id: c.job_id,
      name: `${c?.candidate?.candidate_name || ""} ${c.candidate_last_name || ""}`.trim(),
      email: c?.candidate?.candidate_email,
      phone: c?.candidate?.candidate_mobile,
      experience: c.candidate_experience,
      location: c.candidate_current_location,
      source: "API",
      status: c.application_status || c?.candidate?.pipline_status || "Sourced",
      pipelineStatus: c?.candidate?.pipline_status || c.application_status || "Sourced",
      createdAt: formatDate(c.applied_at),
    }));
  }, [finalCandidates]);

  const jobCandidates = useMemo(() => {
    if (!normalizedTitle) return normalizedCandidates;
    const matched = normalizedCandidates.filter((c) =>
      String(c?.jobTitle || "")
        .toLowerCase()
        .includes(normalizedTitle),
    );
    return matched.length ? matched : normalizedCandidates;
  }, [normalizedCandidates, normalizedTitle]);

  const stageCounts = useMemo(() => {
    const counts = Object.fromEntries(STAGES.map((s) => [s, 0]));
    jobCandidates.forEach((c) => {
      const stage = getStageLabel(c);
      counts[stage] = (counts[stage] || 0) + 1;
    });
    return counts;
  }, [jobCandidates]);

  const jobAnalyticsPipeline = useMemo(
    () => STAGES.map((label) => ({ label, count: stageCounts[label] || 0 })),
    [stageCounts],
  );
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    if (!jobId || activeTab !== "Job Analytics") return;
    getJobHistory(jobId)
      .then((res) => setSummary(res?.summary || null))
      .catch((err) => setActionError(`Could not load this job's figures: ${err.message}`));
  }, [jobId, activeTab]);

  return (
    <div className="space-y-4">
      {/* Action Error Banner */}
      {actionError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-700 text-sm font-medium">{actionError}</p>
            </div>
            <button
              onClick={() => setActionError(null)}
              className="text-red-600 hover:text-red-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Action Success Banner */}
      {actionSuccess && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-green-700 text-sm font-medium">{actionSuccess}</p>
            </div>
            <button
              onClick={() => setActionSuccess(null)}
              className="text-green-600 hover:text-green-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xl font-bold text-slate-900">
              {job?.title || "Job Workspace"}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {job?.location || "—"} - {job?.experienceLevel || "—"} years
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-slate-600">
              {job?.clientDisplayName ? <span>Client: <Link className="font-semibold underline" to="/client-management">{job.clientDisplayName}</Link></span> : null}
              {job?.opportunityId ? <span>Opportunity: <Link className="font-semibold underline" to="/opportunity-pipeline">{(job.opportunityStage || "linked").toLowerCase()}</Link></span> : null}
              {job?.hiringManagerName ? <span>Hiring manager: <span className="font-semibold">{job.hiringManagerName}</span></span> : null}
              {job?.confirmationStatus === "POTENTIAL" ? <span className="font-semibold text-amber-700">Potential: not sold yet</span> : null}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {/* Role Type Indicator */}
              {job?.is_internal_role === true && (
                <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-800">
                  Internal Role
                </span>
              )}
              {job?.is_internal_role === false && (
                <span className="inline-flex items-center rounded-full bg-purple-100 px-2 py-1 text-xs font-semibold text-purple-800">
                  External Role
                </span>
              )}

              {/* Days Remaining Indicator */}
              {job?.end_date && (() => {
                const endDate = new Date(job.end_date);
                const today = new Date();
                const daysRemaining = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));
                const isUrgent = daysRemaining <= 7;
                const isPast = daysRemaining < 0;

                return (
                  <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold ${
                    isPast
                      ? 'bg-red-100 text-red-800'
                      : isUrgent
                      ? 'bg-orange-100 text-orange-800'
                      : 'bg-green-100 text-green-800'
                  }`}>
                    {isPast ? `${Math.abs(daysRemaining)} days overdue` : `${daysRemaining} days remaining`}
                  </span>
                );
              })()}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={job?.status || "Open"} />
            <Button onClick={onAddCandidate}>+ Add Candidate</Button>
            <Button
              onClick={() => {
                setSelectedJobForSubmission(job);
                setShowSubmitJobModal(true);
              }}
            >
              + Submit Candidate
            </Button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border bg-white px-2 py-2 shadow-sm">
        <div className="flex min-w-max items-center gap-1">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`rounded-lg px-3 py-2 text-xs font-semibold ${
                activeTab === tab
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "Job Details" ? (
        <JobDetails job={job} candidates={candidates} mode="edit" defaultTab="details" onUpdate={onUpdateJob} />
      ) : activeTab === "Candidates" ? (
        <JobDetails job={job} candidates={jobCandidates} mode="edit" defaultTab="candidates" onUpdate={onUpdateJob} />
      ) : activeTab === "History" ? (
        <JobHistory jobId={job?.id} />
      ) : activeTab === "Job Analytics" ? (
        <>
          <div className="grid gap-2 rounded-2xl border bg-white p-3 shadow-sm md:grid-cols-4">
            {jobFigures(summary).map(([label, value]) => (
              <div key={label} className="rounded-xl border bg-slate-50 px-3 py-2 text-left">
                <div className="text-xs">{label}</div>
                <div className="text-lg font-bold">{value}</div>
              </div>
            ))}
          </div>

          <div className="rounded-2xl border bg-white p-6 text-sm text-slate-600 shadow-sm">
            <div className="flex justify-between item-center">
              <span className="font-bold">Candidate Pipeline</span>
            </div>
            <div className="flex item-center justify-between gap-100 pt-4">
              {jobAnalyticsPipeline.map((item, index) => (
                <div
                  key={index}
                  className={`flex flex-col items-center justify-center ${
                    index !== 0 ? "pt-15" : ""
                  }`}
                >
                  <div>{item.count}</div>
                  <div>{item.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="w-full rounded-xl border bg-gray-50 p-6 text-sm text-gray-700 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold">Pending review</span>
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-600">
                  New
                </span>
                <span className="text-gray-400 cursor-pointer">ⓘ</span>
              </div>
              <div className="flex items-center gap-1 text-blue-500 text-sm cursor-pointer"></div>
            </div>

            <div className="mt-4">
              <span className="text-3xl font-semibold text-blue-600">
                {(stageCounts.Sourced || 0) + (stageCounts["Recruiter Screening"] || 0) + (stageCounts["L1 Interview"] || 0)}
              </span>
            </div>
            <div className="mt-6 flex items-center gap-6 text-sm text-gray-600">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-purple-400"></span>
                <span>Sourced ({stageCounts.Sourced || 0})</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-teal-400"></span>
                <span>Screening ({stageCounts["Recruiter Screening"] || 0})</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-yellow-400"></span>
                <span>Interview ({stageCounts["L1 Interview"] || 0})</span>
              </div>
            </div>
          </div>

        </>
      ) : (
        <div className="rounded-2xl border bg-white p-6 text-sm text-slate-600 shadow-sm">
          {activeTab} section will be wired next.
        </div>
      )}

      {showSubmitJobModal && selectedJobForSubmission && (
        <CandidateAssignJobModal
          selectedJob={selectedJobForSubmission}
          allCandidates={candidates}
          onAssignSuccess={fetchCandidateJob}
          onClose={() => {
            setShowSubmitJobModal(false);
            setSelectedJobForSubmission(null);
          }}
        />
      )}
    </div>
  );
}
