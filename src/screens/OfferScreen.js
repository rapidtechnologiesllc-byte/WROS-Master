// Offer creation and negotiation view (integrated with backend API).
import { BadgeDollarSign } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge } from "../components/ui";

export default function OfferScreen({
  candidate,
  job,
  offer,
  setOffer,
  users = [],
  existingOffer,
  onCreate,
  onUpdate,
  onReloadDetails,
  onCancel,
  onAccept,
  onDecline,
  loading,
  error
}) {
  const isPending = existingOffer?.offer_status === "Pending";
  const canEdit = !existingOffer || isPending;

  return (
    <div className="grid gap-4">
      <Card
        title={existingOffer ? "Offer Letter" : "Create Offer Letter"}
        icon={<BadgeDollarSign className="h-4 w-4" />}
        right={
          <StatusBadge
            status={
              existingOffer?.offer_status ||
              offer?.state ||
              (existingOffer ? "Pending" : "Draft")
            }
          />
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Candidate</div>
            <div className="text-sm font-extrabold tracking-tight">
              {candidate?.name}
            </div>
            <div className="mt-1 text-xs text-gray-600">{candidate?.email}</div>
          </div>
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Job</div>
            <div className="text-sm font-extrabold tracking-tight">
              {job?.title}
            </div>
            <div className="mt-1 text-xs text-gray-600">{job?.location}</div>
          </div>

          {users?.length > 0 ? (
            <div className="rounded-2xl border bg-white p-4 md:col-span-2">
              <div className="grid gap-3 md:grid-cols-2">
                <Select
                  label="Hiring Manager"
                  value={offer?.hiringManagerId || job?.hiringManager || ""}
                  onChange={(v) => setOffer((o) => ({ ...o, hiringManagerId: v }))}
                  options={["", ...users.map((u) => u.user_id)]}
                />
                <Select
                  label="Reporting Manager"
                  value={offer?.reportingManagerId || offer?.hiringManagerId || job?.hiringManager || ""}
                  onChange={(v) => setOffer((o) => ({ ...o, reportingManagerId: v }))}
                  options={["", ...users.map((u) => u.user_id)]}
                />
              </div>
            </div>
          ) : null}

          <div className="rounded-2xl border bg-white p-4">
            <div className="grid gap-3">
              <Input
                label="Position"
                value={offer?.position || job?.title || ""}
                onChange={(v) => setOffer((o) => ({ ...o, position: v }))}
                disabled={!canEdit}
              />
              <Input
                label="Salary (USD)"
                value={String(offer?.salary ?? existingOffer?.salary ?? 0)}
                onChange={(v) =>
                  setOffer((o) => ({ ...o, salary: Number(v || 0) }))
                }
                disabled={!canEdit}
              />
              <Input
                label="Joining Date"
                type="date"
                value={
                  offer?.startDate ||
                  offer?.joiningDate ||
                  existingOffer?.joining_date ||
                  ""
                }
                onChange={(v) =>
                  setOffer((o) => ({
                    ...o,
                    startDate: v,
                    joiningDate: v
                  }))
                }
                disabled={!canEdit}
              />
            </div>
          </div>

          {canEdit && !existingOffer ? (
            <div className="rounded-2xl border bg-white p-4">
              <div className="text-xs font-semibold text-gray-500">
                Create & Send
              </div>
              <div className="mt-2 text-sm text-gray-700">
                Create the offer letter and notify the candidate.
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={() => setOffer((o) => ({ ...o, state: "Negotiation" }))}
                >
                  Willing to negotiate
                </Button>
                <Button onClick={onCreate} disabled={loading}>
                  {loading ? "Creating…" : "Create & Send Offer"}
                </Button>
              </div>
            </div>
          ) : null}

          {existingOffer && isPending ? (
            <div className="rounded-2xl border bg-white p-4">
              <div className="text-xs font-semibold text-gray-500">
                Update, Reload or Cancel
              </div>
              <div className="mt-2 text-sm text-gray-700">
                Update offer details, reload from server, or cancel the offer.
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={onUpdate}
                  disabled={loading}
                >
                  {loading ? "Updating…" : "Update Offer"}
                </Button>
                <Button
                  variant="secondary"
                  onClick={onReloadDetails}
                  disabled={loading}
                >
                  Reload from server
                </Button>
                <Button variant="danger" onClick={onCancel} disabled={loading}>
                  Cancel Offer
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        {existingOffer && isPending ? (
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="danger" onClick={onDecline} disabled={loading}>
              Offer declined (by candidate)
            </Button>
            <Button onClick={onAccept} disabled={loading}>
              Proceed (candidate accepted)
            </Button>
          </div>
        ) : null}

        {existingOffer?.offer_status === "Accepted" ? (
          <div className="mt-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
            Offer accepted by candidate. Proceed to documents.
          </div>
        ) : null}
      </Card>
    </div>
  );
}
