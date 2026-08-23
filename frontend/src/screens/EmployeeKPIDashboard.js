// Employee KPI Dashboard showing certification targets and progress
import { useEffect, useState } from "react";
import { CheckCircle2, Clock, AlertCircle, TrendingUp } from "lucide-react";
import { Card, Button } from "../components/ui";
import { toast } from "react-toastify";

export default function EmployeeKPIDashboard({ employeeId, onClose }) {
  const [kpiScore, setKPIScore] = useState(null);
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadKPIData();
  }, [employeeId]);

  const loadKPIData = async () => {
    setLoading(true);
    try {
      // Load KPI score
      const scoreResponse = await fetch(`/admin/certifications/employee/${employeeId}/score`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (scoreResponse.ok) {
        const scoreData = await scoreResponse.json();
        setKPIScore(scoreData);
      }

      // Load targets
      const targetsResponse = await fetch(`/admin/certifications/employee/${employeeId}/targets`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      if (targetsResponse.ok) {
        const targetsData = await targetsResponse.json();
        setTargets(targetsData);
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAchieved = async (targetId) => {
    try {
      const response = await fetch(`/admin/certifications/mark-achieved/${targetId}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });

      if (!response.ok) throw new Error("Failed to mark as achieved");

      toast.success("Certification marked as achieved!");
      loadKPIData();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "ACHIEVED":
        return "bg-green-100 text-green-800 border-green-300";
      case "PENDING":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "OVERDUE":
        return "bg-red-100 text-red-800 border-red-300";
      default:
        return "bg-gray-100 text-gray-800 border-gray-300";
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "ACHIEVED":
        return <CheckCircle2 className="h-5 w-5" />;
      case "PENDING":
        return <Clock className="h-5 w-5" />;
      case "OVERDUE":
        return <AlertCircle className="h-5 w-5" />;
      default:
        return null;
    }
  };

  const isOverdue = (targetDate) => {
    return new Date(targetDate) < new Date();
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <Card className="w-full max-w-2xl p-8 text-center">Loading...</Card>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <Card className="w-full max-w-2xl max-h-96 overflow-y-auto">
        <div className="border-b p-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-6 w-6" />
            <h2 className="text-lg font-semibold">KPI Dashboard</h2>
          </div>
          <Button variant="ghost" onClick={onClose}>
            ✕
          </Button>
        </div>

        <div className="p-4 space-y-6">
          {/* Overall KPI Score */}
          {kpiScore && (
            <div className="bg-gradient-to-r from-blue-50 to-blue-100 border border-blue-300 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">Overall KPI Score</div>
              <div className="text-4xl font-bold text-blue-600">{kpiScore.overall_score.toFixed(1)}/100</div>
              <div className="text-xs text-gray-600 mt-2">Last calculated: {new Date(kpiScore.last_calculated_at).toLocaleString()}</div>

              <div className="mt-4 space-y-2">
                <div className="text-sm font-semibold">Components:</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-white p-2 rounded border">
                    <div className="text-gray-600">Certification</div>
                    <div className="font-bold text-lg">{kpiScore.certification_score.toFixed(1)}%</div>
                  </div>
                  <div className="bg-white p-2 rounded border">
                    <div className="text-gray-600">Performance</div>
                    <div className="font-bold text-lg">{kpiScore.performance_score.toFixed(1)}%</div>
                  </div>
                  <div className="bg-white p-2 rounded border">
                    <div className="text-gray-600">Utilization</div>
                    <div className="font-bold text-lg">{kpiScore.utilization_score.toFixed(1)}%</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Certification Targets */}
          <div>
            <h3 className="font-semibold mb-3">Certification Targets ({targets.length})</h3>

            {targets.length === 0 ? (
              <div className="text-center text-gray-500 py-4">No certification targets assigned</div>
            ) : (
              <div className="space-y-2">
                {targets.map((target) => {
                  const overdue = !target.is_achieved && isOverdue(target.target_date);
                  const status = target.is_achieved ? "ACHIEVED" : overdue ? "OVERDUE" : "PENDING";

                  return (
                    <div
                      key={target.id}
                      className={`border rounded-lg p-3 ${getStatusColor(status)}`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(status)}
                            <div>
                              <div className="font-semibold">{target.certification_id}</div>
                              <div className="text-sm opacity-75">
                                Target Date: {new Date(target.target_date).toLocaleDateString()}
                              </div>
                              {target.achieved_date && (
                                <div className="text-sm opacity-75">
                                  Achieved: {new Date(target.achieved_date).toLocaleDateString()}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                        <div>
                          {!target.is_achieved && (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleMarkAchieved(target.id)}
                              className="text-xs"
                            >
                              Mark Achieved
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Summary Stats */}
          {targets.length > 0 && (
            <div className="bg-gray-50 p-3 rounded-lg">
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div>
                  <div className="text-gray-600">Achieved</div>
                  <div className="text-lg font-bold text-green-600">
                    {targets.filter((t) => t.is_achieved).length}
                  </div>
                </div>
                <div>
                  <div className="text-gray-600">Pending</div>
                  <div className="text-lg font-bold text-blue-600">
                    {targets.filter((t) => !t.is_achieved && !isOverdue(t.target_date)).length}
                  </div>
                </div>
                <div>
                  <div className="text-gray-600">Overdue</div>
                  <div className="text-lg font-bold text-red-600">
                    {targets.filter((t) => !t.is_achieved && isOverdue(t.target_date)).length}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="border-t p-4 text-center">
          <Button variant="ghost" onClick={onClose} className="w-full">
            Close
          </Button>
        </div>
      </Card>
    </div>
  );
}
