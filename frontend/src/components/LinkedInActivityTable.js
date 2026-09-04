import { useState, useEffect } from "react";
import { ExternalLink, AlertCircle, Loader, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const STATUS_COLORS = {
  PENDING_CONNECTION: "bg-yellow-50 text-yellow-900",
  CONNECTED: "bg-blue-50 text-blue-900",
  PHONE_COLLECTED: "bg-purple-50 text-purple-900",
  IMPORTED_TO_THUNDER: "bg-green-50 text-green-900",
};

const PENDING_ACTION_COLORS = {
  "Send LinkedIn Connection Request": "text-yellow-700",
  "Collect Phone Number": "text-blue-700",
  "Import to Thunder": "text-purple-700",
  "Monitor Engagement": "text-green-700",
};

export default function LinkedInActivityTable() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");

  const token = localStorage.getItem("token");

  useEffect(() => {
    const fetchActivity = async () => {
      try {
        const response = await axios.get(
          `${API_BASE}/api/v1/linkedin-candidate-pipeline/dashboard/activity`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setItems(response.data.items || []);
      } catch (error) {
        console.error("Failed to fetch LinkedIn activity:", error);
        setItems([]);
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      fetchActivity();
    } else {
      setLoading(false);
    }
  }, [token]);

  const handleSort = (column) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(column);
      setSortOrder("asc");
    }
  };

  const sortedItems = [...items].sort((a, b) => {
    let aVal = a[sortBy];
    let bVal = b[sortBy];

    if (typeof aVal === "string") {
      aVal = aVal.toLowerCase();
      bVal = bVal.toLowerCase();
    }

    const comparison = aVal > bVal ? 1 : -1;
    return sortOrder === "asc" ? comparison : -comparison;
  });

  if (loading) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Loader className="w-5 h-5 animate-spin text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-900">Loading LinkedIn Activity...</h3>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className="w-5 h-5 text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-900">LinkedIn Activity</h3>
        </div>
        <div className="py-8 text-center">
          <p className="text-sm text-gray-600 mb-4">No LinkedIn candidates in queue yet</p>
          <button
            onClick={() => navigate("/linkedin-pipeline")}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
          >
            <ChevronRight className="w-4 h-4" />
            Start LinkedIn Pipeline
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">
          LinkedIn Activity ({items.length} candidates)
        </h3>
        <button
          onClick={() => navigate("/linkedin-pipeline")}
          className="text-xs font-medium text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          Manage <ChevronRight className="w-3 h-3" />
        </button>
      </div>

      {/* Responsive Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th
                className="px-3 py-2 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("candidate_name")}
              >
                Candidate {sortBy === "candidate_name" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th
                className="px-3 py-2 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("status")}
              >
                Status {sortBy === "status" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th
                className="px-3 py-2 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("days_in_pipeline")}
              >
                Days {sortBy === "days_in_pipeline" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th className="px-3 py-2 text-left font-semibold text-gray-700">Pending Action</th>
              <th className="px-3 py-2 text-left font-semibold text-gray-700">Phone</th>
            </tr>
          </thead>
          <tbody>
            {sortedItems.map((item) => (
              <tr
                key={item.id}
                className="border-b border-gray-100 hover:bg-gray-50 transition cursor-pointer"
                onClick={() => navigate("/linkedin-pipeline")}
              >
                <td className="px-3 py-3">
                  <div>
                    <div className="font-medium text-gray-900">{item.candidate_name}</div>
                    <a
                      href={item.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 mt-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View Profile <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </td>
                <td className="px-3 py-3">
                  <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[item.status] || "bg-gray-100 text-gray-900"}`}>
                    {item.status?.replace(/_/g, " ") || "Unknown"}
                  </span>
                </td>
                <td className="px-3 py-3">
                  <span className="text-gray-900 font-medium">{item.days_in_pipeline}d</span>
                </td>
                <td className="px-3 py-3">
                  <span className={`text-xs font-medium ${PENDING_ACTION_COLORS[item.pending_action] || "text-gray-700"}`}>
                    {item.pending_action}
                  </span>
                </td>
                <td className="px-3 py-3">
                  <span className="text-gray-900">
                    {item.phone_number || <span className="text-gray-400">—</span>}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Quick Stats */}
      <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-4 gap-3">
        {[
          { label: "Pending", color: "text-yellow-600", count: sortedItems.filter(i => i.status === "PENDING_CONNECTION").length },
          { label: "Connected", color: "text-blue-600", count: sortedItems.filter(i => i.status === "CONNECTED").length },
          { label: "Phone", color: "text-purple-600", count: sortedItems.filter(i => i.status === "PHONE_COLLECTED").length },
          { label: "Imported", color: "text-green-600", count: sortedItems.filter(i => i.status === "IMPORTED_TO_THUNDER").length },
        ].map((stat) => (
          <div key={stat.label} className="text-center">
            <div className={`text-lg font-bold ${stat.color}`}>{stat.count}</div>
            <div className="text-xs text-gray-600">{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
