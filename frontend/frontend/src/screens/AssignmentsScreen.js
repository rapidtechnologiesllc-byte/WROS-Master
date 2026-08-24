// HR view of assigned candidates and interviews.
import { useEffect, useState } from "react";
import { UserCheck, Calendar } from "lucide-react";
import { Button, Card, Table, StatusBadge } from "../components/ui";
import { getAssignedCandidates, getAssignedInterviews } from "../services/api/users";
import { getAllUsers } from "../services/api/users";
import { createCandidateAssignment, getAllCandidates } from "../services/api/candidates";

export default function AssignmentsScreen() {
  const [candidates, setCandidates] = useState([]);
  const [interviews, setInterviews] = useState([]);
  const [allCandidates, setAllCandidates] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [candidateId, setCandidateId] = useState("");
  const [hiringManagerId, setHiringManagerId] = useState("");
  const [reportingManagerId, setReportingManagerId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formNotice, setFormNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [candRes, intRes, allCandidatesRes, usersRes] = await Promise.all([
        getAssignedCandidates(),
        getAssignedInterviews(),
        getAllCandidates(),
        getAllUsers()
      ]);
      setCandidates(Array.isArray(candRes) ? candRes : []);
      setInterviews(Array.isArray(intRes) ? intRes : []);
      const nextAllCandidates = Array.isArray(allCandidatesRes?.candidates)
        ? allCandidatesRes.candidates
        : [];
      const nextUsers = Array.isArray(usersRes) ? usersRes : [];
      setAllCandidates(nextAllCandidates);
      setAllUsers(nextUsers);
      if (!candidateId && nextAllCandidates.length) {
        setCandidateId(nextAllCandidates[0].candidate_id);
      }
      if (!hiringManagerId && nextUsers.length) {
        setHiringManagerId(nextUsers[0].user_id);
      }
      if (!reportingManagerId && nextUsers.length) {
        setReportingManagerId(nextUsers[0].user_id);
      }
    } catch (err) {
      setError(err.message || "Failed to load assignments.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreateAssignment = async () => {
    if (!candidateId) {
      setFormNotice("Please select a candidate.");
      return;
    }
    setSubmitting(true);
    setFormNotice("");
    try {
      await createCandidateAssignment({
        candidateId,
        hiringManagerId: hiringManagerId || null,
        reportingManagerId: reportingManagerId || null
      });
      setFormNotice("Assignment created successfully.");
      await load();
    } catch (err) {
      setFormNotice(err.message || "Failed to create assignment.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="grid gap-4">
        <Card title="My Assignments">
          <div className="py-4 text-center text-sm text-gray-500">
            Loading…
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <Card title="Assigned Candidates" icon={<UserCheck className="h-4 w-4" />}>
        {error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        <div className="mb-4 grid gap-3 rounded-xl border bg-slate-50 p-3 md:grid-cols-4">
          <label className="block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Candidate</div>
            <select
              value={candidateId}
              onChange={(event) => setCandidateId(event.target.value)}
              className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              {allCandidates.map((candidate) => (
                <option key={candidate.candidate_id} value={candidate.candidate_id}>
                  {candidate.candidate_name} ({candidate.candidate_id})
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Hiring Manager</div>
            <select
              value={hiringManagerId}
              onChange={(event) => setHiringManagerId(event.target.value)}
              className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              <option value="">None</option>
              {allUsers.map((user) => (
                <option key={`hm-${user.user_id}`} value={user.user_id}>
                  {user.user_name || user.user_email} ({user.user_id})
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Reporting Manager</div>
            <select
              value={reportingManagerId}
              onChange={(event) => setReportingManagerId(event.target.value)}
              className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              <option value="">None</option>
              {allUsers.map((user) => (
                <option key={`rm-${user.user_id}`} value={user.user_id}>
                  {user.user_name || user.user_email} ({user.user_id})
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end">
            <Button onClick={handleCreateAssignment} disabled={submitting}>
              {submitting ? "Assigning..." : "Create Assignment"}
            </Button>
          </div>
          {formNotice ? (
            <div className="text-xs text-gray-600 md:col-span-4">{formNotice}</div>
          ) : null}
        </div>
        {candidates.length ? (
          <Table
            columns={[
              { key: "candidate_name", header: "Name" },
              { key: "candidate_email", header: "Email" },
              { key: "assignment_type", header: "Role" }
            ]}
            rows={candidates.map((c) => ({
              candidate_name: c.candidate_name,
              candidate_email: c.candidate_email,
              assignment_type: c.assignment_type?.replace("_", " ") || "-"
            }))}
          />
        ) : (
          <div className="rounded-2xl border bg-gray-50 p-4 text-sm text-gray-600">
            No candidates assigned to you.
          </div>
        )}
      </Card>

      <Card title="Assigned Interviews" icon={<Calendar className="h-4 w-4" />}>
        {interviews.length ? (
          <Table
            columns={[
              { key: "candidate_name", header: "Candidate" },
              { key: "round_name", header: "Round" },
              { key: "start_time", header: "Start" },
              { key: "end_time", header: "End" },
              { key: "status", header: "Status" }
            ]}
            rows={interviews.map((i) => ({
              candidate_name: i.candidate_name,
              round_name: i.round_name,
              start_time: i.start_time
                ? new Date(i.start_time).toLocaleString()
                : "-",
              end_time: i.end_time
                ? new Date(i.end_time).toLocaleString()
                : "-",
              status: <StatusBadge status={i.status} />
            }))}
          />
        ) : (
          <div className="rounded-2xl border bg-gray-50 p-4 text-sm text-gray-600">
            No interviews assigned to you.
          </div>
        )}
      </Card>
    </div>
  );
}
