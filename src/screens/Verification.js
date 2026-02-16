// Document verification placeholder screen.
import { ClipboardCheck } from "lucide-react";
import { Button, Card, StatusBadge } from "../components/ui";

export default function Verification({ onApprove, onReject }) {
  return (
    <div className="grid gap-4">
      <Card
        title="Document Verification"
        icon={<ClipboardCheck className="h-4 w-4" />}
        right={<StatusBadge status="Requested" />}
      >
        <div className="rounded-2xl border bg-gray-50 p-4 text-sm text-gray-700">
          Review uploaded documents and mark as Verified or Pending/Rejected.
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={onReject}>
            Pending / Rejected
          </Button>
          <Button onClick={onApprove}>Verified</Button>
        </div>
      </Card>
    </div>
  );
}
