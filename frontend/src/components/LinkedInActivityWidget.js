import { Link2, TrendingUp, CheckCircle, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

export default function LinkedInActivityWidget() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    pending: 0,
    connected: 0,
    imported: 0,
    total: 0,
  });
  const [loading, setLoading] = useState(true);

  const token = localStorage.getItem("token");

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await axios.get(
          `${API_BASE}/api/v1/linkedin-candidate-pipeline/list`,
          { headers: { Authorization: `Bearer ${token}` } }
        );

        const items = response.data.items || [];
        const stats = {
          total: items.length,
          pending: items.filter((i) => i.status === "PENDING_CONNECTION").length,
          connected: items.filter((i) => i.status === "CONNECTED").length,
          imported: items.filter((i) => i.status === "IMPORTED_TO_THUNDER").length,
        };

        setStats(stats);
      } catch (error) {
        console.error("Failed to fetch LinkedIn stats:", error);
        setStats({ pending: 0, connected: 0, imported: 0, total: 0 });
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      fetchStats();
    } else {
      setLoading(false);
    }
  }, [token]);

  if (loading) {
    return (
      <div className="rounded-2xl border bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold text-gray-600">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Link2 className="h-5 w-5 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-900">LinkedIn Activity</h3>
        </div>
        <TrendingUp className="h-4 w-4 text-green-600" />
      </div>

      <div className="space-y-3">
        {/* Total Queue */}
        <div
          onClick={() => navigate("/linkedin-pipeline")}
          className="cursor-pointer rounded-lg bg-gradient-to-r from-blue-50 to-blue-100 p-3 hover:from-blue-100 hover:to-blue-200 transition"
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-blue-700 font-medium">Queue Total</div>
              <div className="text-2xl font-bold text-blue-900 mt-1">{stats.total}</div>
            </div>
            <UserPlus className="h-5 w-5 text-blue-600 opacity-50" />
          </div>
        </div>

        {/* Status Breakdown */}
        <div className="grid grid-cols-3 gap-2">
          {/* Pending */}
          <div className="rounded-lg bg-yellow-50 p-2">
            <div className="text-xs text-yellow-700 font-medium">Pending</div>
            <div className="text-lg font-bold text-yellow-900 mt-1">{stats.pending}</div>
          </div>

          {/* Connected */}
          <div className="rounded-lg bg-blue-50 p-2">
            <div className="text-xs text-blue-700 font-medium">Connected</div>
            <div className="text-lg font-bold text-blue-900 mt-1">{stats.connected}</div>
          </div>

          {/* Imported */}
          <div className="rounded-lg bg-green-50 p-2">
            <div className="text-xs text-green-700 font-medium">Imported</div>
            <div className="text-lg font-bold text-green-900 mt-1">{stats.imported}</div>
          </div>
        </div>

        {/* Quick Actions */}
        <button
          onClick={() => navigate("/linkedin-pipeline")}
          className="w-full mt-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 transition"
        >
          Manage Pipeline
        </button>
      </div>

      {/* Info Text */}
      {stats.total === 0 && (
        <div className="mt-3 p-3 rounded-lg bg-gray-50">
          <p className="text-xs text-gray-600">
            No LinkedIn candidates queued yet. Start by adding a LinkedIn URL to your pipeline.
          </p>
        </div>
      )}
    </div>
  );
}
