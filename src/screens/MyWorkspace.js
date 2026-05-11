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
import { getMyInterviews } from "../services/api/interviews";

const normalizeInterviewList = (res) => {
  if (Array.isArray(res)) return res;
  if (Array.isArray(res?.interviews)) return res.interviews;
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

const buildCandidateForDetails = (workspaceItem) => ({
  id: workspaceItem?.candidateId || "",
  name: workspaceItem?.candidateName || "Candidate",
  email: workspaceItem?.candidateEmail || "",
  phone: workspaceItem?.candidateMobile || "",
  jobTitle: workspaceItem?.roundName || "",
  limitedInterview: {
    interview_id: workspaceItem?.interviewId || "",
    panel_id: workspaceItem?.panelId || "",
    round_name: workspaceItem?.roundName || "",
    candidate_id: workspaceItem?.candidateId || "",
    candidate_name: workspaceItem?.candidateName || "Candidate",
    candidate_email: workspaceItem?.candidateEmail || "",
    candidate_mobile: workspaceItem?.candidateMobile || "",
    start_time: workspaceItem?.startTime || "",
    end_time: workspaceItem?.endTime || "",
    meeting_link: workspaceItem?.meetingLink || "",
    status: workspaceItem?.interviewStatus || "",
    feedback_submitted: Boolean(workspaceItem?.feedbackSubmitted),
    my_feedback: workspaceItem?.myFeedback || null,
    interviewer_id: workspaceItem?.interviewerId || "",
    interviewer_name: workspaceItem?.interviewerName || "",
  },
});

const getStatusStyles = (status) => {
  const normalized = String(status || "")
    .trim()
    .toLowerCase();

  if (normalized.includes("complete")) {
    return "border-green-200 bg-green-50 text-green-700";
  }

  if (normalized.includes("cancel")) {
    return "border-red-200 bg-red-50 text-red-700";
  }

  if (normalized.includes("schedule")) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }

  if (normalized.includes("submitted")) {
    return "border-green-200 bg-green-50 text-green-700";
  }

  if (normalized.includes("pending")) {
    return "border-orange-200 bg-orange-50 text-orange-700";
  }

  return "border-gray-200 bg-gray-50 text-gray-700";
};

const getFeedbackStatus = (item) => {
  if (item?.feedbackSubmitted) return "Feedback Submitted";
  return "Feedback Pending";
};

export default function MyWorkspace({ onLogout }) {
  const [myInterviews, setMyInterviews] = useState([]);
  const [workspaceSummary, setWorkspaceSummary] = useState({
    interviewerName: "",
    totalInterviews: 0,
    pendingFeedback: 0,
  });
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadWorkspaceData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await getMyInterviews();
      const interviews = normalizeInterviewList(response);

      setMyInterviews(
        interviews.map((interview) => ({
          ...interview,
          interviewer_id: response?.interviewer_id || "",
          interviewer_name: response?.interviewer_name || "",
        })),
      );
      const pendingFeedbackCount = interviews.filter(
        (item) => !item?.feedback_submitted,
      ).length;

      setWorkspaceSummary({
        interviewerName: response?.interviewer_name || "",
        totalInterviews: Number(
          response?.total_interviews ?? interviews.length,
        ),
        pendingFeedback: pendingFeedbackCount,
      });
    } catch (err) {
      console.error("Failed to load workspace data", err);
      setError(
        err?.message || "Unable to load your interviews. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkspaceData();
  }, [loadWorkspaceData]);

  const workspaceItems = useMemo(() => {
    return myInterviews.map((interview) => ({
      key: `interview-${interview?.interview_id || interview?.id}`,
      candidateId: interview?.candidate_id || "",
      candidateName: interview?.candidate_name || "Candidate",
      candidateEmail: interview?.candidate_email || "",
      candidateMobile: interview?.candidate_mobile || "",
      interviewId: interview?.interview_id || interview?.id || "",
      interviewerId: interview?.interviewer_id || "",
      interviewerName: interview?.interviewer_name || "",
      panelId: interview?.panel_id || "",
      roundName: interview?.round_name || "-",
      startTime: interview?.start_time || "",
      endTime: interview?.end_time || "",
      meetingLink: interview?.meeting_link || "",
      interviewStatus: interview?.status || "Scheduled",
      feedbackSubmitted: Boolean(interview?.feedback_submitted),
      myFeedback: interview?.my_feedback || null,
    }));
  }, [myInterviews]);

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
                View your assigned interviews and submit interview feedback.
              </p>

              {workspaceSummary.interviewerName ? (
                <p className="mt-2 text-sm font-medium text-gray-700">
                  Welcome, {workspaceSummary.interviewerName}
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-2">
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
            label="Assigned Interviews"
            value={workspaceSummary.totalInterviews}
          />

          <SummaryCard
            icon={Calendar}
            label="Pending Feedback"
            value={workspaceSummary.pendingFeedback}
          />

          <SummaryCard
            icon={UserCheck}
            label="Submitted Feedback"
            value={
              workspaceItems.filter((item) => item.feedbackSubmitted).length
            }
          />
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-5 py-4">
            <h2 className="text-base font-semibold text-gray-900">
              My Interviews
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Only interviews assigned to you are shown here.
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
                      <th className="px-5 py-3 font-semibold">Round</th>
                      <th className="px-5 py-3 font-semibold">
                        Interview Time
                      </th>
                      <th className="px-5 py-3 font-semibold">Interview</th>
                      <th className="px-5 py-3 font-semibold">Feedback</th>
                      <th className="px-5 py-3 text-right font-semibold">
                        Action
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-gray-100">
                    {workspaceItems?.map((item) => (
                      <tr
                        key={String(item?.key)}
                        className="hover:bg-gray-50/70"
                      >
                        <td className="px-5 py-4">
                          <div className="font-semibold text-gray-900">
                            {item?.candidateName}
                          </div>
                        </td>

                        <td className="px-5 py-4 text-gray-700">
                          {item?.roundName || "-"}
                        </td>

                        <td className="px-5 py-4 text-gray-600">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-gray-400" />
                            {formatDateTime(item?.startTime)}
                          </div>
                        </td>

                        <td className="px-5 py-4">
                          <StatusBadge status={item?.interviewStatus} />
                        </td>

                        <td className="px-5 py-4">
                          <StatusBadge status={getFeedbackStatus(item)} />
                        </td>

                        <td className="px-5 py-4 text-right">
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedCandidate(
                                buildCandidateForDetails(item),
                              )
                            }
                            className="rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-800"
                          >
                            {item?.feedbackSubmitted
                              ? "View Feedback"
                              : "Open Feedback"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-3 p-4 md:hidden">
                {workspaceItems?.map((item) => (
                  <div
                    key={String(item?.key)}
                    className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-gray-900">
                          {item?.candidateName}
                        </h3>
                      </div>

                      <StatusBadge status={getFeedbackStatus(item)} />
                    </div>

                    <div className="mt-4 space-y-2 text-sm text-gray-600">
                      <InfoRow
                        label="Email"
                        value={item?.candidateEmail || "-"}
                      />

                      <InfoRow label="Round" value={item?.roundName || "-"} />

                      <InfoRow
                        label="Interview"
                        value={item?.interviewStatus || "-"}
                      />

                      <InfoRow
                        label="Time"
                        value={formatDateTime(item?.startTime)}
                      />
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        setSelectedCandidate(buildCandidateForDetails(item))
                      }
                      className="mt-4 w-full rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-gray-800"
                    >
                      {item?.feedbackSubmitted
                        ? "View Feedback"
                        : "Open Feedback"}
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
        No assigned interviews
      </h3>

      <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
        You don’t have any assigned interviews at the moment. When you are added
        as a panel member, your interviews will appear here.
      </p>
    </div>
  );
}
