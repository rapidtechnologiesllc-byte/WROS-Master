import { Award, Trophy, Zap } from "lucide-react";
import { useState, useEffect } from "react";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

export default function WeeklyPerformersWidget() {
  const [performers, setPerformers] = useState([]);
  const [loading, setLoading] = useState(true);

  const token = localStorage.getItem("token");

  useEffect(() => {
    const fetchPerformers = async () => {
      try {
        // Fetch candidates data to calculate weekly performance
        const response = await axios.get(
          `${API_BASE}/api/v1/onboarding/hr/get_all_candidates`,
          { headers: { Authorization: `Bearer ${token}` } }
        );

        const candidates = response.data?.candidates || [];

        // Calculate performance metrics (simplified for demo)
        // In production, this would query a dedicated metrics/analytics table
        const performanceMap = new Map();

        candidates.forEach((candidate) => {
          const assignedHr = candidate.assigned_hr_manager_id;
          if (!assignedHr) return;

          if (!performanceMap.has(assignedHr)) {
            performanceMap.set(assignedHr, {
              id: assignedHr,
              name: `Recruiter ${assignedHr.substring(0, 8)}`,
              candidates: 0,
              offers: 0,
              interviewed: 0,
            });
          }

          const record = performanceMap.get(assignedHr);
          record.candidates += 1;

          // Count offers and interviews
          if (candidate.pipelineStatus === "Offer Extended") record.offers += 1;
          if (candidate.pipelineStatus === "Interview Scheduled") record.interviewed += 1;
        });

        // Convert to array and sort by total activity (candidates + offers + interviews)
        const sorted = Array.from(performanceMap.values())
          .sort((a, b) => {
            const scoreA = a.candidates + a.offers * 2 + a.interviewed;
            const scoreB = b.candidates + b.offers * 2 + b.interviewed;
            return scoreB - scoreA;
          })
          .slice(0, 5); // Top 5 performers

        setPerformers(sorted);
      } catch (error) {
        console.error("Failed to fetch weekly performers:", error);
        setPerformers([]);
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      fetchPerformers();
    } else {
      setLoading(false);
    }
  }, [token]);

  if (loading) {
    return (
      <div className="rounded-2xl border bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Trophy className="h-5 w-5 text-yellow-600" />
          <h3 className="text-sm font-semibold text-gray-900">Loading...</h3>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <Trophy className="h-5 w-5 text-yellow-600" />
        <h3 className="text-sm font-semibold text-gray-900">Weekly Performers</h3>
      </div>

      {performers.length === 0 ? (
        <div className="py-8 text-center">
          <Zap className="h-8 w-8 text-gray-300 mx-auto mb-2" />
          <p className="text-xs text-gray-600">No activity this week yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {performers.map((performer, index) => {
            const score = performer.candidates + performer.offers * 2 + performer.interviewed;
            const medal = index === 0 ? "🥇" : index === 1 ? "🥈" : index === 2 ? "🥉" : "⭐";

            return (
              <div
                key={performer.id}
                className="rounded-lg bg-gradient-to-r from-gray-50 to-gray-100 p-3 hover:from-gray-100 hover:to-gray-150 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-xl">{medal}</div>
                    <div>
                      <div className="text-sm font-semibold text-gray-900">
                        {performer.name}
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        {performer.candidates} candidates • {performer.offers} offers • {performer.interviewed} interviews
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-blue-600">{score}</div>
                    <div className="text-xs text-gray-600">points</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 p-3 rounded-lg bg-blue-50 border border-blue-200">
        <div className="text-xs text-blue-900 font-medium mb-2">Scoring:</div>
        <div className="text-xs text-blue-800 space-y-1">
          <div>• Candidate: +1 point</div>
          <div>• Offer: +2 points</div>
          <div>• Interview: +1 point</div>
        </div>
      </div>
    </div>
  );
}
