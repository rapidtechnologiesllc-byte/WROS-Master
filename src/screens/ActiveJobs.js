// HR/Admin view for active/public jobs.
import { useEffect, useState } from "react";
import { Briefcase, Plus } from "lucide-react";
import { Button, Card, StatusBadge, Table } from "../components/ui";
import { getActiveJobs } from "../services/api/jobs";
import { getAllUsers } from "../services/api/users";

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
    if (raw === "closed") return "Closed";
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

export default function ActiveJobs({ onCreate, onOpenJob, onViewJob, onDeleteJob, onPostToLinkedIn }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState([]);
  const canDelete = Boolean(onDeleteJob);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const [jobsRes, usersRes] = await Promise.all([
        getActiveJobs(),
        getAllUsers()
      ]);
      const list = Array.isArray(jobsRes?.jobs) ? jobsRes.jobs : [];
      const users = usersRes?.users || [];
      setJobs(list.map((j) => mapJobFromApi(j, users)));
    } catch (err) {
      setError(err.message || "Failed to load active jobs.");
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  if (loading) {
    return (
      <Card title="Active Jobs" icon={<Briefcase className="h-4 w-4" />}>
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

      <Card
        title="Active Jobs"
        icon={<Briefcase className="h-4 w-4" />}
        right={
          onCreate ? (
            <Button onClick={onCreate}>
              <Plus className="h-4 w-4" /> Create Job
            </Button>
          ) : null
        }
      >
        <Table
          columns={[
            { key: "title", header: "Title" },
            { key: "status", header: "Status" },
            { key: "location", header: "Location" },
            { key: "hm", header: "Hiring Manager" },
            { key: "edit", header: "Edit" },
            ...(onPostToLinkedIn ? [{ key: "linkedin", header: "LinkedIn" }] : []),
            ...(canDelete ? [{ key: "delete", header: "Delete" }] : [])
          ]}
          rows={jobs.map((j) => ({
            title: (
              <button
                className="font-semibold hover:underline"
                onClick={() => (onViewJob ? onViewJob(j.id) : onOpenJob(j.id))}
              >
                {j.title}
              </button>
            ),
            status: <StatusBadge status={j.status} />,
            location: j.location || "-",
            hm: j.hiringManagerName || j.hiringManager || "-",
            edit: (
              <Button variant="secondary" onClick={() => onOpenJob(j.id)}>
                Edit
              </Button>
            ),
            linkedin: onPostToLinkedIn ? (
              <Button
                variant="secondary"
                onClick={() => onPostToLinkedIn(j.id)}
                title="LinkedIn integration is not yet connected -- this only simulates a post, nothing goes live on LinkedIn."
              >
                Simulate LinkedIn Post
              </Button>
            ) : null,
            delete: canDelete ? (
              <Button variant="danger" onClick={() => onDeleteJob(j.id)}>
                Delete
              </Button>
            ) : undefined
          }))}
        />
      </Card>
    </div>
  );
}

