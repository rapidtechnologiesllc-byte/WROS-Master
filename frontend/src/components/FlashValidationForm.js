import { useState } from "react"
import { Card, Button } from "./ui"
import { AlertCircle, CheckCircle, AlertTriangle, TrendingUp, Clock, Calendar, Week } from "lucide-react"

/**
 * Flash Validation Form Component
 *
 * Displays Flash orchestrator's progress validation and coaching.
 *
 * States:
 * - ON_TRACK: Progress within 5% of expected. Submit button enabled.
 * - SLIGHT_LAG: 10% behind pace. Requires confirmation. Submit blocked until addressed.
 * - CRITICAL_LAG: >10% behind pace. Escalation required. Submit disabled.
 * - AHEAD: Exceeding pace. Encouragement. Submit enabled.
 */

const StatusConfig = {
  ON_TRACK: {
    color: "green",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
    textColor: "text-green-800",
    icon: CheckCircle,
    label: "On Track"
  },
  SLIGHT_LAG: {
    color: "yellow",
    bgColor: "bg-yellow-50",
    borderColor: "border-yellow-200",
    textColor: "text-yellow-800",
    icon: AlertTriangle,
    label: "Slight Lag"
  },
  CRITICAL_LAG: {
    color: "red",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
    textColor: "text-red-800",
    icon: AlertCircle,
    label: "Critical Lag"
  },
  AHEAD: {
    color: "blue",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
    textColor: "text-blue-800",
    icon: TrendingUp,
    label: "Ahead of Pace"
  }
}

function ProgressBar({ label, expected, actual, unit }) {
  const percentage = (actual / expected) * 100
  const isAhead = actual >= expected

  return (
    <div className="mb-4">
      <div className="flex justify-between items-baseline mb-2">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className="text-sm text-gray-600">
          {actual.toLocaleString()} / {expected.toLocaleString()} {unit}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${
            isAhead ? "bg-green-500" : percentage >= 75 ? "bg-yellow-500" : "bg-red-500"
          }`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 mt-1">
        {percentage >= 100
          ? `+${Math.round(percentage - 100)}% ahead of pace`
          : `${Math.round(100 - percentage)}% behind pace`}
      </p>
    </div>
  )
}

function TimeframeBreakdown({ timeframes }) {
  return (
    <div className="grid grid-cols-5 gap-2 mb-6">
      <div className="bg-gradient-to-b from-blue-50 to-blue-100 p-3 rounded border border-blue-200">
        <div className="flex items-center gap-1 mb-1">
          <Calendar size={14} className="text-blue-600" />
          <span className="text-xs font-semibold text-blue-900">Annual</span>
        </div>
        <div className="text-lg font-bold text-blue-900">
          {timeframes.annual?.toLocaleString() || "—"}
        </div>
      </div>

      <div className="bg-gradient-to-b from-purple-50 to-purple-100 p-3 rounded border border-purple-200">
        <div className="text-xs font-semibold text-purple-900 mb-1">Quarterly</div>
        <div className="text-lg font-bold text-purple-900">
          {(timeframes.annual / 4)?.toLocaleString() || "—"}
        </div>
      </div>

      <div className="bg-gradient-to-b from-green-50 to-green-100 p-3 rounded border border-green-200">
        <div className="text-xs font-semibold text-green-900 mb-1">Monthly</div>
        <div className="text-lg font-bold text-green-900">
          {(timeframes.annual / 12)?.toLocaleString() || "—"}
        </div>
      </div>

      <div className="bg-gradient-to-b from-orange-50 to-orange-100 p-3 rounded border border-orange-200">
        <div className="flex items-center gap-1 mb-1">
          <Week size={14} className="text-orange-600" />
          <span className="text-xs font-semibold text-orange-900">Weekly</span>
        </div>
        <div className="text-lg font-bold text-orange-900">
          {(timeframes.annual / 52)?.toFixed(1) || "—"}
        </div>
      </div>

      <div className="bg-gradient-to-b from-red-50 to-red-100 p-3 rounded border border-red-200">
        <div className="flex items-center gap-1 mb-1">
          <Clock size={14} className="text-red-600" />
          <span className="text-xs font-semibold text-red-900">Daily</span>
        </div>
        <div className="text-lg font-bold text-red-900">
          {(timeframes.annual / 365)?.toFixed(2) || "—"}
        </div>
      </div>
    </div>
  )
}

export default function FlashValidationForm({
  validation,
  onSubmit,
  onCancel,
  loading = false
}) {
  const [confirmed, setConfirmed] = useState(false)
  const [confirmationComment, setConfirmationComment] = useState("")

  if (!validation) {
    return null
  }

  const config = StatusConfig[validation.status] || StatusConfig.ON_TRACK
  const Icon = config.icon
  const requiresConfirmation =
    validation.status === "SLIGHT_LAG" || validation.status === "CRITICAL_LAG"
  const canSubmit =
    validation.submit_enabled &&
    (!requiresConfirmation || (confirmed && confirmationComment.trim()))

  const handleSubmit = () => {
    if (onSubmit) {
      onSubmit({
        confirmed,
        confirmation_comment: confirmationComment
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* Status Header */}
      <div className={`${config.bgColor} border-l-4 ${config.borderColor} p-4 rounded`}>
        <div className="flex items-start gap-3">
          <Icon size={24} className={`text-${config.color}-600 flex-shrink-0 mt-1`} />
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className={`text-lg font-bold ${config.textColor}`}>
                {config.label}
              </h3>
              <span className={`text-xs font-medium px-3 py-1 rounded-full bg-${config.color}-100 text-${config.color}-800`}>
                {validation.status}
              </span>
            </div>
            <p className={`text-sm ${config.textColor}`}>
              {validation.annual_goal}
            </p>
          </div>
        </div>
      </div>

      {/* Goal Breakdown */}
      <Card className="p-4">
        <h4 className="font-semibold text-gray-900 mb-4">Pace Breakdown</h4>
        <TimeframeBreakdown timeframes={validation} />
      </Card>

      {/* Progress Analysis */}
      <Card className="p-4">
        <h4 className="font-semibold text-gray-900 mb-4">Progress Analysis</h4>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-xs text-gray-600 mb-1">Expected by Now</p>
            <p className="text-2xl font-bold text-gray-900">
              {validation.expected_pace?.toLocaleString() || "—"}
            </p>
          </div>

          <div className="bg-gray-50 p-3 rounded">
            <p className="text-xs text-gray-600 mb-1">Actual Progress</p>
            <p className="text-2xl font-bold text-gray-900">
              {validation.actual_progress?.toLocaleString() || "—"}
            </p>
          </div>

          <div className={`bg-${config.color}-50 p-3 rounded border border-${config.color}-200`}>
            <p className={`text-xs text-${config.color}-700 mb-1`}>Variance</p>
            <p className={`text-2xl font-bold text-${config.color}-900`}>
              {validation.pace_variance > 0 ? "+" : ""}
              {validation.pace_variance?.toLocaleString() || "—"}
              {validation.variance_pct && (
                <span className="text-sm ml-1">({validation.variance_pct.toFixed(1)}%)</span>
              )}
            </p>
          </div>
        </div>

        <ProgressBar
          label="Overall Progress"
          expected={validation.expected_pace || 1}
          actual={validation.actual_progress || 0}
          unit=""
        />
      </Card>

      {/* Flash Feedback */}
      <Card className="p-4 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200">
        <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <TrendingUp size={18} className="text-purple-600" />
          Flash Coaching
        </h4>
        <p className="text-sm text-gray-700 whitespace-pre-wrap mb-4">
          {validation.feedback}
        </p>
      </Card>

      {/* Concrete Actions */}
      {validation.concrete_actions && validation.concrete_actions.length > 0 && (
        <Card className="p-4">
          <h4 className="font-semibold text-gray-900 mb-3">Recommended Actions</h4>
          <ol className="space-y-2">
            {validation.concrete_actions.map((action, idx) => (
              <li key={idx} className="text-sm text-gray-700 flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">
                  {idx + 1}
                </span>
                <span>{action}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {/* Confirmation Gate (for SLIGHT_LAG and CRITICAL_LAG) */}
      {requiresConfirmation && (
        <Card className="p-4 bg-yellow-50 border border-yellow-200">
          <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <AlertCircle size={18} className="text-yellow-600" />
            Confirm Data Accuracy
          </h4>
          <p className="text-sm text-gray-700 mb-4">
            Your progress shows concerning variance. Before submitting, please confirm:
          </p>

          <div className="space-y-3 mb-4">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-1"
              />
              <span className="text-sm text-gray-700">
                I have reviewed the data and confirm it is accurate
              </span>
            </label>

            {confirmed && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  What's causing this variance? (required)
                </label>
                <textarea
                  value={confirmationComment}
                  onChange={(e) => setConfirmationComment(e.target.value)}
                  placeholder="Describe the factors contributing to this progress variance..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
                  rows="3"
                />
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Submit Actions */}
      <div className="flex gap-3">
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit || loading}
          className={`flex-1 ${
            canSubmit
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "bg-gray-300 text-gray-500 cursor-not-allowed"
          }`}
        >
          {loading ? "Submitting..." : "Submit Report"}
        </Button>

        {onCancel && (
          <Button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 bg-gray-200 text-gray-700 hover:bg-gray-300"
          >
            Cancel
          </Button>
        )}
      </div>

      {/* Help Text */}
      {!canSubmit && (
        <div className="text-xs text-gray-600 bg-gray-50 p-3 rounded">
          {requiresConfirmation && !confirmed
            ? "Please confirm data accuracy and address the variance to continue"
            : requiresConfirmation && confirmed && !confirmationComment.trim()
            ? "Please explain the variance before submitting"
            : validation.status === "CRITICAL_LAG"
            ? "Critical lag detected. Manager discussion required before submission."
            : "Address Flash feedback before submitting."}
        </div>
      )}
    </div>
  )
}
