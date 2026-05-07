import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Calendar,
  Clock,
  LogOut,
  RefreshCw,
  UserCheck,
  Users,
} from "lucide-react";
import CandidateDetailsScreen from "./CandidateDetailsScreen";
import { getAssignedCandidates } from "../services/api/candidates";
import { getAssignedInterviews } from "../services/api/interviews";

const normalizeList = (res, keys = []) => {
  if (Array.isArray(res)) return res;

  for (const key of keys) {
    if (Array.isArray(res?.[key])) return res[key];
  }

  if (Array.isArray(res?.data)) return res.data;
  if (Array.isArray(res?.items)) return res.items;

  return [];
};

const formatDateTime = (value) => {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getCandidateId = (item) =>
  item?.candidate_id || item?.candidateId || item?.id || "";

const buildCandidateForDetails = (workspaceItem) => ({
  id: workspaceItem.candidateId,
  name: workspaceItem.candidateName,
  email: workspaceItem.candidateEmail,
  phone: workspaceItem.candidateMobile,
  jobTitle: workspaceItem.assignmentType || workspaceItem.roundName || "",
});

const getStatusStyles = (status) => {
  const normalized = String(status || "").trim().toLowerCase();

  if (normalized.includes("complete")) {
    return "border-green-200 bg-green-50 text-green-700";
  }

  if (normalized.includes("cancel")) {
    return "border-red-200 bg-red-50 text-red-700";
  }

  if (normalized.includes("schedule")) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }

  return "border-gray-200 bg-gray-50 text-gray-700";
};

export default function MyWorkspace({ onLogout }) {
  const [assignedCandidates, setAssignedCandidates] = useState([]);
  const [assignedInterviews, setAssignedInterviews] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadWorkspaceData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [candidateRes, interviewRes] = await Promise.all([
        getAssignedCandidates(),
        getAssignedInterviews(),
      ]);

      setAssignedCandidates(
        normalizeList(candidateRes, ["candidates", "assignments"]),
      );

      setAssignedInterviews(
        normalizeList(interviewRes, ["interviews", "assigned_interviews"]),
      );
    } catch (err) {
      console.error("Failed to load workspace data", err);
      setError(
        err?.message ||
          "Unable to load your assignments. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkspaceData();
  }, [loadWorkspaceData]);

  const workspaceItems = useMemo(() => {
    const candidateById = new Map();

    assignedCandidates.forEach((candidate) => {
      const candidateId = getCandidateId(candidate);
      if (!candidateId) return;

      candidateById.set(String(candidateId), candidate);
    });

    const interviewItems = assignedInterviews.map((interview) => {
      const candidateId = getCandidateId(interview);
      const candidate = candidateById.get(String(candidateId)) || {};

      return {
        key: `interview-${interview?.interview_id || interview?.id || candidateId}`,
        candidateId,
        candidateName:
          interview?.candidate_name ||
          candidate?.candidate_name ||
          "Candidate",
        candidateEmail: candidate?.candidate_email || "",
        candidateMobile: candidate?.candidate_mobile || "",
        assignmentType: candidate?.assignment_type || "",
        assignedAt: candidate?.assigned_at || "",
        interviewId: interview?.interview_id || interview?.id || "",
        panelId: interview?.panel_id || "",
        roundName: interview?.round_name || interview?.panel_round_name || "-",
        startTime: interview?.start_time || "",
        endTime: interview?.end_time || "",
        meetingLink: interview?.meeting_link || "",
        status: interview?.status || "Scheduled",
        hasInterview: true,
      };
    });

    const interviewCandidateIds = new Set(
      interviewItems.map((item) => String(item.candidateId)),
    );

    const candidateOnlyItems = assignedCandidates
      .filter((candidate) => {
        const candidateId = getCandidateId(candidate);
        return candidateId && !interviewCandidateIds.has(String(candidateId));
      })
      .map((candidate) => {
        const candidateId = getCandidateId(candidate);

        return {
          key: `candidate-${candidateId}`,
          candidateId,
          candidateName: candidate?.candidate_name || "Candidate",
          candidateEmail: candidate?.candidate_email || "",
          candidateMobile: candidate?.candidate_mobile || "",
          assignmentType: candidate?.assignment_type || "",
          assignedAt: candidate?.assigned_at || "",
          interviewId: "",
          panelId: "",
          roundName: "-",
          startTime: "",
          endTime: "",
          meetingLink: "",
          status: "No interview assigned",
          hasInterview: false,
        };
      });

    return [...interviewItems, ...candidateOnlyItems];
  }, [assignedCandidates, assignedInterviews]);

  if (selectedCandidate) {
    return (
      <div className="min-h-screen bg-gray-50 px-4 py-6 text-gray-900">
        <div className="mx-auto max-w-7xl">
          <CandidateDetailsScreen
            candidate={selectedCandidate}
            limitedMode
            onBack={() => setSelectedCandidate(null)}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-6 text-gray-900">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                HRMS
              </div>
              <h1 className="mt-1 text-xl font-bold text-gray-900">
                My Workspace
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                View your assigned candidates and submit interview feedback.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={loadWorkspaceData}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 disabled:opacity-60"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>

              {onLogout && (
                <button
                  type="button"
                  onClick={onLogout}
                  className="inline-flex items-center gap-2 rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-800"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </button>
              )}
            </div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          <SummaryCard
            icon={Users}
            label="Assigned Candidates"
            value={assignedCandidates.length}
          />
          <SummaryCard
            icon={Calendar}
            label="Assigned Interviews"
            value={assignedInterviews.length}
          />
          <SummaryCard
            icon={UserCheck}
            label="Pending Actions"
            value={workspaceItems.filter((item) => item.hasInterview).length}
          />
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-5 py-4">
            <h2 className="text-base font-semibold text-gray-900">
              My Candidates
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Only candidates and interviews assigned to you are shown here.
            </p>
          </div>

          {loading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={loadWorkspaceData} />
          ) : workspaceItems.length === 0 ? (
            <EmptyState />
          ) : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Candidate</th>
                      <th className="px-5 py-3 font-semibold">Contact</th>
                      <th className="px-5 py-3 font-semibold">Round</th>
                      <th className="px-5 py-3 font-semibold">Interview Time</th>
                      <th className="px-5 py-3 font-semibold">Status</th>
                      <th className="px-5 py-3 text-right font-semibold">
                        Action
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-gray-100">
                    {workspaceItems.map((item) => (
                      <tr key={item.key} className="hover:bg-gray-50/70">
                        <td className="px-5 py-4">
                          <div className="font-semibold text-gray-900">
                            {item.candidateName}
                          </div>
                          <div className="mt-1 text-xs text-gray-500">
                            {item.candidateId}
                          </div>
                        </td>

                        <td className="px-5 py-4 text-gray-600">
                          <div>{item.candidateEmail || "-"}</div>
                          <div className="mt-1 text-xs">
                            {item.candidateMobile || "-"}
                          </div>
                        </td>

                        <td className="px-5 py-4 text-gray-700">
                          {item.roundName}
                        </td>

                        <td className="px-5 py-4 text-gray-600">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-gray-400" />
                            {formatDateTime(item.startTime)}
                          </div>
                        </td>

                        <td className="px-5 py-4">
                          <StatusBadge status={item.status} />
                        </td>

                        <td className="px-5 py-4 text-right">
                          <button
                            type="button"
                            disabled={!item.hasInterview}
                            onClick={() =>
                              setSelectedCandidate(
                                buildCandidateForDetails(item),
                              )
                            }
                            className="rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-300"
                          >
                            {item.hasInterview ? "Open Feedback" : "No Action"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-3 p-4 md:hidden">
                {workspaceItems.map((item) => (
                  <div
                    key={item.key}
                    className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-gray-900">
                          {item.candidateName}
                        </h3>
                        <p className="mt-1 text-xs text-gray-500">
                          {item.candidateId}
                        </p>
                      </div>

                      <StatusBadge status={item.status} />
                    </div>

                    <div className="mt-4 space-y-2 text-sm text-gray-600">
                      <InfoRow label="Email" value={item.candidateEmail || "-"} />
                      <InfoRow label="Phone" value={item.candidateMobile || "-"} />
                      <InfoRow label="Round" value={item.roundName} />
                      <InfoRow
                        label="Time"
                        value={formatDateTime(item.startTime)}
                      />
                    </div>

                    <button
                      type="button"
                      disabled={!item.hasInterview}
                      onClick={() =>
                        setSelectedCandidate(buildCandidateForDetails(item))
                      }
                      className="mt-4 w-full rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-300"
                    >
                      {item.hasInterview ? "Open Feedback" : "No Action"}
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-gray-500">{label}</div>
          <div className="mt-2 text-2xl font-bold text-gray-900">
            {value ?? 0}
          </div>
        </div>

        <div className="rounded-2xl bg-gray-100 p-3">
          <Icon className="h-5 w-5 text-gray-700" />
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${getStatusStyles(
        status,
      )}`}
    >
      {status || "-"}
    </span>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-gray-500">{label}</span>
      <span className="text-right font-medium text-gray-800">{value}</span>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="p-5">
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-16 animate-pulse rounded-2xl bg-gray-100"
          />
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="px-5 py-10 text-center">
      <div className="mx-auto max-w-md rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
        {message}
      </div>

      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-800"
      >
        Try Again
      </button>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="px-5 py-14 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100">
        <UserCheck className="h-6 w-6 text-gray-500" />
      </div>

      <h3 className="mt-4 text-base font-semibold text-gray-900">
        No pending assignments
      </h3>

      <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
        You don’t have any assigned candidates or interviews at the moment.
        When you are added as a panel member, your interviews will appear here.
      </p>
    </div>
  );
}