import { useEffect, useState } from "react"
import { toast } from "react-toastify"
import { Target, TrendingUp, Users, DollarSign, Zap } from "lucide-react"
import { Card, Button, Input } from "../components/ui"

/**
 * CEO Goals Setting Screen
 *
 * CEO sets ONE strategic goal.
 * System AUTOMATICALLY cascades to all departments.
 *
 * Instead of 6 people manually setting targets,
 * CEO sets constraints and Workforce Ops, Sales, etc.
 * automatically inherit their piece of the goal.
 *
 * Example:
 *   CEO: "I want 150 consultants by EOY"
 *   System Auto-Sets:
 *     - Workforce Ops: 150 hires/year
 *     - Sales: Revenue targets
 *     - Partners: $5M per partner annual
 *     - BU Heads: Revenue per BU
 */

const CEO_STRATEGIC_GOALS = [
  {
    id: "consultants",
    title: "Total Consultants",
    description: "End-of-year headcount target",
    icon: Users,
    current: 87,
    target: 150,
    unit: "people",
    cascadeTo: ["workforce_ops"],
    formula: "Each hire counts toward total"
  },
  {
    id: "annual_revenue",
    title: "Annual Revenue",
    description: "Total company revenue target",
    icon: DollarSign,
    current: 3200000,
    target: 15000000,
    unit: "$",
    cascadeTo: ["partner", "bu_head", "sales"],
    formula: "Divide by number of Partners/BUs"
  },
  {
    id: "managed_services_logos",
    title: "Managed Services Logos",
    description: "Direct managed services customers",
    icon: Zap,
    current: 2,
    target: 5,
    unit: "logos",
    cascadeTo: ["sales"],
    formula: "Sales targets 5 logos"
  },
  {
    id: "guidewire_partnership",
    title: "Guidewire Partnership",
    description: "Strategic partnership status",
    icon: Target,
    current: 1,
    target: 1,
    unit: "partnership",
    cascadeTo: ["partner"],
    formula: "Executive focus - not cascaded"
  }
]

function CascadeVisualization({ goal }) {
  const progress = (goal.current / goal.target) * 100

  // Calculate cascades
  const cascades = {}
  if (goal.cascadeTo.includes("workforce_ops")) {
    cascades["Workforce Ops"] = {
      annual: goal.target,
      quarterly: (goal.target / 4).toFixed(1),
      monthly: (goal.target / 12).toFixed(1),
      weekly: (goal.target / 52).toFixed(1),
      daily: (goal.target / 365).toFixed(2),
      current: goal.current
    }
  }
  if (goal.cascadeTo.includes("partner")) {
    const perPartner = (goal.target / 3).toFixed(0) // Assume 3 partners
    cascades["Per Partner"] = {
      annual: perPartner,
      quarterly: (perPartner / 4).toFixed(1),
      monthly: (perPartner / 12).toFixed(1),
      weekly: (perPartner / 52).toFixed(1),
      daily: (perPartner / 365).toFixed(2)
    }
  }
  if (goal.cascadeTo.includes("sales")) {
    cascades["Sales Team"] = {
      annual: goal.target,
      quarterly: (goal.target / 4).toFixed(1),
      monthly: (goal.target / 12).toFixed(1),
      weekly: (goal.target / 52).toFixed(1),
      daily: (goal.target / 365).toFixed(2)
    }
  }

  return (
    <div className="space-y-4">
      {/* Progress Bar */}
      <div>
        <div className="flex justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            Progress: {goal.current.toLocaleString()} / {goal.target.toLocaleString()} {goal.unit}
          </span>
          <span className="text-sm font-medium text-blue-600">{progress.toFixed(0)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      </div>

      {/* Cascade breakdown */}
      {Object.entries(cascades).map(([dept, breakdown]) => (
        <div key={dept} className="bg-gradient-to-r from-blue-50 to-purple-50 p-3 rounded-lg">
          <h4 className="font-semibold text-gray-900 mb-2">{dept}</h4>
          <div className="grid grid-cols-5 gap-2 text-xs">
            <div className="bg-white p-2 rounded border border-blue-100">
              <div className="text-gray-600 font-medium">Annual</div>
              <div className="text-blue-700 font-bold">{breakdown.annual}</div>
            </div>
            <div className="bg-white p-2 rounded border border-purple-100">
              <div className="text-gray-600 font-medium">Q</div>
              <div className="text-purple-700 font-bold">{breakdown.quarterly}</div>
            </div>
            <div className="bg-white p-2 rounded border border-green-100">
              <div className="text-gray-600 font-medium">M</div>
              <div className="text-green-700 font-bold">{breakdown.monthly}</div>
            </div>
            <div className="bg-white p-2 rounded border border-orange-100">
              <div className="text-gray-600 font-medium">W</div>
              <div className="text-orange-700 font-bold">{breakdown.weekly}</div>
            </div>
            <div className="bg-white p-2 rounded border border-red-100">
              <div className="text-gray-600 font-medium">D</div>
              <div className="text-red-700 font-bold">{breakdown.daily}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function CEOGoalsSettingScreen() {
  const [goals, setGoals] = useState(CEO_STRATEGIC_GOALS)
  const [editingId, setEditingId] = useState(null)
  const [editValue, setEditValue] = useState(0)

  const handleEdit = (id, currentTarget) => {
    setEditingId(id)
    setEditValue(currentTarget)
  }

  const handleSave = async (id) => {
    try {
      // TODO: Call backend to save CEO goal and cascade to all departments
      // await updateCEOGoal(id, editValue)
      // This would auto-update all department targets
      setGoals(goals.map(g =>
        g.id === id ? { ...g, target: editValue } : g
      ))
      toast.success("Goal updated. Cascading to all departments...")
      setEditingId(null)
    } catch (err) {
      toast.error("Failed to save goal")
    }
  }

  const handleCancel = () => {
    setEditingId(null)
  }

  return (
    <div className="container mx-auto p-6 bg-white min-h-screen">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Target size={32} className="text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Strategic Goals</h1>
          <span className="text-sm bg-blue-100 text-blue-800 px-3 py-1 rounded-full font-medium">CEO Level</span>
        </div>
        <p className="text-gray-600 max-w-2xl">
          Set strategic targets here. System automatically cascades to all departments.
          Workforce Ops, Sales, Partners, and BU Heads inherit their piece of each goal.
        </p>
      </div>

      {/* Key Concept */}
      <Card className="p-4 mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200">
        <h2 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Zap size={20} className="text-blue-600" />
          How This Works
        </h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <strong className="text-blue-700">You Set (CEO Level):</strong>
            <ul className="mt-2 space-y-1 text-gray-700">
              <li>• 150 total consultants by EOY</li>
              <li>• $15M annual revenue</li>
              <li>• 5 managed services logos</li>
              <li>• Guidewire partnership</li>
            </ul>
          </div>
          <div>
            <strong className="text-indigo-700">System Auto-Cascades:</strong>
            <ul className="mt-2 space-y-1 text-gray-700">
              <li>• Workforce Ops: 150 hires (12.5/month)</li>
              <li>• Sales: $15M revenue ($1.25M/month)</li>
              <li>• Partners: $5M each ($417K/month)</li>
              <li>• All roles see their piece of the goal</li>
            </ul>
          </div>
        </div>
      </Card>

      {/* Current Status */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">2026 Strategic Targets</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {goals.map(goal => {
            const Icon = goal.icon
            const isEditing = editingId === goal.id

            return (
              <Card key={goal.id} className="p-4 border border-gray-200">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-start gap-3">
                    <Icon size={24} className="text-blue-600 mt-1" />
                    <div>
                      <h3 className="font-semibold text-gray-900">{goal.title}</h3>
                      <p className="text-sm text-gray-600">{goal.description}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => isEditing ? handleCancel() : handleEdit(goal.id, goal.target)}
                    className="text-gray-400 hover:text-blue-600 transition font-medium text-sm"
                  >
                    {isEditing ? "Cancel" : "Edit"}
                  </button>
                </div>

                {isEditing ? (
                  <div className="bg-blue-50 p-3 rounded-lg mb-3">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Target ({goal.unit})
                    </label>
                    <div className="flex gap-2">
                      <Input
                        type="number"
                        value={editValue}
                        onChange={(e) => setEditValue(parseFloat(e.target.value))}
                        className="flex-1"
                        min="0"
                      />
                      <Button
                        onClick={() => handleSave(goal.id)}
                        className="bg-blue-600 text-white whitespace-nowrap"
                      >
                        Save & Cascade
                      </Button>
                    </div>
                  </div>
                ) : (
                  <CascadeVisualization goal={goal} />
                )}
              </Card>
            )
          })}
        </div>
      </div>

      {/* Flash Validation Impact */}
      <Card className="p-4 bg-purple-50 border border-purple-200">
        <h3 className="font-semibold text-gray-900 mb-2">Flash Validation Impact</h3>
        <p className="text-sm text-gray-700 mb-3">
          When you update a goal here, every employee in the cascaded department sees their personal pace against this target:
        </p>
        <div className="bg-white p-3 rounded border-l-4 border-purple-400 text-sm text-gray-700">
          <strong>Example:</strong> You set "150 consultants" target.
          <br />
          Workforce Ops sees: "Annual goal: 150 hires. You're at 87. Week 33 pace: need 2.4/week. Currently at 1.5/week."
          <br />
          Flash: "SLIGHT_LAG - Need 0.9 more per week to stay on pace."
        </div>
      </Card>

      {/* Backend Integration Notes */}
      <Card className="p-4 bg-gray-50 mt-6">
        <h3 className="font-semibold text-gray-900 mb-2">Backend Integration Required</h3>
        <ul className="text-sm text-gray-700 space-y-2">
          <li>✓ <strong>POST /goals/cascade</strong> - CEO sets goal, auto-cascades to departments</li>
          <li>✓ <strong>GET /goals/cascade/:ceo_goal_id</strong> - See all cascaded department targets</li>
          <li>✓ <strong>GET /departments/:dept_id/goal</strong> - Department sees their cascaded target</li>
          <li>✓ <strong>PUT /goals/:id</strong> - Update CEO goal, re-cascade to all</li>
          <li>✓ <strong>Flash validation</strong> - Uses cascaded goal, not manually set target</li>
        </ul>
      </Card>
    </div>
  )
}
