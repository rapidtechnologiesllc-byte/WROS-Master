// Pre-onboarding checklist view.
import { useMemo, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Button, Card } from "../components/ui";

export default function PreOnboarding({
  onFinish,
  candidate,
  candidates = [],
  selectedCandidateId = "",
  onChangeCandidate
}) {
  const [tasks, setTasks] = useState({
    employeeId: false,
    accounts: false,
    welcome: false
  });
  const done = Object.values(tasks).every(Boolean);

  const activeCandidate = useMemo(() => {
    return (
      candidates.find((c) => String(c.id) === String(selectedCandidateId || candidate?.id)) ||
      candidate
    );
  }, [candidates, selectedCandidateId, candidate]);

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

        <div className="mb-4 text-sm text-gray-700">
          Completing pre-onboarding for:{" "}
          <span className="font-semibold">{activeCandidate?.name || "—"}</span>
          {activeCandidate?.email ? (
            <span className="ml-2 text-gray-500">({activeCandidate.email})</span>
          ) : null}
        </div>

        <div className="space-y-2">
          {[
            ["Generate Employee ID", "employeeId"],
            ["Provision system accounts", "accounts"],
            ["Send welcome email", "welcome"]
          ].map(([label, key]) => (
            <label
              key={key}
              className="flex items-center justify-between rounded-2xl border bg-white p-4"
            >
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4" />
                <div className="text-sm font-semibold">{label}</div>
              </div>
              <input
                type="checkbox"
                checked={tasks[key]}
                onChange={(e) =>
                  setTasks((t) => ({ ...t, [key]: e.target.checked }))
                }
                className="h-5 w-5"
              />
            </label>
          ))}
        </div>

        <div className="mt-4 flex justify-end">
          <Button onClick={onFinish} disabled={!done}>
            Finish (Hire)
          </Button>
        </div>

        <div className="mt-2 text-xs text-gray-500">
          When all tasks are complete, workflow ends.
        </div>
      </Card>
    </div>
  );
}
