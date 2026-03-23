// Final approval screen for hiring manager decisions.
import { CheckCircle2, ClipboardCheck, XCircle } from "lucide-react";
import { Button, Card, StatusBadge } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export default function Approval({ candidate, onApprove, onReject }) {
  return (
    <div className="grid gap-4">
      <Card
        title="Hiring Manager – Final Approval"
        icon={<ClipboardCheck className="h-4 w-4" />}
        right={<StatusBadge status={candidate.status} />}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Candidate</div>
            <div className="text-lg font-extrabold tracking-tight">
              {candidate.name}
            </div>
            <div className="mt-1 text-xs text-gray-600">{candidate.id}</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {candidate.skills.map((s) => (
                <span key={s} className={cx(pill, "border-gray-200 bg-gray-50")}>
                  {s}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border bg-white p-4">
            <div className="text-xs font-semibold text-gray-500">Feedback (demo)</div>
            <ul className="mt-2 list-disc pl-5 text-sm text-gray-700">
              <li>Tech round: Strong fundamentals</li>
              <li>Communication: Good</li>
              <li>Recommendation: Proceed</li>
            </ul>
          </div>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="danger" onClick={onReject}>
            <XCircle className="h-4 w-4" /> Reject (No Hire)
          </Button>
          <Button onClick={onApprove}>
            <CheckCircle2 className="h-4 w-4" /> Approve
          </Button>
        </div>
      </Card>
    </div>
  );
}
