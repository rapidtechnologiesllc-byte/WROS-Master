import { useEffect, useState } from "react";
import { Award, CheckCircle, AlertCircle } from "lucide-react";
import { Card } from "../components/ui";

const GUIDEWIRE_CERTS = ["ACE", "Associate", "Specialist"];

export default function TrainingCertificationDashboard() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock data - replace with API call when backend is ready
    const mockData = [
      { id: 1, name: "John Smith", current: "Specialist", expected: "Specialist", status: "Met" },
      { id: 2, name: "Sarah Johnson", current: "Associate", expected: "Specialist", status: "Gap" },
      { id: 3, name: "Mike Chen", current: "ACE", expected: "Associate", status: "Exceeds" },
      { id: 4, name: "Lisa Rodriguez", current: "None", expected: "Associate", status: "Gap" },
      { id: 5, name: "David Kim", current: "Specialist", expected: "ACE", status: "Below" },
    ];

    setEmployees(mockData);
    setLoading(false);
  }, []);

  const calculateMetrics = () => {
    const metrics = {
      total: employees.length,
      certified: employees.filter(e => e.current !== "None").length,
      metExpected: employees.filter(e => {
        const levels = { "None": 0, "ACE": 1, "Associate": 2, "Specialist": 3 };
        return levels[e.current] >= levels[e.expected];
      }).length,
      gaps: employees.filter(e => {
        const levels = { "None": 0, "ACE": 1, "Associate": 2, "Specialist": 3 };
        return levels[e.current] < levels[e.expected];
      }).length,
    };
    return metrics;
  };

  const metrics = calculateMetrics();
  const statusColor = (status) => {
    switch (status) {
      case "Met": return "bg-green-50 border-green-200";
      case "Exceeds": return "bg-blue-50 border-blue-200";
      case "Gap": return "bg-red-50 border-red-200";
      case "Below": return "bg-orange-50 border-orange-200";
      default: return "bg-gray-50 border-gray-200";
    }
  };

  const statusIcon = (status) => {
    switch (status) {
      case "Met": return <CheckCircle className="h-5 w-5 text-green-600" />;
      case "Exceeds": return <Award className="h-5 w-5 text-blue-600" />;
      case "Gap": return <AlertCircle className="h-5 w-5 text-red-600" />;
      case "Below": return <AlertCircle className="h-5 w-5 text-orange-600" />;
      default: return null;
    }
  };

  if (loading) return <div className="p-6 text-center text-gray-500">Loading...</div>;

  return (
    <div className="space-y-6 p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900">Guidewire Certification Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Total Employees</div>
              <div className="text-3xl font-bold text-gray-900 mt-2">{metrics.total}</div>
            </div>
            <Award className="h-6 w-6 text-blue-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Certified</div>
              <div className="text-3xl font-bold text-green-600 mt-2">{metrics.certified}</div>
            </div>
            <CheckCircle className="h-6 w-6 text-green-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Met Expected</div>
              <div className="text-3xl font-bold text-green-600 mt-2">{metrics.metExpected}</div>
            </div>
            <CheckCircle className="h-6 w-6 text-green-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Certification Gaps</div>
              <div className="text-3xl font-bold text-red-600 mt-2">{metrics.gaps}</div>
            </div>
            <AlertCircle className="h-6 w-6 text-red-500" />
          </div>
        </Card>
      </div>

      {/* Employee Certification Table */}
      <Card title="Employee Certification Status">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Employee</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-700">Current Level</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-700">Expected Level</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-700">Status</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => (
                <tr key={emp.id} className={`border-b ${statusColor(emp.status)}`}>
                  <td className="py-3 px-4 text-gray-900 font-medium">{emp.name}</td>
                  <td className="py-3 px-4 text-center">
                    <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-gray-200 text-gray-800">
                      {emp.current}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-blue-200 text-blue-800">
                      {emp.expected}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {statusIcon(emp.status)}
                      <span className="text-xs font-semibold">{emp.status}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
