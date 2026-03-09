// HR view of assigned candidates and interviews.
import { useEffect, useState } from "react";
import { UserCheck, Calendar } from "lucide-react";
import { Card, Table, StatusBadge } from "../components/ui";
import { getAssignedCandidates, getAssignedInterviews } from "../services/api/users";

export default function AssignmentsScreen() {
  const [candidates, setCandidates] = useState([]);
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [candRes, intRes] = await Promise.all([
          getAssignedCandidates(),
          getAssignedInterviews()
        ]);
        if (isMounted) {
          setCandidates(Array.isArray(candRes) ? candRes : []);
          setInterviews(Array.isArray(intRes) ? intRes : []);
        }
      } catch (err) {
        if (isMounted)
          setError(err.message || "Failed to load assignments.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    load();
    return () => { isMounted = false; };
  }, []);

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
        {candidates.length ? (
          <Table
            columns={[
              { key: "candidate_id", header: "Candidate ID" },
              { key: "candidate_name", header: "Name" },
              { key: "candidate_email", header: "Email" },
              { key: "assignment_type", header: "Role" }
            ]}
            rows={candidates.map((c) => ({
              candidate_id: c.candidate_id,
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
