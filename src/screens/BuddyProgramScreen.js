// S-364 Buddy KPI Tracking + S-365 Graduation Gate.
// KPI_DEFINITIONS mirrors app.services.buddy_program_service's own
// fixed, BU-Head-approved constant -- never recruiter-adjustable, per
// that module's own docstring, so it's safe to duplicate here rather
// than add a GET endpoint just to fetch static config.
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { Card, Button, TextArea } from "../components/ui";
import {
  createBuddyProgramRecord, exitProgram, extendProgram, getBuddyProgramRecord, getCanExtend,
  getScorecard, graduateEmployee, submitWeeklyScores,
} from "../services/api/buddyProgram";

const KPI_DEFINITIONS = {
  1: ["HR", "Timesheet Punctuality"], 2: ["HR", "HR Email Response Time"], 3: ["HR", "Onboarding Task Completion"],
  4: ["HR", "IT Setup Speed"], 5: ["HR", "Benefits Enrollment"], 6: ["HR", "Policy Sign-off Rate"],
  7: ["HR", "Background Check Responsiveness"], 8: ["HR", "Contract Execution Speed"], 9: ["HR", "Training Module Completion"],
  10: ["HR", "Meeting Attendance"], 11: ["HR", "Calendar Responsiveness"], 12: ["HR", "Written Communication Tone"],
  13: ["BUDDY", "Technical Knowledge Depth"], 14: ["BUDDY", "Requirements Understanding"], 15: ["BUDDY", "Adhoc Problem Solving"],
  16: ["BUDDY", "Learning Speed"], 17: ["BUDDY", "Work Quality"], 18: ["BUDDY", "Documentation Discipline"],
  19: ["BUDDY", "Question Quality"], 20: ["BUDDY", "Mistake Ownership"], 21: ["BUDDY", "Initiative Level"],
  22: ["BUDDY", "Team Integration Speed"], 23: ["BUDDY", "Communication Clarity"], 24: ["BUDDY", "Deadline Reliability"],
  25: ["BUDDY", "Escalation Judgement"], 26: ["BUDDY", "Pressure Behaviour"], 27: ["BUDDY", "Peer Interaction Quality"],
  28: ["RM", "Timesheet Accuracy"], 29: ["RM", "Standup Quality"], 30: ["RM", "Proactive Communication"],
  31: ["RM", "Sprint Velocity"], 32: ["RM", "RM Check-in Responsiveness"], 33: ["RM", "Interview Participation"],
  34: ["RM", "Interview Quality Score"], 35: ["RM", "Bench Responsibility"],
};
const CATEGORIES = ["HR", "BUDDY", "RM"];

export default function BuddyProgramScreen() {
  const { recordId } = useParams();
  const [record, setRecord] = useState(null);
  const [scorecard, setScorecard] = useState(null);
  const [canExtend, setCanExtend] = useState(true);
  const [week, setWeek] = useState(1);
  const [scores, setScores] = useState({});
  const [decisionNotes, setDecisionNotes] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [r, sc, ce] = await Promise.all([
        getBuddyProgramRecord(recordId), getScorecard(recordId), getCanExtend(recordId),
      ]);
      setRecord(r);
      setScorecard(sc);
      setCanExtend(ce.can_extend);
    } catch (err) {
      toast.error("Could not load buddy program record.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [recordId]);

  const setScore = (kpiNumber, value) => {
    setScores({ ...scores, [kpiNumber]: Number(value) });
  };

  const handleSubmitScores = async () => {
    const entries = Object.entries(scores).filter(([, v]) => v >= 1 && v <= 5);
    if (entries.length === 0) return;
    try {
      await submitWeeklyScores(recordId, week, Object.fromEntries(entries));
      toast.success(`Week ${week} scores submitted.`);
      setScores({});
      load();
    } catch (err) {
      toast.error(err.message || "Could not submit scores.");
    }
  };

  const handleDecision = async (action) => {
    try {
      if (action === "graduate") await graduateEmployee(recordId, decisionNotes || null);
      else if (action === "extend") await extendProgram(recordId, decisionNotes);
      else await exitProgram(recordId, decisionNotes || null);
      toast.success(`Decision recorded: ${action}.`);
      setDecisionNotes("");
      load();
    } catch (err) {
      toast.error(err.message || "Could not record decision.");
    }
  };

  if (loading || !record) return <div className="p-6 text-sm text-gray-500">Loading...</div>;

  const decidable = record.status === "IN_PROGRESS" || record.status === "EXTENDED";

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-bx-navy">Buddy Program -- {record.employee_id}</h1>
        <p className="text-sm text-gray-500">
          {record.status} -- started {record.program_start_date}, expected end {record.expected_end_date}
          {record.extension_count > 0 ? ` (extended ${record.extension_count}x)` : ""}
        </p>
      </div>

      <Card title="Weekly KPI Scoring" subtitle="Submit scores 1-5 for your category's KPIs -- a week only counts once all 35 are in.">
        <div className="mb-3 flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-700">Week</span>
          {[1, 2, 3, 4].map((w) => (
            <button
              key={w}
              className={`px-2.5 py-1 rounded text-xs font-medium ${week === w ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}
              onClick={() => setWeek(w)}
            >
              {w}
            </button>
          ))}
        </div>
        {CATEGORIES.map((cat) => (
          <div key={cat} className="mb-4">
            <div className="text-xs font-semibold uppercase text-gray-500 mb-1">{cat}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(KPI_DEFINITIONS).filter(([, [c]]) => c === cat).map(([num, [, name]]) => (
                <div key={num} className="flex items-center justify-between text-sm py-1 border-b border-gray-100">
                  <span className="text-gray-700">{name}</span>
                  <select
                    className="border border-gray-300 rounded px-2 py-1 text-xs"
                    value={scores[num] || ""}
                    onChange={(e) => setScore(num, e.target.value)}
                  >
                    <option value="">--</option>
                    {[1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>
        ))}
        <Button onClick={handleSubmitScores}>Submit Week {week} Scores</Button>
      </Card>

      <Card title="Day-30 Scorecard" subtitle={`Complete weeks: ${scorecard.complete_weeks.join(", ") || "none yet"}`}>
        <div className="grid grid-cols-3 gap-3 mb-3">
          {CATEGORIES.map((cat) => (
            <div key={cat} className="rounded-lg border border-gray-200 p-3 text-center">
              <div className="text-xs text-gray-500">{cat}</div>
              <div className="text-lg font-semibold text-gray-900">{scorecard.category_averages[cat] ?? "--"}</div>
            </div>
          ))}
        </div>
        <p className="text-sm text-gray-700">
          Weighted overall: <span className="font-semibold">{scorecard.weighted_overall_score ?? "not yet computable"}</span>
          {scorecard.trajectory ? ` -- trajectory: ${scorecard.trajectory}` : ""}
        </p>
      </Card>

      {decidable && (
        <Card title="BU Head Decision" subtitle="Graduate, Extend 15 days, or Exit -- a real, human, consequential decision.">
          <TextArea label="Notes (required for Extend, min 50 chars)" value={decisionNotes} onChange={setDecisionNotes} rows={3} />
          <div className="flex gap-2 mt-3">
            <Button onClick={() => handleDecision("graduate")}>Graduate</Button>
            {canExtend && <Button variant="secondary" onClick={() => handleDecision("extend")}>Extend 15 Days</Button>}
            <Button variant="ghost" onClick={() => handleDecision("exit")}>Exit</Button>
          </div>
          {!canExtend && <p className="text-xs text-amber-600 mt-2">Max extensions used -- this review is Graduate or Exit only.</p>}
        </Card>
      )}
    </div>
  );
}
