// Pre-onboarding: HR checklist from backend + pipeline context.
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, ListChecks } from "lucide-react";
import { Button, Card, StatusBadge } from "../components/ui";
import { getCandidateStatus } from "../services/api/candidateStatus";
import {
  assignChecklistToCandidate,
  getCandidateChecklists,
  hrCompleteChecklistItem,
  listChecklistTemplates
} from "../services/api/checklists";

function canHrCompleteItem(item) {
  if (!item || item.status === "completed") return false;
  if (item.item_type === "todo") return item.status === "pending";
  if (item.item_type === "queue") return item.status === "active";
  return false;
}

export default function PreOnboarding({
  onFinish,
  candidate,
  candidates = [],
  selectedCandidateId = "",
  onChangeCandidate
}) {
  const [loading, setLoading] = useState(true);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pipeline, setPipeline] = useState(null);
  const [checklistsPayload, setChecklistsPayload] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [completingId, setCompletingId] = useState(null);
  
useEffect(() => {
  if (!notice) return;

  const timer = setTimeout(() => {
    setNotice("");
  }, 3000);

  return () => clearTimeout(timer);
}, [notice]);

  const activeCandidate = useMemo(() => {
    return (
      candidates.find((c) => String(c.id) === String(selectedCandidateId || candidate?.id)) ||
      candidate
    );
  }, [candidates, selectedCandidateId, candidate]);

  const reload = useCallback(async () => {
    if (!activeCandidate?.id) {
      setLoading(false);
      setChecklistsPayload(null);
      setPipeline(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [statusRes, listRes] = await Promise.all([
        getCandidateStatus(activeCandidate.id),
        getCandidateChecklists(activeCandidate.id)
      ]);
      setPipeline(statusRes);
      setChecklistsPayload(listRes);
    } catch (err) {
      setError(err.message || "Failed to load pre-onboarding data.");
      setChecklistsPayload(null);
      setPipeline(null);
    } finally {
      setLoading(false);
    }
  }, [activeCandidate?.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    let mounted = true;
    const loadT = async () => {
      setTemplatesLoading(true);
      try {
        const res = await listChecklistTemplates();
        if (!mounted) return;
        const list = res?.templates || [];
        setTemplates(list);
        if (list.length && !selectedTemplateId) {
          setSelectedTemplateId(String(list[0].id));
        }
      } catch (err) {
        if (!mounted) return;
        setTemplates([]);
      } finally {
        if (mounted) setTemplatesLoading(false);
      }
    };
    loadT();
    return () => {
      mounted = false;
    };
  }, []);

  const checklists = checklistsPayload?.checklists || [];

  const allChecklistsComplete =
    checklists.length > 0 && checklists.every((cl) => cl.status === "completed");

  const handleAssign = async () => {
    if (!activeCandidate?.id || !selectedTemplateId) return;
    setAssigning(true);
    setNotice("");
    setError("");
    try {
      await assignChecklistToCandidate({
        candidateId: activeCandidate.id,
        templateId: selectedTemplateId
      });
      setNotice("Checklist assigned.");
      await reload();
    } catch (err) {
      setError(err.message || "Failed to assign checklist.");
    } finally {
      setAssigning(false);
    }
  };

  const handleCompleteItem = async (itemId) => {
    setCompletingId(itemId);
    setNotice("");
    setError("");
    try {
      await hrCompleteChecklistItem(itemId);
      await reload();
      setNotice("Item marked complete.");
    } catch (err) {
      setError(err.message || "Failed to complete item.");
    } finally {
      setCompletingId(null);
    }
  };

  return (
    <div className="grid gap-4">
      <Card title="Pre-Onboarding" icon={<CheckCircle2 className="h-4 w-4" />}>
        {candidates.length > 0 && onChangeCandidate ? (
          <label className="mb-4 block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Candidate</div>
            <select
              value={activeCandidate?.id || ""}
              onChange={(e) => onChangeCandidate(e.target.value)}
              className="w-full max-w-md rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.id})
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-gray-700">
          <span>
            For: <span className="font-semibold">{activeCandidate?.name || "—"}</span>
            {activeCandidate?.email ? (
              <span className="ml-2 text-gray-500">({activeCandidate.email})</span>
            ) : null}
          </span>
          {(pipeline?.pipeline_status || activeCandidate?.pipelineStatus) ? (
            <StatusBadge status={pipeline?.pipeline_status || activeCandidate.pipelineStatus} />
          ) : null}
        </div>

        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {notice}
          </div>
        ) : null}

        {loading ? (
          <div className="py-6 text-center text-sm text-gray-500">Loading checklist…</div>
        ) : !checklists.length ? (
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="flex items-start gap-2 text-sm text-gray-700">
              <ListChecks className="mt-0.5 h-4 w-4 shrink-0 text-gray-500" />
              <div>
                <div className="font-semibold">No checklist assigned yet</div>
                <div className="mt-1 text-xs text-gray-600">
                  Assign a template to start pre-onboarding tasks for this candidate.
                </div>
              </div>
            </div>
            {templatesLoading ? (
              <div className="mt-3 text-xs text-gray-500">Loading templates…</div>
            ) : templates.length ? (
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="block flex-1">
                  <div className="mb-1 text-xs font-semibold text-gray-700">Template</div>
                  <select
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
                  >
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.item_count ?? 0} items)
                      </option>
                    ))}
                  </select>
                </label>
                <Button onClick={handleAssign} disabled={assigning || !selectedTemplateId}>
                  {assigning ? "Assigning…" : "Assign checklist"}
                </Button>
              </div>
            ) : (
              <div className="mt-3 text-sm text-amber-800">
                No checklist templates found. Create one via the API or admin tools first.
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {checklists.map((cl) => (
              <div key={cl.id} className="rounded-2xl border bg-white p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-semibold">
                    {cl.template_name || `Checklist #${cl.id}`}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-600">
                    <span>
                      {cl.completed_items ?? 0}/{cl.total_items ?? 0} done
                    </span>
                    <StatusBadge status={cl.status === "completed" ? "Completed" : "Scheduled"} />
                  </div>
                </div>
                <ul className="space-y-2">
                  {(cl.items || [])
                    .slice()
                    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
                    .map((item) => {
                      const actionable = canHrCompleteItem(item);
                      const waitingQueue =
                        item.item_type === "queue" &&
                        item.status === "pending" &&
                        !actionable;
                      return (
                        <li
                          key={item.id}
                          className="flex flex-col gap-2 rounded-xl border border-gray-100 bg-gray-50 p-3 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div>
                            <div className="text-sm font-medium">{item.title}</div>
                            {item.description ? (
                              <div className="mt-0.5 text-xs text-gray-600">{item.description}</div>
                            ) : null}
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                              <span className="rounded-md border bg-white px-2 py-0.5">
                                {item.item_type}
                              </span>
                              <StatusBadge status={item.status} />
                            </div>
                            {waitingQueue ? (
                              <div className="mt-1 text-xs text-amber-700">Awaiting previous step</div>
                            ) : null}
                          </div>
                          {item.status !== "completed" ? (
                            <Button
                              variant="secondary"
                              onClick={() => handleCompleteItem(item.id)}
                              disabled={!actionable || completingId === item.id}
                            >
                              {completingId === item.id ? "Saving…" : "Mark complete"}
                            </Button>
                          ) : (
                            <span className="text-xs font-semibold text-green-700">Done</span>
                          )}
                        </li>
                      );
                    })}
                </ul>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          <Button
            onClick={onFinish}
            disabled={loading || !allChecklistsComplete}
          >
            Finish (complete hire)
          </Button>
        </div>

        <div className="mt-2 text-xs text-gray-500">
          All checklist items must be completed before finishing. Pipeline updates to Onboarded when you
          finish.
        </div>
      </Card>
    </div>
  );
}
