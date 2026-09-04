import { useEffect, useState } from "react";
import { Button, Card, Badge } from "./ui";
import { AlertCircle, CheckCircle, Clock } from "lucide-react";
import {
  checkL1ToL2Trigger,
  getPanelistSuggestions,
  checkAffordability,
  createL2Panel,
} from "../services/api/hiringWorkflow";
import { toast } from "react-toastify";
import ScreenErrorDisplay from "./ScreenErrorDisplay";

export default function L1ToL2WorkflowPanel({ l1InterviewId, demandId, submissionId, onL2Created }) {
  const [checking, setChecking] = useState(true);
  const [triggerResult, setTriggerResult] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [affordability, setAffordability] = useState(null);
  const [selectedPanelists, setSelectedPanelists] = useState([]);
  const [creating, setCreating] = useState(false);
  const [step, setStep] = useState("trigger"); // trigger → panelist → create
  const [screenError, setScreenError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        setChecking(true);
        const trigger = await checkL1ToL2Trigger(l1InterviewId);
        setTriggerResult(trigger);

        if (trigger?.should_trigger_l2) {
          // Auto-triggered: show panelist suggestions
          const sug = await getPanelistSuggestions(demandId, "L2");
          setSuggestions(sug || []);

          // Show affordability
          const aff = await checkAffordability(submissionId);
          setAffordability(aff);
        }
      } catch (err) {
        setScreenError("Failed to check L1→L2 trigger: " + err.message);
      } finally {
        setChecking(false);
      }
    };

    load();
  }, [l1InterviewId, demandId, submissionId]);

  const handleSelectPanelist = (empId) => {
    setSelectedPanelists((prev) =>
      prev.includes(empId) ? prev.filter((id) => id !== empId) : [...prev, empId]
    );
  };

  const handleCreateL2 = async () => {
    if (selectedPanelists.length === 0) {
      setScreenError("Select at least one panelist for L2 interview.");
      return;
    }

    setCreating(true);
    try {
      const result = await createL2Panel(demandId, submissionId, selectedPanelists);
      toast.success("L2 interview panel created successfully.");
      onL2Created?.(result);
    } catch (err) {
      setScreenError("Failed to create L2 panel: " + err.message);
    } finally {
      setCreating(false);
    }
  };

  if (checking) {
    return (
      <>
        <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
        <Card>Checking if L2 interview should auto-trigger...</Card>
      </>
    );
  }

  if (!triggerResult) {
    return (
      <>
        <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
        <Card className="bg-amber-50 border-amber-200">Could not check L1→L2 trigger.</Card>
      </>
    );
  }

  if (!triggerResult.should_trigger_l2) {
    return (
      <>
        <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
        <Card className="bg-yellow-50 border-yellow-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-yellow-900">Manual HM Decision Required</div>
              <div className="text-sm text-yellow-800 mt-1">
                Negative vote detected ({triggerResult.negative_votes} no-hire, {triggerResult.positive_votes} hire).
                Hiring Manager must decide whether to advance to L2.
              </div>
            </div>
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
      <Card title="L2 Interview Auto-Trigger" className="border-green-200 bg-green-50">
      <div className="space-y-4">
        {/* Trigger Status */}
        <div className="flex items-center gap-2">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <div className="text-sm text-green-900">
            L2 interview auto-triggered ({triggerResult.positive_votes} hire, {triggerResult.negative_votes} no-hire)
          </div>
        </div>

        {/* Affordability Check */}
        {affordability && (
          <div className={`p-3 rounded-lg border ${affordability.affordable ? "bg-green-100 border-green-300" : "bg-red-100 border-red-300"}`}>
            <div className="font-semibold text-sm">
              Affordability: {affordability.affordable ? "✓ APPROVE" : "✗ DECLINE"}
            </div>
            <div className="text-xs text-gray-700 mt-1">
              Fully loaded cost: ${(affordability.fully_loaded_cost_usd / 100).toLocaleString()}
              <br />
              BU margin available: ${(affordability.bu_margin_available_usd / 100).toLocaleString()}
            </div>
          </div>
        )}

        {/* Panelist Selection */}
        {step === "panelist" || (step === "trigger" && suggestions.length > 0) && (
          <div>
            <div className="text-sm font-semibold text-gray-900 mb-2">Select L2 Panelists</div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {suggestions.map((emp) => (
                <label key={emp.employee_id} className="flex items-start gap-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="checkbox"
                    checked={selectedPanelists.includes(emp.employee_id)}
                    onChange={() => handleSelectPanelist(emp.employee_id)}
                    className="mt-1"
                  />
                  <div className="flex-1 text-sm">
                    <div className="font-semibold text-gray-900">{emp.employee_name}</div>
                    <div className="text-xs text-gray-600">
                      Skill match: {(emp.skill_match_score * 100).toFixed(0)}% ·
                      Interview load: {emp.interview_load} ·
                      Score: {emp.overall_score}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="flex justify-end gap-2 pt-2 border-t">
          <Button
            disabled={creating || selectedPanelists.length === 0}
            onClick={handleCreateL2}
            variant="primary"
          >
            {creating ? "Creating L2 Panel..." : "Create L2 Interview Panel"}
          </Button>
        </div>
      </div>
      </Card>
    </>
  );
}
