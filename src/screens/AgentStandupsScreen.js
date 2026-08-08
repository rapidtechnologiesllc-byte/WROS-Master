import { useEffect, useState } from "react";
import { RefreshCw, AlertTriangle, Check, Clock, TrendingDown, TrendingUp } from "lucide-react";
import { toast } from "react-toastify";
import { Card, Button, Tabs } from "../components/ui";
import { apiRequest } from "../services/api";

export default function AgentStandupsScreen() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [agentDetails, setAgentDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackAction, setFeedbackAction] = useState("encourage");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  const loadDashboard = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiRequest("GET", "/admin/agent-standups/dashboard");
      setDashboard(res);
    } catch (err) {
      setError(err.message || "Failed to load standup dashboard");
    } finally {
      setLoading(false);
    }
  };

  const loadAgentDetails = async (agentName) => {
    setLoadingDetails(true);
    try {
      const res = await apiRequest("GET", `/admin/agent-standups/agent/${agentName}/details`);
      setAgentDetails(res);
    } catch (err) {
      toast.error(`Failed to load details for ${agentName}`);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleAgentClick = (agentName) => {
    setSelectedAgent(agentName);
    loadAgentDetails(agentName);
    setFeedbackText("");
  };

  const submitFeedback = async () => {
    if (!feedbackText.trim()) {
      toast.error("Please enter feedback");
      return;
    }
    if (!selectedAgent) {
      toast.error("No agent selected");
      return;
    }

    setSubmittingFeedback(true);
    try {
      await apiRequest("POST", `/admin/agent-standups/provide-feedback/${selectedAgent}`, {
        feedback_text: feedbackText,
        action: feedbackAction
      });
      toast.success(`Feedback sent to ${selectedAgent}`);
      setFeedbackText("");
      loadDashboard();
    } catch (err) {
      toast.error(err.message || "Failed to submit feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(loadDashboard, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  if (loading || !dashboard) {
    return (
      <Card title="Agent Standups Dashboard" subtitle="Loading...">
        <div className="py-8 text-center text-sm text-gray-500">Loading daily standups...</div>
      </Card>
    );
  }

  const { daily_standup, scrum_of_scrums, weekly_feedback } = dashboard;

  const getStatusColor = (status) => {
    const colors = {
      healthy: "bg-green-50 border-green-200",
      degraded: "bg-yellow-50 border-yellow-200",
      critical: "bg-red-50 border-red-200",
      not_running: "bg-gray-50 border-gray-200",
      on_track: "bg-green-50 border-green-200",
      forecasting_off_track: "bg-yellow-50 border-yellow-200",
      needs_action: "bg-red-50 border-red-200"
    };
    return colors[status] || "bg-white border-gray-200";
  };

  const getStatusIcon = (status) => {
    if (status === "healthy" || status === "on_track") return <Check className="h-4 w-4 text-green-600" />;
    if (status === "degraded" || status === "forecasting_off_track") return <TrendingDown className="h-4 w-4 text-yellow-600" />;
    if (status === "critical" || status === "needs_action") return <AlertTriangle className="h-4 w-4 text-red-600" />;
    return <Clock className="h-4 w-4 text-gray-600" />;
  };

  const tabItems = [
    {
      key: "standup",
      label: "Daily Standup",
      children: (
        <div className="grid gap-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">
                Daily report from all 70+ agents (6:00 AM IST)
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Date: {daily_standup.date} | Status: {daily_standup.overall_status}
              </p>
            </div>
            <Button variant="ghost" onClick={loadDashboard}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
          </div>

          {/* Tier Summary */}
          {daily_standup.tier_summary && (
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {Object.entries(daily_standup.tier_summary).map(([tier, data]) => (
                <div key={tier} className="rounded-lg border border-gray-200 p-3 bg-white">
                  <p className="text-xs font-semibold text-gray-700 uppercase">{tier}</p>
                  <div className="mt-2 flex gap-1">
                    <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-green-100 text-green-800">
                      {data.healthy}✓
                    </span>
                    <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-yellow-100 text-yellow-800">
                      {data.degraded}⚠
                    </span>
                    <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-red-100 text-red-800">
                      {data.critical}✗
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">Avg: {data.avg_success_rate.toFixed(0)}%</p>
                </div>
              ))}
            </div>
          )}

          {/* Agent List */}
          <div className="space-y-2">
            <h3 className="font-semibold text-sm">Agent Status</h3>
            {daily_standup.agent_standups?.map((agent) => (
              <div
                key={agent.agent_name}
                onClick={() => handleAgentClick(agent.agent_name)}
                className={`rounded-lg border p-3 cursor-pointer transition-all ${getStatusColor(agent.status)} hover:shadow-md`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(agent.status)}
                    <div>
                      <p className="text-sm font-semibold">{agent.agent_name}</p>
                      <p className="text-xs text-gray-500">{agent.tier}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold">{agent.success_rate}%</p>
                    <p className="text-xs text-gray-500">{agent.executions} executions</p>
                  </div>
                </div>
                {agent.errors && agent.errors.length > 0 && (
                  <div className="mt-2 text-xs text-red-700">
                    Last error: {agent.errors[0]}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )
    },
    {
      key: "scrum",
      label: "Scrum of Scrums",
      children: (
        <div className="grid gap-4">
          <div>
            <p className="text-sm text-gray-600">
              Thunder + Flask report to CEO Agent (7:00 AM IST)
            </p>
            <p className="text-xs text-gray-500 mt-1">
              System Health: <span className="font-semibold">{scrum_of_scrums.system_health}</span>
            </p>
          </div>

          {/* Thunder Report */}
          <Card title="Thunder's Report" subtitle="Recruitment Agent">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500">Executions</p>
                <p className="text-2xl font-bold">{scrum_of_scrums.thunder_report.executions}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Success Rate</p>
                <p className="text-2xl font-bold">{scrum_of_scrums.thunder_report.success_rate}%</p>
              </div>
            </div>
          </Card>

          {/* CEO Decisions */}
          {scrum_of_scrums.ceo_agent_decisions?.length > 0 && (
            <Card title={`CEO Agent Decisions (${scrum_of_scrums.ceo_agent_decisions.length})`}>
              <div className="space-y-2">
                {scrum_of_scrums.ceo_agent_decisions.map((decision, idx) => (
                  <div key={idx} className="rounded-lg border border-red-200 bg-red-50 p-3">
                    <p className="font-semibold text-sm text-red-900">{decision.agent}</p>
                    <p className="text-xs text-red-700 mt-1">{decision.decision}</p>
                    <p className="text-xs text-red-600 mt-1">{decision.action}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Strategic Instructions */}
          <Card title="Strategic Instructions">
            <ul className="list-disc pl-4 space-y-1 text-sm text-gray-700">
              {scrum_of_scrums.strategic_instructions?.map((instr, idx) => (
                <li key={idx}>{instr}</li>
              ))}
            </ul>
          </Card>
        </div>
      )
    },
    {
      key: "feedback",
      label: "Weekly Feedback",
      children: (
        <div className="grid gap-4">
          <div>
            <p className="text-sm text-gray-600">
              Performance review from Feedback Agent (Friday 5:00 PM IST)
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Week ending: {weekly_feedback.week_ending}
            </p>
          </div>

          {/* Summary */}
          <div className="grid grid-cols-4 gap-2">
            <div className="rounded-lg bg-green-50 border border-green-200 p-3">
              <p className="text-xs text-gray-600">Excellent</p>
              <p className="text-2xl font-bold text-green-700">{weekly_feedback.summary.excellent}</p>
            </div>
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
              <p className="text-xs text-gray-600">Good</p>
              <p className="text-2xl font-bold text-blue-700">{weekly_feedback.summary.good}</p>
            </div>
            <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-3">
              <p className="text-xs text-gray-600">Needs Improvement</p>
              <p className="text-2xl font-bold text-yellow-700">{weekly_feedback.summary.needs_improvement}</p>
            </div>
            <div className="rounded-lg bg-red-50 border border-red-200 p-3">
              <p className="text-xs text-gray-600">Critical</p>
              <p className="text-2xl font-bold text-red-700">{weekly_feedback.summary.critical}</p>
            </div>
          </div>

          {/* Agent Feedback */}
          <div className="space-y-2">
            <h3 className="font-semibold text-sm">Agent Performance</h3>
            {weekly_feedback.feedback_entries?.map((entry) => (
              <div key={entry.agent} className={`rounded-lg border p-3 ${getStatusColor(entry.status)}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-sm">{entry.agent}</p>
                    <p className="text-xs text-gray-600 mt-1">{entry.feedback}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold">{entry.performance_score}</p>
                    <p className="text-xs text-gray-500">{entry.success_rate}% success</p>
                  </div>
                </div>
                {entry.reward_or_action && (
                  <p className="text-xs font-semibold mt-2 text-gray-700">
                    → {entry.reward_or_action}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )
    },
    {
      key: "provide-feedback",
      label: "Provide Feedback",
      children: (
        <div className="grid gap-4">
          {!selectedAgent ? (
            <div className="rounded-lg border-2 border-dashed border-gray-300 p-6 text-center">
              <p className="text-gray-600">
                Select an agent from the Daily Standup tab to provide feedback
              </p>
            </div>
          ) : (
            <Card title={`Feedback for ${selectedAgent}`}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Action Type</label>
                  <select
                    value={feedbackAction}
                    onChange={(e) => setFeedbackAction(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  >
                    <option value="encourage">Encourage (Top Performer Recognition)</option>
                    <option value="improve">Improve (Performance Improvement)</option>
                    <option value="escalate">Escalate (Critical - 24h Turnaround)</option>
                    <option value="replace">Replace (Immediate Replacement)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Feedback</label>
                  <textarea
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    placeholder="Enter your feedback for the agent..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm"
                    rows={4}
                  />
                </div>

                {agentDetails && (
                  <div className="rounded-lg bg-gray-50 p-3">
                    <p className="text-xs font-semibold text-gray-700">Agent Status</p>
                    <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                      <div>Success Rate: {agentDetails.metrics?.success_rate}%</div>
                      <div>Executions: {agentDetails.metrics?.executions}</div>
                      <div>Avg Duration: {agentDetails.metrics?.avg_duration_ms}ms</div>
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => setSelectedAgent(null)}
                    disabled={submittingFeedback}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    onClick={submitFeedback}
                    disabled={submittingFeedback || !feedbackText.trim()}
                  >
                    {submittingFeedback ? "Sending..." : "Send Feedback"}
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </div>
      )
    }
  ];

  return (
    <Card
      title="Agent Standups & Scrum of Scrums"
      subtitle="Daily coordination dashboard for all 70+ agents with CEO performance management"
    >
      <Tabs
        items={tabItems}
        defaultActiveKey="standup"
        style={{ backgroundColor: "transparent", borderRadius: "0" }}
      />
    </Card>
  );
}
