import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Brain, Users, AlertCircle, CheckCircle } from "lucide-react";
import { Card } from "./ui";
import { apiRequest } from "../services/api/client";

export default function FlashVsPanelComparison({ interviewId, panelFeedback }) {
  const [flashAnalysis, setFlashAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchFlashAnalysis = async () => {
      try {
        setLoading(true);
        const { data } = await apiRequest(
          `/flash/interviews/${interviewId}/analysis`,
          { method: "GET" }
        );
        if (data?.data) {
          setFlashAnalysis(data.data);
        }
      } catch (err) {
        console.error("Failed to fetch Flash analysis:", err);
        // Don't show error toast - Flash analysis is supplementary
      } finally {
        setLoading(false);
      }
    };

    if (interviewId && !flashAnalysis) {
      fetchFlashAnalysis();
    }
  }, [interviewId, flashAnalysis]);

  const RecommendationBadge = ({ recommendation, confidence }) => {
    const colors = {
      HIRE: "bg-green-50 border-green-200 text-green-700",
      NO_HIRE: "bg-red-50 border-red-200 text-red-700",
      MAYBE: "bg-amber-50 border-amber-200 text-amber-700"
    };
    return (
      <div className={`border rounded-lg px-4 py-3 ${colors[recommendation]}`}>
        <div className="flex items-center gap-2 mb-1">
          {recommendation === "HIRE" ? (
            <CheckCircle className="h-5 w-5" />
          ) : recommendation === "NO_HIRE" ? (
            <AlertCircle className="h-5 w-5" />
          ) : (
            <AlertCircle className="h-5 w-5" />
          )}
          <span className="font-semibold">{recommendation}</span>
        </div>
        <div className="text-xs opacity-75">{confidence}% confidence</div>
      </div>
    );
  };

  const ScoreCard = ({ label, score, level, maxScore = 5 }) => (
    <div className="bg-gray-50 rounded-lg p-3">
      <div className="text-xs text-gray-600 mb-1">{label}</div>
      <div className="flex items-end justify-between">
        <div className="text-2xl font-bold text-gray-900">{score}</div>
        <div className="flex gap-1">
          {Array.from({ length: maxScore }).map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${
                i < score ? "bg-blue-500" : "bg-gray-300"
              }`}
            />
          ))}
        </div>
      </div>
      <div className="text-xs text-gray-600 mt-1">{level}</div>
    </div>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
      {/* Panel Feedback Column */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Users className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">Panel Feedback</h3>
        </div>
        {panelFeedback ? (
          <Card>
            <div className="space-y-4">
              {panelFeedback.recommendation && (
                <RecommendationBadge
                  recommendation={panelFeedback.recommendation}
                  confidence={panelFeedback.confidence || 75}
                />
              )}

              {panelFeedback.scores && (
                <div className="grid grid-cols-2 gap-3">
                  {panelFeedback.scores.technical && (
                    <ScoreCard
                      label="Technical"
                      score={panelFeedback.scores.technical}
                      level="Proficiency"
                    />
                  )}
                  {panelFeedback.scores.communication && (
                    <ScoreCard
                      label="Communication"
                      score={panelFeedback.scores.communication}
                      level="Clarity"
                    />
                  )}
                  {panelFeedback.scores.problemSolving && (
                    <ScoreCard
                      label="Problem Solving"
                      score={panelFeedback.scores.problemSolving}
                      level="Rigor"
                    />
                  )}
                  {panelFeedback.scores.cultureFit && (
                    <ScoreCard
                      label="Culture Fit"
                      score={panelFeedback.scores.cultureFit}
                      level="Alignment"
                    />
                  )}
                </div>
              )}

              {panelFeedback.comments && (
                <div className="border-t pt-4">
                  <div className="text-sm font-semibold text-gray-900 mb-2">
                    Comments
                  </div>
                  <div className="text-sm text-gray-700 whitespace-pre-wrap">
                    {panelFeedback.comments}
                  </div>
                </div>
              )}
            </div>
          </Card>
        ) : (
          <Card>
            <div className="text-center text-gray-500 py-6">
              No panel feedback yet
            </div>
          </Card>
        )}
      </div>

      {/* Flash Analysis Column */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Brain className="h-5 w-5 text-purple-600" />
          <h3 className="text-lg font-semibold text-gray-900">Flash Analysis</h3>
        </div>
        {loading ? (
          <Card>
            <div className="text-center text-gray-500 py-6">
              Analyzing transcript...
            </div>
          </Card>
        ) : flashAnalysis ? (
          <Card>
            <div className="space-y-4">
              {flashAnalysis.recommendation && (
                <RecommendationBadge
                  recommendation={flashAnalysis.recommendation}
                  confidence={flashAnalysis.confidence_pct}
                />
              )}

              <div className="bg-purple-50 rounded-lg p-3 border border-purple-200">
                <div className="text-sm text-purple-900">
                  <span className="font-semibold">Rationale:</span> {flashAnalysis.rationale}
                </div>
              </div>

              {flashAnalysis.technical_assessment && (
                <div className="grid grid-cols-2 gap-3">
                  <ScoreCard
                    label="Technical"
                    score={flashAnalysis.technical_assessment.score}
                    level={flashAnalysis.technical_assessment.level}
                  />
                  <ScoreCard
                    label="Communication"
                    score={flashAnalysis.communication_assessment.score}
                    level={flashAnalysis.communication_assessment.level}
                  />
                  <ScoreCard
                    label="Problem Solving"
                    score={flashAnalysis.problem_solving_assessment.score}
                    level={flashAnalysis.problem_solving_assessment.level}
                  />
                  <ScoreCard
                    label="Culture Fit"
                    score={flashAnalysis.culture_fit_assessment.score}
                    level={flashAnalysis.culture_fit_assessment.alignment}
                  />
                </div>
              )}

              {flashAnalysis.strengths && flashAnalysis.strengths.length > 0 && (
                <div className="border-t pt-3">
                  <div className="text-sm font-semibold text-gray-900 mb-2">
                    Key Strengths
                  </div>
                  <ul className="space-y-1">
                    {flashAnalysis.strengths.map((strength, i) => (
                      <li key={i} className="text-xs text-green-700 flex gap-2">
                        <span className="text-green-500">✓</span>
                        <span>{strength}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {flashAnalysis.concerns && flashAnalysis.concerns.length > 0 && (
                <div className="border-t pt-3">
                  <div className="text-sm font-semibold text-gray-900 mb-2">
                    Areas of Concern
                  </div>
                  <ul className="space-y-1">
                    {flashAnalysis.concerns.map((concern, i) => (
                      <li key={i} className="text-xs text-amber-700 flex gap-2">
                        <span className="text-amber-500">!</span>
                        <span>{concern}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="text-xs text-gray-500 pt-2">
                Analysis based on transcript and panel feedback scores
              </div>
            </div>
          </Card>
        ) : (
          <Card>
            <div className="text-center text-gray-500 py-6">
              Flash analysis not available
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
