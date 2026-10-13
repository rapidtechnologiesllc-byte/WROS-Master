// Hiring Pipeline: every candidate's place in the hiring order
// (screen -> L1 -> L2 -> offer -> onboarding -> BGV -> bench -> client -> allocated)
// and exactly what each one is waiting for. The stage is derived by the backend from facts;
// this screen is where people supply the facts only they can: screen decision, a round
// verdict when feedback is mixed, document checks, BGV, and the client's start date.
import { useCallback, useEffect, useState } from "react";
import { GitBranch, RefreshCw, X } from "lucide-react";
import { Button, Card, Input, Table } from "../components/ui";
import {
  confirmClientStart,
  decideRound,
  evaluatePipeline,
  getCandidateBgv,
  getCandidatePipeline,
  getOnboarding,
  listClientOnboardings,
  listPipelines,
  listVerdicts,
  recordBgvVerdict,
  recordScreen,
  reviewDocument,
  setRoundLevel,
  startBgv,
  waiveBgv,
} from "../services/api/hiringPipeline";

const STAGES = ["SCREEN", "L1", "L2", "OFFER", "ONBOARDING", "BGV", "BENCH", "SUBMITTED", "CLIENT_SELECTED", "CLIENT_ONBOARDING"];
const LEVELS = ["SCREEN", "L1", "L2", "OTHER"];
const label = (stage) => (stage || "").replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
const when = (value) => (value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");

function Section({ title, children }) {
  return (
    <div className="mt-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</div>
      {children}
    </div>
  );
}

function CandidateDrawer({ candidateId, onClose, onChanged }) {
  const [pipeline, setPipeline] = useState(null);
  const [verdicts, setVerdicts] = useState([]);
  const [onboarding, setOnboarding] = useState(null);
  const [bgv, setBgv] = useState([]);
  const [vendor, setVendor] = useState("");
  const [vendorRef, setVendorRef] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [p, v, o, b] = await Promise.all([
        getCandidatePipeline(candidateId),
        listVerdicts(candidateId),
        getOnboarding(candidateId),
        getCandidateBgv(candidateId),
      ]);
      setPipeline(p);
      setVerdicts(v || []);
      setOnboarding(o);
      setBgv(b || []);
    } catch (err) {
      setError(err.message || "Failed to load the candidate's pipeline.");
    }
  }, [candidateId]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await evaluatePipeline(candidateId);
      await load();
      onChanged();
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  const currentBgv = bgv[0];

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/20" onClick={onClose}>
      <div className="h-full w-full max-w-2xl overflow-y-auto bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs text-gray-500">{candidateId}</div>
            <div className="text-lg font-semibold text-gray-900">{pipeline ? label(pipeline.stage) : "Loading…"}</div>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-gray-500 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>
        {error ? <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
        {pipeline ? (
          <>
            <Section title="Waiting for">
              {(pipeline.blockers || []).length ? (
                <ul className="list-disc pl-5 text-sm text-gray-800">
                  {pipeline.blockers.map((b) => <li key={b}>{b}</li>)}
                </ul>
              ) : (
                <div className="text-sm text-gray-600">Nothing — {pipeline.closed_at ? "pipeline closed" : "moving on"}.</div>
              )}
              {pipeline.grandfathered ? <div className="mt-1 text-xs text-amber-700">Employee before the pipeline existed (earlier steps treated as done).</div> : null}
            </Section>

            {pipeline.stage === "SCREEN" ? (
              <Section title="Recruiter screen">
                <div className="flex gap-2">
                  {["PASS", "SKIP", "FAIL"].map((d) => (
                    <Button key={d} variant={d === "FAIL" ? "ghost" : "primary"} disabled={busy} onClick={() => act(() => recordScreen(candidateId, d))}>
                      {d === "PASS" ? "Passed screen" : d === "SKIP" ? "Skip screen" : "Failed screen"}
                    </Button>
                  ))}
                </div>
              </Section>
            ) : null}

            <Section title="Interview rounds">
              {verdicts.length === 0 ? <div className="text-sm text-gray-500">No interview rounds yet.</div> : (
                <div className="grid gap-2">
                  {verdicts.map((v) => (
                    <div key={v.panel_id} className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                      <span className="font-semibold">{v.round_name || `Round ${v.panel_id}`}</span>
                      <select
                        value={v.level}
                        disabled={busy}
                        onChange={(e) => act(() => setRoundLevel(v.panel_id, e.target.value))}
                        className="rounded border px-2 py-1 text-xs"
                      >
                        {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
                      </select>
                      <span className={v.verdict === "PASS" ? "text-emerald-700" : v.verdict === "FAIL" ? "text-rose-700" : "text-amber-700"}>
                        {label(v.verdict)}{v.source === "MANUAL" ? " (decided)" : ""}
                      </span>
                      {v.verdict === "NEEDS_DECISION" || v.verdict === "PENDING" ? (
                        <span className="ml-auto flex gap-1">
                          <Button disabled={busy} onClick={() => act(() => decideRound(v.panel_id, "PASS"))}>Pass</Button>
                          <Button variant="ghost" disabled={busy} onClick={() => act(() => decideRound(v.panel_id, "FAIL"))}>Fail</Button>
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </Section>

            {onboarding && onboarding.documents.length ? (
              <Section title={`Pre-joining documents (joining ${onboarding.joining_date || "TBD"})`}>
                <div className="grid gap-2">
                  {onboarding.documents.map((d) => (
                    <div key={d.id} className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                      <span className="flex-1">{d.label}</span>
                      <span className="text-xs font-semibold text-gray-600">{label(d.status)}</span>
                      {d.status === "RECEIVED" ? (
                        <>
                          <Button disabled={busy} onClick={() => act(() => reviewDocument(d.id, "VERIFIED"))}>Verify</Button>
                          <Button variant="ghost" disabled={busy} onClick={() => act(() => reviewDocument(d.id, "PENDING"))}>Ask again</Button>
                        </>
                      ) : null}
                      {d.status === "PENDING" ? (
                        <Button variant="ghost" disabled={busy} onClick={() => act(() => reviewDocument(d.id, "WAIVED"))}>Not needed</Button>
                      ) : null}
                    </div>
                  ))}
                </div>
                {onboarding.checklists.length ? (
                  <div className="mt-2 text-xs text-gray-600">
                    Checklists: {onboarding.checklists.map((c) => `${c.name} (${c.status})`).join(", ")}
                  </div>
                ) : null}
              </Section>
            ) : null}

            {currentBgv ? (
              <Section title={`Background verification — ${label(currentBgv.status)}`}>
                {currentBgv.status === "NOT_STARTED" || currentBgv.status === "IN_PROGRESS" ? (
                  <div className="grid gap-2">
                    {currentBgv.status === "NOT_STARTED" ? (
                      <div className="grid grid-cols-2 gap-2">
                        <Input label="Vendor" value={vendor} onChange={setVendor} />
                        <Input label="Vendor reference" value={vendorRef} onChange={setVendorRef} />
                        <div className="col-span-2">
                          <Button disabled={busy || !vendor} onClick={() => act(() => startBgv(currentBgv.id, vendor, vendorRef || undefined))}>
                            Start BGV (needs the consent document)
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-xs text-gray-600">{currentBgv.vendor_name} {currentBgv.vendor_reference || ""}</div>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <Button disabled={busy} onClick={() => act(() => recordBgvVerdict(currentBgv.id, "PASSED"))}>BGV passed</Button>
                      <Button variant="ghost" disabled={busy} onClick={() => act(() => recordBgvVerdict(currentBgv.id, "FAILED"))}>BGV failed</Button>
                    </div>
                    <div className="flex items-end gap-2">
                      <div className="flex-1"><Input label="Waive BGV — reason (recorded)" value={reason} onChange={setReason} /></div>
                      <Button variant="ghost" disabled={busy || !reason.trim()} onClick={() => act(() => waiveBgv(currentBgv.id, reason))}>Waive</Button>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-gray-700">
                    {currentBgv.verdict_by ? `By ${currentBgv.verdict_by} on ${when(currentBgv.verdict_at)}` : null}
                    {currentBgv.waiver_reason ? ` — ${currentBgv.waiver_reason}` : null}
                  </div>
                )}
              </Section>
            ) : null}

            <Section title="History">
              <div className="grid gap-1 text-xs text-gray-600">
                {(pipeline.events || []).map((e, i) => (
                  <div key={i}>
                    {when(e.at)} · {e.from_stage ? `${label(e.from_stage)} → ` : ""}{label(e.to_stage)} · {e.trigger}{e.note ? ` · ${e.note}` : ""}
                  </div>
                ))}
              </div>
            </Section>
          </>
        ) : null}
      </div>
    </div>
  );
}

function ClientOnboardingCard() {
  const [rows, setRows] = useState([]);
  const [dates, setDates] = useState({});
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const all = await listClientOnboardings();
      setRows((all || []).filter((r) => r.status === "PENDING" || r.status === "START_CONFIRMED"));
    } catch (err) {
      setError(err.message || "Failed to load client onboardings.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const confirm = async (row) => {
    setError("");
    try {
      await confirmClientStart(row.id, dates[row.id] || row.proposed_start_date);
      await load();
    } catch (err) {
      setError(err.message || "Could not confirm the start date.");
    }
  };

  return (
    <Card title="Client onboarding" subtitle="Selected by the client — record the start date they confirm; placement and allocation follow on that date.">
      {error ? <div className="mb-2 text-sm text-rose-700">{error}</div> : null}
      {rows.length === 0 ? <div className="text-sm text-gray-500">Nobody waiting on a client start date.</div> : (
        <Table
          rows={rows}
          columns={[
            { key: "candidate_id", header: "Candidate" },
            { key: "status", header: "Status", cell: (r) => label(r.status) },
            { key: "proposed", header: "Proposed", cell: (r) => r.proposed_start_date || "—" },
            {
              key: "confirm",
              header: "Confirmed start",
              cell: (r) => (
                <div className="flex items-end gap-2">
                  <Input type="date" value={dates[r.id] ?? r.confirmed_start_date ?? r.proposed_start_date ?? ""} onChange={(v) => setDates((d) => ({ ...d, [r.id]: v }))} />
                  <Button disabled={!(dates[r.id] || r.proposed_start_date)} onClick={() => confirm(r)}>Confirm</Button>
                </div>
              ),
            },
          ]}
        />
      )}
    </Card>
  );
}

export default function HiringPipelineScreen() {
  const [stage, setStage] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listPipelines(stage);
      setRows(data?.pipelines || []);
    } catch (err) {
      setError(err.message || "Failed to load the hiring pipeline.");
    } finally {
      setLoading(false);
    }
  }, [stage]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="grid gap-4">
      <Card
        title="Hiring Pipeline"
        icon={<GitBranch className="h-4 w-4" />}
        subtitle="Screen → L1 → L2 → offer → onboarding → BGV → bench → client. Moves on by itself; this shows who is waiting on what."
        right={<Button variant="ghost" onClick={load} disabled={loading}><RefreshCw className="h-4 w-4" />Refresh</Button>}
      >
        <div className="mb-3 flex flex-wrap gap-2">
          {["", ...STAGES].map((s) => (
            <button
              key={s || "all"}
              type="button"
              onClick={() => setStage(s)}
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${stage === s ? "border-bx-orange bg-bx-orange text-white" : "text-gray-700"}`}
            >
              {s ? label(s) : "All open"}
            </button>
          ))}
        </div>
        {error ? <div className="mb-2 text-sm text-rose-700">{error}</div> : null}
        {rows.length === 0 ? (
          <div className="text-sm text-gray-500">{loading ? "Loading…" : "No candidates at this stage."}</div>
        ) : (
          <Table
            rows={rows.map((r) => ({ ...r, id: r.candidate_id }))}
            columns={[
              {
                key: "candidate_id",
                header: "Candidate",
                cell: (r) => (
                  <button type="button" className="font-semibold text-bx-orange underline" onClick={() => setOpen(r.candidate_id)}>
                    {r.candidate_id}
                  </button>
                ),
              },
              { key: "stage", header: "Stage", cell: (r) => label(r.stage) },
              { key: "since", header: "Since", cell: (r) => when(r.stage_entered_at) },
              { key: "blockers", header: "Waiting for", cell: (r) => (r.blockers || []).join("; ") || "—" },
            ]}
          />
        )}
      </Card>
      <ClientOnboardingCard />
      {open ? <CandidateDrawer candidateId={open} onClose={() => setOpen(null)} onChanged={load} /> : null}
    </div>
  );
}
