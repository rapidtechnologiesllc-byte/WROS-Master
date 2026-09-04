// S-364/S-365 -- active 30-Day Buddy Program cohort.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Card } from "../components/ui";
import { listBuddyProgramRecords } from "../services/api/buddyProgram";
import { ROUTES } from "../utils/Routes";

export default function BuddyProgramListScreen() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    listBuddyProgramRecords()
      .then(setRecords)
      .catch(() => toast.error("Could not load buddy program records."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Card title="Active Cohort" subtitle="New hires currently in their Buddy Program run.">
        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : records.length === 0 ? (
          <p className="text-sm text-gray-400">No active buddy program records.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-gray-500">
              <tr>
                <th className="py-1.5 pr-3">Employee</th>
                <th className="py-1.5 pr-3">Status</th>
                <th className="py-1.5 pr-3">Expected End</th>
                <th className="py-1.5 pr-3">Extensions</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-gray-100 cursor-pointer hover:bg-gray-50"
                  onClick={() => navigate(`${ROUTES.BUDDY_PROGRAM}/${r.id}`)}
                >
                  <td className="py-1.5 pr-3">{r.employee_id}</td>
                  <td className="py-1.5 pr-3">{r.status}</td>
                  <td className="py-1.5 pr-3">{r.expected_end_date}</td>
                  <td className="py-1.5 pr-3">{r.extension_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
