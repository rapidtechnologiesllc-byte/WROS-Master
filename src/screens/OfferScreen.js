// Offer creation and negotiation view.
import { BadgeDollarSign } from "lucide-react";
import { Button, Card, Input, StatusBadge } from "../components/ui";

export default function OfferScreen({
  candidate,
  job,
  offer,
  setOffer,
  onSend,
  onNegotiate,
  onAccept,
  onDecline
}) {
  return (
    <div className="grid gap-4">
      <Card
        title="Initiate Offer Letter"
        icon={<BadgeDollarSign className="h-4 w-4" />}
        right={<StatusBadge status={offer.state} />}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Candidate</div>
            <div className="text-sm font-extrabold tracking-tight">
              {candidate.name}
            </div>
            <div className="mt-1 text-xs text-gray-600">{candidate.email}</div>
          </div>
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Job</div>
            <div className="text-sm font-extrabold tracking-tight">{job.title}</div>
            <div className="mt-1 text-xs text-gray-600">{job.location}</div>
          </div>

          <div className="rounded-2xl border bg-white p-4">
            <div className="grid gap-3">
              <Input
                label="Salary (USD)"
                value={String(offer.salary)}
                onChange={(v) => setOffer((o) => ({ ...o, salary: Number(v || 0) }))}
              />
              <Input
                label="Start Date"
                value={offer.startDate}
                onChange={(v) => setOffer((o) => ({ ...o, startDate: v }))}
              />
            </div>
          </div>

          <div className="rounded-2xl border bg-white p-4">
            <div className="text-xs font-semibold text-gray-500">Negotiation</div>
            <div className="mt-2 text-sm text-gray-700">
              If candidate wants to negotiate, update offer details and resend.
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="secondary" onClick={onNegotiate}>
                Willing to negotiate
              </Button>
              <Button variant="secondary" onClick={onSend}>
                Send / Resend offer
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="danger" onClick={onDecline}>
            Offer declined
          </Button>
          <Button onClick={onAccept}>Offer accepted</Button>
        </div>

        <div className="mt-3 text-xs text-gray-500">
          Maps to: “Willing to Negotiate? → Discuss → Offer Update Needed → Offer
          Acceptance”.
        </div>
      </Card>
    </div>
  );
}
