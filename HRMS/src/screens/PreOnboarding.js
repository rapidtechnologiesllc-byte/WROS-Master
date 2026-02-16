// Pre-onboarding checklist view.
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Button, Card } from "../components/ui";

export default function PreOnboarding({ onFinish }) {
  const [tasks, setTasks] = useState({
    employeeId: false,
    accounts: false,
    welcome: false
  });
  const done = Object.values(tasks).every(Boolean);

  return (
    <div className="grid gap-4">
      <Card title="Pre-Onboarding" icon={<CheckCircle2 className="h-4 w-4" />}>
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
