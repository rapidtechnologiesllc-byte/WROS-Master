// HR/Admin view for active/public jobs.
import { useEffect, useState } from "react";
import { Briefcase, Plus } from "lucide-react";
import { Button, Card, StatusBadge, Table } from "../components/ui";
import { getActiveJobs } from "../services/api/jobs";

const mapJobFromApi = (j) => ({
  id: j.job_id,
  title: j.job_title,
  dept: "",
  location: j.job_location || "",
  skills: String(j.job_skills || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  hiringManager: j.hiring_manager_id || "",
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

export default function ActiveJobs({ onCreate, onOpenJob, onDeleteJob, onPostToLinkedIn }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState([]);
  const canDelete = Boolean(onDeleteJob);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getActiveJobs();
      const list = Array.isArray(res?.jobs) ? res.jobs : [];
      setJobs(list.map(mapJobFromApi));
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
            title: j.title,
            status: <StatusBadge status={j.status} />,
            location: j.location || "-",
            hm: j.hiringManager || "-",
            edit: (
              <Button variant="secondary" onClick={() => onOpenJob(j.id)}>
                Edit
              </Button>
            ),
            linkedin: onPostToLinkedIn ? (
              <Button variant="secondary" onClick={() => onPostToLinkedIn(j.id)}>
                Post to LinkedIn
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

