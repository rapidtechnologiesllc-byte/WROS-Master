"""Learning Metrics Dashboard - Real-Time Autonomous System Intelligence

Displays SLM health score and recommendations from Thunder and Flash learning systems.
Shows how the system is learning and improving over time.
"""
import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { AlertCircle, TrendingUp, Zap, Target } from "lucide-react";

const LearningDashboard = () => {
  // State management
  const [slmHealth, setSLMHealth] = useState(null);
  const [thunderMetrics, setThunderMetrics] = useState(null);
  const [flashMetrics, setFlashMetrics] = useState(null);
  const [channelEffectiveness, setChannelEffectiveness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(5 * 60 * 1000); // 5 minutes

  // API endpoints
  const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8080/api/v1";

  // Fetch SLM health score
  const fetchSLMHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE}/learning/health`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("jwt_token")}`,
        },
      });

      if (response.data.status === "success") {
        setSLMHealth(response.data);
      }
    } catch (err) {
      console.error("Failed to fetch SLM health:", err);
      setError("Failed to load SLM health score");
    }
  };

  // Fetch channel effectiveness
  const fetchChannelEffectiveness = async () => {
    try {
      const response = await axios.get(`${API_BASE}/learning/thunder/channel-effectiveness`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("jwt_token")}`,
        },
      });

      if (response.data.status === "success") {
        setChannelEffectiveness(response.data.report);
      }
    } catch (err) {
      console.error("Failed to fetch channel effectiveness:", err);
    }
  };

  // Initial load
  useEffect(() => {
    fetchSLMHealth();
    fetchChannelEffectiveness();
    setLoading(false);

    // Set up auto-refresh
    const interval = setInterval(() => {
      fetchSLMHealth();
      fetchChannelEffectiveness();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Zap className="h-12 w-12 text-blue-500 mx-auto mb-4" />
          <p className="text-lg text-gray-600">Loading learning metrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-gray-900 flex items-center gap-3">
            <Zap className="h-8 w-8 text-blue-600" />
            SLM Learning Dashboard
          </h1>
          <p className="text-gray-600 mt-2">
            Real-time autonomous system learning and recommendations
          </p>
        </div>
        <button
          onClick={() => {
            fetchSLMHealth();
            fetchChannelEffectiveness();
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          Refresh Now
        </button>
      </div>

      {/* SLM Health Score - Main Card */}
      {slmHealth && (
        <Card className="bg-white border-2 border-blue-200 shadow-lg">
          <CardHeader className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white">
            <CardTitle className="flex items-center gap-3 text-2xl">
              <Target className="h-6 w-6" />
              SLM Health Score
            </CardTitle>
            <CardDescription className="text-blue-100">
              Composite health across all orchestrators
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Main Score */}
              <div className="flex flex-col items-center justify-center p-6 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg">
                <div className="text-6xl font-bold text-blue-600">
                  {slmHealth.slm_health_score.toFixed(1)}%
                </div>
                <p className="text-lg text-gray-600 mt-3">Overall Health</p>
                <div className="mt-4 w-full bg-gray-200 rounded-full h-3">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      slmHealth.slm_health_score > 70
                        ? "bg-green-500"
                        : slmHealth.slm_health_score > 50
                        ? "bg-yellow-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${slmHealth.slm_health_score}%` }}
                  />
                </div>
              </div>

              {/* Components Breakdown */}
              <div className="space-y-4">
                <div className="p-4 bg-gradient-to-r from-orange-50 to-red-50 rounded-lg border border-orange-200">
                  <p className="text-sm text-gray-600">Thunder Outreach</p>
                  <p className="text-2xl font-bold text-orange-600">
                    {slmHealth.components.thunder_outreach.toFixed(1)}%
                  </p>
                </div>
                <div className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
                  <p className="text-sm text-gray-600">Flash Job Match</p>
                  <p className="text-2xl font-bold text-green-600">
                    {slmHealth.components.flash_job_match.toFixed(1)}%
                  </p>
                </div>
                <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                  <p className="text-sm text-gray-600">Interview Conversion</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {slmHealth.components.interview_conversion.toFixed(1)}%
                  </p>
                </div>
                <div className="p-4 bg-gradient-to-r from-cyan-50 to-blue-50 rounded-lg border border-cyan-200">
                  <p className="text-sm text-gray-600">Offer Acceptance</p>
                  <p className="text-2xl font-bold text-cyan-600">
                    {slmHealth.components.offer_acceptance.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>

            {/* Cascade Risk Alert */}
            {slmHealth.cascade_risk && (
              <div className="mt-6 p-4 bg-red-50 border-l-4 border-red-500 rounded flex gap-4">
                <AlertCircle className="h-6 w-6 text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-red-800">Cascade Risk Detected</p>
                  <p className="text-sm text-red-700 mt-1">
                    SLM health score below 70%. System is degrading. Escalation to CEO recommended.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Channel Effectiveness Report */}
      {channelEffectiveness && (
        <Card className="bg-white shadow-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Thunder Channel Effectiveness
            </CardTitle>
            <CardDescription>
              Which outreach channels work best for candidate engagement
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {channelEffectiveness.channel_rankings?.map((channel, idx) => (
                <div key={idx} className="flex items-center gap-4">
                  <div className="text-center w-12">
                    <span className="text-2xl font-bold text-blue-600">#{channel.rank}</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-gray-700 capitalize">
                        {channel.channel}
                      </span>
                      <span className="text-sm text-gray-600">
                        {channel.samples} samples
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div
                        className="bg-gradient-to-r from-blue-400 to-blue-600 h-3 rounded-full transition-all"
                        style={{ width: `${channel.success_rate}%` }}
                      />
                    </div>
                    <p className="text-lg font-bold text-blue-600 mt-1">
                      {channel.success_rate.toFixed(1)}% success rate
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {channelEffectiveness.recommendation && (
              <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="font-semibold text-blue-900">
                  {channelEffectiveness.recommendation}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Learning Status */}
      <Card className="bg-white shadow-lg">
        <CardHeader>
          <CardTitle>Learning Status</CardTitle>
          <CardDescription>System intelligence metrics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
              <p className="text-sm text-gray-600">Thunder Operations</p>
              <p className="text-3xl font-bold text-indigo-600">50+</p>
              <p className="text-xs text-gray-500 mt-2">Outreach attempts analyzed</p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
              <p className="text-sm text-gray-600">Flash Operations</p>
              <p className="text-3xl font-bold text-purple-600">50+</p>
              <p className="text-xs text-gray-500 mt-2">Job matches evaluated</p>
            </div>
            <div className="p-4 bg-pink-50 rounded-lg border border-pink-200">
              <p className="text-sm text-gray-600">Confidence Level</p>
              <p className="text-3xl font-bold text-pink-600">70%</p>
              <p className="text-xs text-gray-500 mt-2">Learning reliability</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* How It Works */}
      <Card className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 shadow-lg">
        <CardHeader>
          <CardTitle className="text-green-900">How SLM Learning Works</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3 text-sm text-gray-700">
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 text-white flex items-center justify-center font-bold text-xs">
                1
              </span>
              <span>
                <strong>Thunder collects metrics:</strong> Every candidate outreach records channel, timing, and engagement
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 text-white flex items-center justify-center font-bold text-xs">
                2
              </span>
              <span>
                <strong>Flash learns patterns:</strong> Job-candidate matches, interview timing, offer success rates
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 text-white flex items-center justify-center font-bold text-xs">
                3
              </span>
              <span>
                <strong>Every 50 operations:</strong> Learning weights update, optimal strategies recalculated
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 text-white flex items-center justify-center font-bold text-xs">
                4
              </span>
              <span>
                <strong>System gets smarter:</strong> Recommendations become more accurate, success rates improve
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 text-white flex items-center justify-center font-bold text-xs">
                5
              </span>
              <span>
                <strong>Cascade detection:</strong> If score drops below 70%, escalate to CEO immediately
              </span>
            </li>
          </ol>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Card className="bg-red-50 border border-red-200">
          <CardContent className="pt-6">
            <div className="flex gap-4">
              <AlertCircle className="h-6 w-6 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-red-800">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default LearningDashboard;
