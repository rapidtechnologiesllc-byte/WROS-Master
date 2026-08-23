import { useEffect, useState } from "react"
import { toast } from "react-toastify"
import { Target, Edit2, Save, X, AlertCircle, Loader } from "lucide-react"
import { Card, Button, Input } from "../components/ui"
import { apiRequest } from "../services/api"

/**
 * Goals Management Screen
 *
 * Allows admins/partners to set annual targets for Flash validation.
 * Flash validates all reporting against these goals.
 *
 * Goals hierarchy:
 * - Annual Goal (e.g., 100 hires, 500 commits, $5M revenue)
 * - Q1-Q4 breakdown (25% each, typically)
 * - Monthly breakdown (1/12 of annual)
 * - Weekly breakdown (1/52 of annual)
 * - Daily breakdown (1/365 of annual) - calculated automatically
 */

const GOAL_DEFINITIONS = [
  {
    id: "tech_leads",
    department: "Engineering",
    metric: "commits",
    description: "Source code commits per developer",
    defaultAnnual: 500,
    unit: "commits",
    role: "TECH_LEAD"
  },
  {
    id: "workforce_ops",
    department: "Workforce Operations",
    metric: "hires",
    description: "New hires brought on board",
    defaultAnnual: 100,
    unit: "hires",
    role: "RECRUITER"
  },
  {
    id: "sales",
    department: "Sales",
    metric: "revenue",
    description: "Annual revenue target",
    defaultAnnual: 15000000, // $15M
    unit: "$",
    role: "SALES_REP"
  },
  {
    id: "partner",
    department: "Partner Operations",
    metric: "partner_revenue",
    description: "Annual revenue per partner",
    defaultAnnual: 5000000, // $5M
    unit: "$",
    role: "PARTNER"
  },
  {
    id: "bu_head",
    department: "Business Unit",
    metric: "bu_revenue",
    description: "Annual revenue per BU",
    defaultAnnual: 1000000, // $1M
    unit: "$",
    role: "BU_HEAD"
  },
  {
    id: "delivery",
    department: "Delivery",
    metric: "delivery_rate",
    description: "On-time delivery percentage",
    defaultAnnual: 95, // 95% on-time
    unit: "%",
    role: "MANAGER"
  }
]

const calculateBreakdown = (annual) => {
  const quarterly = annual / 4
  const monthly = annual / 12
  const weekly = annual / 52
  const daily = annual / 365

  return {
    annual: Math.round(annual),
    quarterly: Math.round(quarterly * 100) / 100,
    monthly: Math.round(monthly * 100) / 100,
    weekly: Math.round(weekly * 100) / 100,
    daily: Math.round(daily * 10000) / 10000
  }
}

function GoalCard({ goal, onEdit }) {
  const [isEditing, setIsEditing] = useState(false)
  const [value, setValue] = useState(goal.defaultAnnual)

  const breakdown = calculateBreakdown(value)

  const handleSave = async () => {
    try {
      // TODO: Call backend to save goal
      // await updateGoal(goal.id, value)
      toast.success(`${goal.department} goal updated to ${value} ${goal.unit}`)
      setIsEditing(false)
      onEdit?.(goal.id, value)
    } catch (err) {
      toast.error("Failed to save goal")
    }
  }

  const handleCancel = () => {
    setValue(goal.defaultAnnual)
    setIsEditing(false)
  }

  return (
    <Card className="p-4 mb-4 border border-gray-200 hover:border-blue-300 transition">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Target size={18} className="text-blue-600" />
            <h3 className="font-semibold text-gray-900">{goal.department}</h3>
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
              {goal.role}
            </span>
          </div>
          <p className="text-sm text-gray-600">{goal.description}</p>
        </div>
        <button
          onClick={() => setIsEditing(!isEditing)}
          className="text-gray-400 hover:text-blue-600 transition"
        >
          {isEditing ? <X size={20} /> : <Edit2 size={20} />}
        </button>
      </div>

      {isEditing ? (
        <div className="bg-blue-50 p-3 rounded-lg mb-3">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Annual Target ({goal.unit})
          </label>
          <div className="flex gap-2 items-end">
            <Input
              type="number"
              value={value}
              onChange={(e) => setValue(parseFloat(e.target.value))}
              className="flex-1"
              min="0"
              step="1"
            />
            <Button onClick={handleSave} className="bg-blue-600 text-white">
              <Save size={16} className="mr-1" />
              Save
            </Button>
            <Button onClick={handleCancel} className="bg-gray-300 text-gray-700">
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-2 text-center text-sm">
          <div className="bg-gradient-to-b from-blue-50 to-blue-100 p-2 rounded">
            <div className="text-xs text-gray-600">Annual</div>
            <div className="font-semibold text-blue-900">
              {breakdown.annual.toLocaleString()} {goal.unit}
            </div>
          </div>
          <div className="bg-gradient-to-b from-purple-50 to-purple-100 p-2 rounded">
            <div className="text-xs text-gray-600">Quarterly</div>
            <div className="font-semibold text-purple-900">
              {breakdown.quarterly.toLocaleString()} {goal.unit}
            </div>
          </div>
          <div className="bg-gradient-to-b from-green-50 to-green-100 p-2 rounded">
            <div className="text-xs text-gray-600">Monthly</div>
            <div className="font-semibold text-green-900">
              {breakdown.monthly.toLocaleString()} {goal.unit}
            </div>
          </div>
          <div className="bg-gradient-to-b from-orange-50 to-orange-100 p-2 rounded">
            <div className="text-xs text-gray-600">Weekly</div>
            <div className="font-semibold text-orange-900">
              {breakdown.weekly.toLocaleString()} {goal.unit}
            </div>
          </div>
          <div className="bg-gradient-to-b from-red-50 to-red-100 p-2 rounded">
            <div className="text-xs text-gray-600">Daily</div>
            <div className="font-semibold text-red-900">
              {breakdown.daily.toLocaleString()} {goal.unit}
            </div>
          </div>
        </div>
      )}

      <div className="mt-3 p-2 bg-blue-50 border-l-4 border-blue-400 text-xs text-blue-700">
        <strong>Flash Validation:</strong> Reports compared against {goal.department} target.
        Behind at any level = coaching required before submitting.
      </div>
    </Card>
  )
}

export default function GoalsManagementScreen() {
  const [goals, setGoals] = useState(GOAL_DEFINITIONS)
  const [cascadedGoals, setCascadedGoals] = useState([])
  const [filter, setFilter] = useState("all")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(null)

  useEffect(() => {
    // Fetch cascaded goals from backend on load
    const fetchGoals = async () => {
      try {
        setLoading(true)

        // Fetch cascaded goals for current user's department
        const response = await apiRequest("GET", "/goals/cascaded?year=2026")

        if (response.cascaded_goals && response.cascaded_goals.length > 0) {
          // Map cascaded goals to frontend format
          const mappedGoals = response.cascaded_goals.map(cg => ({
            id: cg.cascaded_goal_id,
            department: cg.cascaded_to_department,
            metric: cg.strategic_goal_name?.toLowerCase().replace(/ /g, "_"),
            description: `Target: ${cg.annual.toLocaleString()} ${cg.unit}`,
            defaultAnnual: cg.annual,
            unit: cg.unit,
            role: cg.cascaded_to_department.toUpperCase(),
            cascadedGoalId: cg.cascaded_goal_id,
            status: cg.status,
            variance: cg.variance,
            current: cg.current_progress
          }))
          setGoals(mappedGoals)
          setCascadedGoals(response.cascaded_goals)
        } else {
          // No cascaded goals, use defaults
          setCascadedGoals([])
        }
      } catch (err) {
        console.error("Failed to fetch goals:", err)
        toast.error("Failed to load goals from backend")
      } finally {
        setLoading(false)
      }
    }

    fetchGoals()
  }, [])

  const handleGoalUpdate = (id, value) => {
    setGoals(goals.map(g =>
      g.id === id ? { ...g, defaultAnnual: value } : g
    ))
  }

  const filteredGoals = filter === "all"
    ? goals
    : goals.filter(g => g.role?.toLowerCase().includes(filter))

  if (loading) {
    return (
      <div className="container mx-auto p-6 bg-white min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Loading annual goals...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 bg-white min-h-screen">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Target size={32} className="text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Annual Goals</h1>
          {cascadedGoals.length > 0 && (
            <span className="text-sm bg-green-100 text-green-800 px-3 py-1 rounded-full font-medium">
              {cascadedGoals.length} Cascaded
            </span>
          )}
        </div>
        <p className="text-gray-600">
          Set annual targets for each department. Flash validates all reports against these goals.
        </p>
      </div>

      {/* Alert: Goals are critical for Flash validation */}
      <div className="mb-6 p-4 bg-yellow-50 border border-yellow-300 rounded-lg flex gap-3">
        <AlertCircle size={20} className="text-yellow-600 flex-shrink-0 mt-0.5" />
        <div>
          <strong className="text-yellow-900">Flash Validation Requires Goals</strong>
          <p className="text-sm text-yellow-800 mt-1">
            Flash orchestrator compares weekly reports against annual targets defined here.
            If a role's goal is not set, Flash validation is skipped for that team.
          </p>
        </div>
      </div>

      {/* Goal Cascade Explanation */}
      <Card className="p-4 mb-6 bg-gradient-to-r from-blue-50 to-purple-50">
        <h2 className="font-semibold text-gray-900 mb-3">How Goal Cascading Works</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <strong className="text-blue-700">Example: 100 Hires Goal</strong>
            <ul className="mt-2 space-y-1 text-gray-700">
              <li>• Annual: 100 hires</li>
              <li>• Quarterly: 25 hires each</li>
              <li>• Monthly: 8.3 hires</li>
              <li>• Weekly: 1.9 hires</li>
              <li>• Daily: 0.27 hires</li>
            </ul>
          </div>
          <div>
            <strong className="text-purple-700">Flash Feedback Example</strong>
            <ul className="mt-2 space-y-1 text-gray-700">
              <li>• Week 20: Expected 38 hires, actual 12</li>
              <li>• Status: CRITICAL_LAG (26 behind pace)</li>
              <li>• Q1 target at risk (need 13 more by week 13)</li>
              <li>• This month cannot recover alone</li>
              <li>• Escalation: Manager discussion required</li>
            </ul>
          </div>
        </div>
      </Card>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6 border-b border-gray-200">
        {["all", "TECH_LEAD", "RECRUITER", "PARTNER", "BU_HEAD"].map(role => (
          <button
            key={role}
            onClick={() => setFilter(role)}
            className={`px-4 py-2 font-medium transition ${
              filter === role
                ? "text-blue-600 border-b-2 border-blue-600"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {role === "all" ? "All Departments" : role.replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Goals Cards */}
      <div className="mb-6">
        {filteredGoals.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No goals to display</p>
        ) : (
          filteredGoals.map(goal => (
            <GoalCard
              key={goal.id}
              goal={goal}
              onEdit={handleGoalUpdate}
            />
          ))
        )}
      </div>

      {/* Implementation Notes */}
      <Card className="p-4 bg-gray-50">
        <h3 className="font-semibold text-gray-900 mb-2">Backend Integration</h3>
        <ul className="text-sm text-gray-700 space-y-1">
          <li>• GET /goals - Fetch all annual goals</li>
          <li>• PUT /goals/:id - Update a goal's annual target</li>
          <li>• POST /goals - Create new goal for a department</li>
          <li>• These goals feed Flash validation engine at /agents/*/validate-progress</li>
        </ul>
      </Card>
    </div>
  )
}
