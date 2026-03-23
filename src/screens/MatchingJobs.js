// Matching jobs view (client-side scoring).
import { useMemo } from "react";
import { Briefcase } from "lucide-react";
import { Button, Card, StatusBadge } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export default function MatchingJobs({ candidate, jobs, onApply }) {
  const ranked = useMemo(() => {
    const set = new Set(candidate.skills.map((s) => s.toLowerCase()));
    return jobs
      // Backend allows applications only for `active/public` jobs.
      // We normalize them into UI labels: `Open` (active) and `Public` (public).
      .filter((j) => j.status === "Open" || j.status === "Public")
      .map((j) => {
        const score = j.skills.reduce(
          (acc, s) => acc + (set.has(s.toLowerCase()) ? 1 : 0),
          0
        );
        return { job: j, score };
      })
      .sort((a, b) => b.score - a.score);
  }, [candidate.skills, jobs]);

  return (
    <div className="grid gap-4">
      <Card title="Matching Jobs" icon={<Briefcase className="h-4 w-4" />}>
        <div className="mb-3 text-sm text-gray-700">
          Candidate: <span className="font-semibold">{candidate.name}</span> (
          {candidate.id})
        </div>

        <div className="space-y-3">
          {ranked.map(({ job, score }) => (
            <div
              key={job.id}
              className="flex flex-col gap-3 rounded-2xl border bg-white p-4 md:flex-row md:items-center md:justify-between"
            >
              <div>
                <div className="flex items-center gap-2">
                  <div className="text-sm font-extrabold tracking-tight">
                    {job.title}
                  </div>
                  <span className={cx(pill, "border-gray-200 bg-gray-50")}>
                    {job.id}
                  </span>
                  <StatusBadge status={job.status} />
                </div>
                <div className="mt-1 text-xs text-gray-600">
                  {job.dept} • {job.location} • HM: {job.hiringManager}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {job.skills.map((s) => (
                    <span key={s} className={cx(pill, "border-gray-200 bg-gray-50")}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-xs font-semibold text-gray-600">Match</div>
                  <div className="text-lg font-extrabold tracking-tight">
                    {Math.min(
                      100,
                      Math.round((score / Math.max(1, job.skills.length)) * 100)
                    )}
                    %
                  </div>
                </div>
                <Button onClick={() => onApply(job.id)}>Apply</Button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-3 text-xs text-gray-500">
          This maps to: “Show current open jobs matching resume with single click
          Apply”.
        </div>
      </Card>
    </div>
  );
}
