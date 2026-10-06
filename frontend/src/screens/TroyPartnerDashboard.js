import { useEffect, useState } from "react";
import { Briefcase, Users, Award, TrendingUp, AlertCircle, X, AlertTriangle } from "lucide-react";
import { Card, Button } from "../components/ui";
import { apiRequest } from "../services/api/client";
import { listBusinessUnits } from "../services/api/rbac";
import { getHrMe } from "../services/api/users";
import DashboardBUPicker from "../components/DashboardBUPicker";

export default function TroyPartnerDashboard() {
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [buName, setBuName] = useState("");
  // Users without a BU of their own (e.g. Admin) choose which BU to view
  const [buChoices, setBuChoices] = useState(null);
  const [selectedBuId, setSelectedBuId] = useState(null);

  // BU label = the logged-in user's business unit (Users & Access Control > Business Units)
  useEffect(() => {
    Promise.all([getHrMe(), listBusinessUnits()])
      .then(([me, bus]) => {
        const bu = bus.find((b) => String(b.id) === String(me?.business_unit_id));
        setBuName(bu?.name || "");
      })
      .catch((err) => setActionError(`Failed to load business unit: ${err.message}`));
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const qs = selectedBuId ? `?business_unit_id=${selectedBuId}` : "";
        const { data } = await apiRequest(`/dashboards/troy-partner${qs}`, { method: "GET" });
        if (data?.status === "needs_business_unit") {
          setBuChoices(data.business_units || []);
          setDashboard(null);
          return;
        }
        setDashboard(data?.data);
        if (buChoices && data?.business_unit_id) {
          setBuName(buChoices.find((b) => b.id === data.business_unit_id)?.name || "");
        }
      } catch (err) {
        setActionError(`Failed to load Troy's dashboard: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedBuId]);

  const picker = buChoices ? (
    <DashboardBUPicker businessUnits={buChoices} value={selectedBuId} onChange={setSelectedBuId} />
  ) : null;

  if (loading) return <div className="p-6 text-center text-gray-500">Loading dashboard...</div>;
  if (!dashboard) {
    return (
      <div className="p-6 space-y-4 max-w-6xl mx-auto">
        {actionError && <div className="text-red-700 text-sm">{actionError}</div>}
        {picker || <div className="text-center text-gray-500">No data available</div>}
      </div>
    );
  }

  const {
    current_demand,
    pre_onboarding_pipeline,
    certifications,
    buddy_program,
    core_certified_employees
  } = dashboard;

  return (
    <div className="space-y-6 p-6 max-w-6xl mx-auto">
      {/* Error Banner */}
      {actionError && (
        <div className="mb-6 border border-red-200 bg-red-50 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-red-600">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <span className="text-red-800">{actionError}</span>
          </div>
          <button
            onClick={() => setActionError(null)}
            className="text-red-600 hover:text-red-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Troy's Partner Dashboard</h1>
        <div className="text-sm text-gray-600">{buName || "No business unit assigned"}</div>
      </div>
      {picker}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Open Positions</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{current_demand?.open_positions || 0}</div>
            </div>
            <Briefcase className="h-6 w-6 text-blue-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Pre-Onboarding</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{pre_onboarding_pipeline?.in_pre_onboarding || 0}</div>
            </div>
            <TrendingUp className="h-6 w-6 text-purple-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Certified</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{certifications?.total_active || 0}</div>
            </div>
            <Award className="h-6 w-6 text-green-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Buddy Program</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{buddy_program?.total_in_program || 0}</div>
            </div>
            <Users className="h-6 w-6 text-indigo-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Core Certified</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{core_certified_employees?.length || 0}</div>
            </div>
            <Award className="h-6 w-6 text-yellow-500" />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current Demand */}
        <Card title="Current Demand">
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
              <span className="font-semibold">Open Positions</span>
              <span className="text-2xl font-bold text-blue-600">{current_demand?.open_positions || 0}</span>
            </div>
            <div className="text-sm text-gray-600">
              Positions available for recruitment in your business unit
            </div>
            <Button className="w-full">View Open Positions</Button>
          </div>
        </Card>

        {/* Pre-Onboarding Pipeline */}
        <Card title="Pre-Onboarding Pipeline">
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-purple-50 rounded-lg">
              <span className="font-semibold">In Pipeline</span>
              <span className="text-2xl font-bold text-purple-600">{pre_onboarding_pipeline?.in_pre_onboarding || 0}</span>
            </div>
            <div className="text-sm text-gray-600">
              Candidates ready for onboarding
            </div>
            <Button className="w-full">Start Onboarding</Button>
          </div>
        </Card>

        {/* Certifications */}
        <Card title="Certification Status">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>Total Certified</span>
              <span className="font-bold">{certifications?.total_active || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-orange-600">Expiring Soon</span>
              <span className="font-bold text-orange-600">{certifications?.expiring_within_30_days || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-red-600">Expired</span>
              <span className="font-bold text-red-600">{certifications?.already_expired || 0}</span>
            </div>
            {certifications?.by_level && (
              <div className="mt-3 pt-3 border-t space-y-1">
                {Object.entries(certifications.by_level).map(([level, count]) => (
                  <div key={level} className="flex justify-between text-sm">
                    <span>{level}</span>
                    <span className="font-semibold">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Buddy Program */}
        <Card title="Buddy Program Status">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>In Program</span>
              <span className="font-bold">{buddy_program?.total_in_program || 0}</span>
            </div>
            <div className="flex justify-between text-green-600">
              <span>On Track</span>
              <span className="font-bold">{buddy_program?.on_track || 0}</span>
            </div>
            <div className="flex justify-between text-orange-600">
              <span>At Risk</span>
              <span className="font-bold">{buddy_program?.at_risk || 0}</span>
            </div>
            <div className="flex justify-between text-green-600">
              <span>Completed This Month</span>
              <span className="font-bold">{buddy_program?.completed_this_month || 0}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Core Certified Employees */}
      <Card title="Core Certified Employees">
        {core_certified_employees && core_certified_employees.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3 font-semibold">Employee</th>
                  <th className="text-left py-2 px-3 font-semibold">Certification</th>
                  <th className="text-left py-2 px-3 font-semibold">Earned Date</th>
                </tr>
              </thead>
              <tbody>
                {core_certified_employees.map((emp, idx) => (
                  <tr key={idx} className="border-b hover:bg-gray-50">
                    <td className="py-2 px-3">{emp.name}</td>
                    <td className="py-2 px-3">{emp.certification}</td>
                    <td className="py-2 px-3 text-sm text-gray-600">
                      {emp.earned_date ? new Date(emp.earned_date).toLocaleDateString() : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-600 py-4">No core certified employees yet</div>
        )}
      </Card>
    </div>
  );
}
