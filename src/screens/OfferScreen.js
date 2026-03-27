// Offer creation and negotiation view (integrated with backend API).
import { useMemo, useState } from "react";
import { BadgeDollarSign } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge } from "../components/ui";

export default function OfferScreen({
  candidate,
  job,
  candidates = [],
  jobs = [],
  selectedCandidateId = "",
  selectedJobId = "",
  onChangeCandidate,
  onChangeJob,
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
  const normalizeText = (value) =>
    String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

  const findMatchingJobForCandidate = (candidateJobTitle) => {
    const normalizedCandidateJob = normalizeText(candidateJobTitle);
    if (!normalizedCandidateJob || !Array.isArray(jobs) || !jobs.length) return null;
    const exact = jobs.find(
      (j) => normalizeText(j?.title) === normalizedCandidateJob
    );
    if (exact) return exact;
    const contains = jobs.find((j) => {
      const normalizedJobTitle = normalizeText(j?.title);
      return (
        normalizedJobTitle.includes(normalizedCandidateJob) ||
        normalizedCandidateJob.includes(normalizedJobTitle)
      );
    });
    return contains || null;
  };

  const [selectionNotice, setSelectionNotice] = useState("");

  const activeCandidate = useMemo(() => {
    return (
      candidates.find((c) => String(c.id) === String(selectedCandidateId || candidate?.id)) ||
      candidate
    );
  }, [candidates, selectedCandidateId, candidate]);

  const activeJob = useMemo(() => {
    return jobs.find((j) => String(j.id) === String(selectedJobId || job?.id)) || job;
  }, [jobs, selectedJobId, job]);

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

        {candidates.length > 0 && jobs.length > 0 ? (
          <div className="mb-4 grid gap-3 md:grid-cols-2">
            <label className="block">
              <div className="mb-1 text-xs font-semibold text-gray-700">Candidate</div>
              <select
                value={activeCandidate?.id || ""}
                onChange={(event) => {
                  const value = event.target.value;
                  onChangeCandidate?.(value);
                  const nextCandidate = candidates.find((c) => String(c.id) === String(value));
                  const matchedJob = findMatchingJobForCandidate(nextCandidate?.jobTitle);
                  if (matchedJob) {
                    onChangeJob?.(matchedJob.id);
                    setSelectionNotice(`Auto-selected job "${matchedJob.title}" for ${nextCandidate?.name}.`);
                  } else if (nextCandidate?.jobTitle) {
                    setSelectionNotice(
                      `No matching job for job title "${nextCandidate.jobTitle}".`
                    );
                  } else {
                    setSelectionNotice("");
                  }
                }}
                className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
              >
                {candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.id})
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <div className="mb-1 text-xs font-semibold text-gray-700">Job</div>
              <select
                value={activeJob?.id || ""}
                onChange={(event) => {
                  onChangeJob?.(event.target.value);
                  setSelectionNotice("");
                }}
                className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
              >
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} ({j.id})
                  </option>
                ))}
              </select>
            </label>
            {selectionNotice ? (
              <div className="md:col-span-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                {selectionNotice}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Candidate</div>
            <div className="text-sm font-extrabold tracking-tight">
              {activeCandidate?.name}
            </div>
            <div className="mt-1 text-xs text-gray-600">{activeCandidate?.email}</div>
          </div>
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Job</div>
            <div className="text-sm font-extrabold tracking-tight">
              {activeJob?.title}
            </div>
            <div className="mt-1 text-xs text-gray-600">{activeJob?.location}</div>
          </div>

          {users?.length > 0 ? (
            <div className="rounded-2xl border bg-white p-4 md:col-span-2">
              <div className="grid gap-3 md:grid-cols-2">
                <Select
                  label="Hiring Manager"
                  value={offer?.hiringManagerId || activeJob?.hiringManager || ""}
                  onChange={(v) => setOffer((o) => ({ ...o, hiringManagerId: v }))}
                  options={["", ...users.map((u) => u.user_id)]}
                />
                <Select
                  label="Reporting Manager"
                  value={offer?.reportingManagerId || offer?.hiringManagerId || activeJob?.hiringManager || ""}
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
                value={offer?.position || activeJob?.title || ""}
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
