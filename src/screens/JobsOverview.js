// Job list overview with actions.
import { Briefcase, Plus } from "lucide-react";
import { Button, Card, StatusBadge, Table } from "../components/ui";

export default function JobsOverview({
  jobs,
  onCreate,
  onOpenJob,
  onViewJob,
  onDeleteJob,
  onPostToLinkedIn,
  onApproveJob,
}) {
  const canDelete = Boolean(onDeleteJob);
  const canApprove = Boolean(onApproveJob);
  const submittedCount = jobs.filter((j) => j.status === "Submitted").length;
  const totalCount = jobs.length;
  
  return (
    <div className="grid gap-4">
      <Card
        title="Jobs"
        icon={<Briefcase className="h-4 w-4" />}
        right={
          <Button onClick={onCreate}>
            <Plus className="h-4 w-4" /> Create Job
          </Button>
        }
      >
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border bg-gray-50 px-4 py-3">
            <div className="text-xs font-semibold text-gray-600">
              Submitted Jobs
            </div>
            <div className="mt-1 text-2xl font-extrabold tracking-tight">
              {submittedCount}
            </div>
          </div>
          <div className="rounded-xl border bg-gray-50 px-4 py-3">
            <div className="text-xs font-semibold text-gray-600">
              Total Jobs
            </div>
            <div className="mt-1 text-2xl font-extrabold tracking-tight">
              {totalCount}
            </div>
          </div>
        </div>
      </Card>

      <Card title="All Jobs" icon={<Briefcase className="h-4 w-4" />}>
        <Table
          columns={[
            { key: "title", header: "Title" },
            { key: "status", header: "Status" },
            { key: "dept", header: "Department" },
            { key: "location", header: "Location" },
            { key: "hm", header: "Hiring Manager" },
            { key: "edit", header: "Edit" },
            ...(canApprove ? [{ key: "approve", header: "Approve" }] : []),
            ...(onPostToLinkedIn
              ? [{ key: "linkedin", header: "LinkedIn" }]
              : []),
            ...(canDelete ? [{ key: "delete", header: "Delete" }] : []),
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
            dept: j.dept || "-",
            location: j.location || "-",
            hm: j.hiringManagerName || j.hiringManager || "-",
            edit: (
              <Button variant="secondary" onClick={() => onOpenJob(j.id)}>
                Edit
              </Button>
            ),
            ...(canApprove
              ? {
                  approve:
                    String(j.status || "")
                      .trim()
                      .toLowerCase() === "pending approval" ||
                    String(j.status || "")
                      .trim()
                      .toLowerCase() === "pending_approval" ? (
                      <Button
                        variant="success"
                        onClick={() => onApproveJob(j.id)}
                      >
                        Approve
                      </Button>
                    ) : (
                      <span className="text-xs text-gray-500">-</span>
                    ),
                }
              : {}),
            ...(onPostToLinkedIn
              ? {
                  linkedin: (
                    <Button
                      variant="secondary"
                      onClick={() => onPostToLinkedIn(j.id)}
                    >
                      Post to LinkedIn
                    </Button>
                  ),
                }
              : {}),
            delete: canDelete ? (
              <Button variant="danger" onClick={() => onDeleteJob(j.id)}>
                Delete
              </Button>
            ) : undefined,
          }))}
        />
      </Card>
    </div>
  );
}
