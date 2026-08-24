import { useState } from "react";
import { Button, Card } from "./ui";
import { AlertTriangle } from "lucide-react";
import { recordNoShow } from "../services/api/hiringWorkflow";
import { toast } from "react-toastify";
import ScreenErrorDisplay from "./ScreenErrorDisplay";

export default function NoShowConfirmation({ interviewId, candidateName, onNoShowRecorded }) {
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [screenError, setScreenError] = useState(null);

  const handleConfirmNoShow = async () => {
    setConfirming(true);
    try {
      const result = await recordNoShow(interviewId);
      toast.success("No-show recorded. Candidate remains in pipeline for future matches.");
      setConfirmed(true);
      onNoShowRecorded?.(result);
    } catch (err) {
      setScreenError("Failed to record no-show: " + err.message);
    } finally {
      setConfirming(false);
    }
  };

  if (confirmed) {
    return (
      <>
        <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
        <Card className="bg-blue-50 border-blue-200">
          <div className="text-sm text-blue-900">
            ✓ No-show recorded for {candidateName}. Interview dropped from panelist load.
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
      <Card className="bg-amber-50 border-amber-200">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <div className="font-semibold text-amber-900">Confirm No-Show</div>
          <div className="text-sm text-amber-800 mt-1">
            {candidateName} did not appear for this interview.
            <br />
            Confirming will drop this interview from the panelist's load, but the candidate
            remains in the pool for future matching.
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <Button
              variant="ghost"
              onClick={() => {}} // Parent handles cancel
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmNoShow}
              disabled={confirming}
              variant="primary"
              className="bg-amber-600 hover:bg-amber-700"
            >
              {confirming ? "Recording..." : "Confirm No-Show"}
            </Button>
          </div>
        </div>
      </div>
      </Card>
    </>
  );
}
