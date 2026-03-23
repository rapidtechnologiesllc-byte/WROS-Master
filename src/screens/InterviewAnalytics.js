// HR/Admin interview analytics (statistics, candidate history, interviewer workload).
import { useEffect, useMemo, useState } from "react";
import { BarChart3, Calendar, History } from "lucide-react";
import { Button, Card, Select, StatusBadge, Table } from "../components/ui";
import {
  getCandidateInterviewHistory,
  getInterviewerWorkload,
  getInterviewStatistics
} from "../services/api/interviews";

const formatDateTime = (value) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
};

export default function InterviewAnalytics({ candidates, users }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [stats, setStats] = useState(null);

  const [candidateId, setCandidateId] = useState("");
  const [candidateHistory, setCandidateHistory] = useState(null);
  const [historyBusy, setHistoryBusy] = useState(false);

  const [interviewerId, setInterviewerId] = useState("");
  const [workload, setWorkload] = useState(null);
  const [workloadBusy, setWorkloadBusy] = useState(false);

  const candidateOptions = useMemo(() => {
    return ["", ...(candidates || []).map((c) => c.id)];
  }, [candidates]);

  const interviewerOptions = useMemo(() => {
    return ["", ...(users || []).map((u) => u.user_id)];
  }, [users]);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await getInterviewStatistics();
        if (!isMounted) return;
        setStats(res || null);
      } catch (err) {
        if (!isMounted) return;
        setError(err.message || "Failed to load interview statistics.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!candidateId && candidates?.length) setCandidateId(candidates[0].id);
  }, [candidateId, candidates]);

  useEffect(() => {
    if (!interviewerId && users?.length) setInterviewerId(users[0].user_id);
  }, [interviewerId, users]);

  const loadCandidateHistory = async () => {
    if (!candidateId) return;
    setHistoryBusy(true);
    setError("");
    try {
      const res = await getCandidateInterviewHistory(candidateId);
      setCandidateHistory(res || null);
    } catch (err) {
      setError(err.message || "Failed to load candidate history.");
    } finally {
      setHistoryBusy(false);
    }
  };

  const loadWorkload = async () => {
    if (!interviewerId) return;
    setWorkloadBusy(true);
    setError("");
    try {
      const res = await getInterviewerWorkload(interviewerId);
      setWorkload(res || null);
    } catch (err) {
      setError(err.message || "Failed to load interviewer workload.");
    } finally {
      setWorkloadBusy(false);
    }
  };

  if (loading) {
    return (
      <Card title="Interview Analytics" icon={<BarChart3 className="h-4 w-4" />}>
        <div className="py-4 text-center text-sm text-gray-500">Loading…</div>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <Card title="Overall Statistics" icon={<BarChart3 className="h-4 w-4" />}>
        {!stats ? (
          <div className="text-sm text-gray-600">No statistics available.</div>
        ) : (
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-xl border bg-gray-50 p-4">
              <div className="text-xs font-semibold text-gray-600">Total Interviews</div>
              <div className="mt-1 text-2xl font-extrabold tracking-tight">
                {stats.total_interviews}
              </div>
            </div>
            <div className="rounded-xl border bg-gray-50 p-4">
              <div className="text-xs font-semibold text-gray-600">Scheduled</div>
              <div className="mt-1 text-2xl font-extrabold tracking-tight">
                {stats.scheduled}
              </div>
            </div>
            <div className="rounded-xl border bg-gray-50 p-4">
              <div className="text-xs font-semibold text-gray-600">Completed</div>
              <div className="mt-1 text-2xl font-extrabold tracking-tight">
                {stats.completed}
              </div>
            </div>
            <div className="rounded-xl border bg-gray-50 p-4">
              <div className="text-xs font-semibold text-gray-600">Cancelled</div>
              <div className="mt-1 text-2xl font-extrabold tracking-tight">
                {stats.cancelled}
              </div>
            </div>
            <div className="rounded-xl border bg-gray-50 p-4">
              <div className="text-xs font-semibold text-gray-600">Avg Feedback Score</div>
              <div className="mt-1 text-2xl font-extrabold tracking-tight">
                {stats.average_feedback_score == null
                  ? "-"
                  : Number(stats.average_feedback_score).toFixed(2)}
              </div>
            </div>
          </div>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card
          title="Candidate Interview History"
          icon={<History className="h-4 w-4" />}
          right={
            <Button variant="secondary" onClick={loadCandidateHistory} disabled={historyBusy}>
              {historyBusy ? "Loading…" : "Load History"}
            </Button>
          }
        >
          <div className="grid gap-3">
            <Select
              label="Candidate"
              value={candidateId}
              onChange={setCandidateId}
              options={candidateOptions}
            />
          </div>

          {candidateHistory ? (
            <div className="mt-4">
              <div className="mb-2 text-sm text-gray-700">
                {candidateHistory.candidate_name} ({candidateHistory.candidate_id})
              </div>
              <div className="mb-3 flex flex-wrap gap-2 text-xs">
                <div className="rounded-xl border bg-gray-50 px-3 py-1">
                  Total: <span className="font-bold">{candidateHistory.total_interviews}</span>
                </div>
                <div className="rounded-xl border bg-gray-50 px-3 py-1">
                  Completed:{" "}
                  <span className="font-bold">{candidateHistory.completed_interviews}</span>
                </div>
                <div className="rounded-xl border bg-gray-50 px-3 py-1">
                  Cancelled:{" "}
                  <span className="font-bold">{candidateHistory.cancelled_interviews}</span>
                </div>
              </div>
              <Table
                columns={[
                  { key: "round", header: "Round" },
                  { key: "start", header: "Start" },
                  { key: "end", header: "End" },
                  { key: "status", header: "Status" },
                  { key: "feedback", header: "Feedback" }
                ]}
                rows={(candidateHistory.interviews || []).map((i) => ({
                  round: i.panel_round_name,
                  start: formatDateTime(i.start_time),
                  end: formatDateTime(i.end_time),
                  status: <StatusBadge status={i.status} />,
                  feedback: String(i.feedback_count ?? 0)
                }))}
              />
            </div>
          ) : (
            <div className="mt-3 text-sm text-gray-600">Select a candidate and load history.</div>
          )}
        </Card>

        <Card
          title="Interviewer Workload"
          icon={<Calendar className="h-4 w-4" />}
          right={
            <Button variant="secondary" onClick={loadWorkload} disabled={workloadBusy}>
              {workloadBusy ? "Loading…" : "Load Workload"}
            </Button>
          }
        >
          <div className="grid gap-3">
            <Select
              label="Interviewer"
              value={interviewerId}
              onChange={setInterviewerId}
              options={interviewerOptions}
            />
          </div>

          {workload ? (
            <div className="mt-4">
              <div className="mb-2 text-sm text-gray-700">
                {workload.interviewer_name} ({workload.interviewer_id})
              </div>
              <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl border bg-gray-50 p-3">
                  Panels: <span className="font-bold">{workload.total_panels}</span>
                </div>
                <div className="rounded-xl border bg-gray-50 p-3">
                  Interviews: <span className="font-bold">{workload.total_interviews}</span>
                </div>
              </div>
              <div className="mb-2 text-xs font-semibold text-gray-600">Upcoming</div>
              {workload.upcoming_interviews?.length ? (
                <Table
                  columns={[
                    { key: "candidate", header: "Candidate" },
                    { key: "round", header: "Round" },
                    { key: "start", header: "Start" },
                    { key: "status", header: "Status" }
                  ]}
                  rows={workload.upcoming_interviews.map((i) => ({
                    candidate: `${i.candidate_name} (${i.candidate_id})`,
                    round: i.panel_round_name,
                    start: formatDateTime(i.start_time),
                    status: <StatusBadge status={i.status} />
                  }))}
                />
              ) : (
                <div className="text-sm text-gray-600">No upcoming interviews.</div>
              )}
            </div>
          ) : (
            <div className="mt-3 text-sm text-gray-600">Select an interviewer and load workload.</div>
          )}
        </Card>
      </div>
    </div>
  );
}

