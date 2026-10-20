import { useEffect, useState } from "react";
import { Gift, Briefcase, Clock, CheckCircle2, AlertCircle, TrendingUp, Plus, X, AlertTriangle } from "lucide-react";
import { Card, Button } from "../components/ui";
import { useNavigate } from "react-router-dom";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { getMyReferrals } from "../services/api/referrals";

const STATUS_COLORS = {
  PENDING: "bg-yellow-100 text-yellow-800",
  SCREENING: "bg-blue-100 text-blue-800",
  INTERVIEW_SCHEDULED: "bg-purple-100 text-purple-800",
  OFFERED: "bg-amber-100 text-amber-800",
  HIRED: "bg-green-100 text-green-800",
  BONUS_PAID: "bg-emerald-100 text-emerald-800",
  REJECTED: "bg-red-100 text-red-800",
};

const STATUS_ICONS = {
  PENDING: Clock,
  SCREENING: AlertCircle,
  INTERVIEW_SCHEDULED: Briefcase,
  OFFERED: Briefcase,
  HIRED: CheckCircle2,
  BONUS_PAID: Gift,
  REJECTED: AlertCircle,
};

// Stages a referral moves through (backend: PIPELINE_TO_REFERRAL_STATUS)
const TIMELINE = [
  { status: "PENDING", label: "Referred" },
  { status: "SCREENING", label: "Screening" },
  { status: "INTERVIEW_SCHEDULED", label: "Interview" },
  { status: "OFFERED", label: "Offer" },
  { status: "HIRED", label: "Hired" },
  { status: "BONUS_PAID", label: "Bonus Paid" },
];

export default function MyReferralsScreen() {
  const navigate = useNavigate();
  const [referrals, setReferrals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState(null);
  const [stats, setStats] = useState({
    totalReferrals: 0,
    totalPotentialBonus: 0,
  });

  useEffect(() => {
    loadMyReferrals();
  }, []);

  const loadMyReferrals = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const data = await getMyReferrals();

      setReferrals(data.referrals || []);
      setStats({
        totalReferrals: data.total_referrals || 0,
        totalPotentialBonus: data.total_potential_bonus || 0,
      });
    } catch (err) {
      setActionError(err.message || "Failed to load referrals");
      setReferrals([]);
    } finally {
      setLoading(false);
    }
  };

  const handleReferCandidate = () => {
    if (!hasPermission("candidates", "create")) {
      setActionError("You don't have permission to create candidates");
      return;
    }
    // Add Candidate opens with source "Employee Referral" and you as the referrer
    navigate("/candidates/create?referral=1");
  };

  return (
    <div className="space-y-6">
      {actionError && (
        <div className="flex items-start gap-3 rounded-lg bg-red-50 px-4 py-3 border border-red-200">
          <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">{actionError}</p>
          </div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="flex-shrink-0 text-red-400 hover:text-red-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">My Referrals</h1>
          <p className="text-gray-600 mt-1">Track your referrals and potential bonuses</p>
        </div>
        <div className="flex gap-2">
          {hasPermission("candidates", "create") && (
            <Button variant="primary" onClick={handleReferCandidate}>
              <Plus className="h-4 w-4 mr-2" /> Refer a Candidate
            </Button>
          )}
          <Button variant="ghost" onClick={loadMyReferrals}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Referrals</p>
              <p className="text-4xl font-bold mt-2">{stats.totalReferrals}</p>
            </div>
            <Briefcase className="h-12 w-12 text-blue-500 opacity-20" />
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Potential Bonus</p>
              <p className="text-4xl font-bold mt-2">${Number(stats.totalPotentialBonus).toFixed(2)}</p>
            </div>
            <Gift className="h-12 w-12 text-green-500 opacity-20" />
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Conversion Rate</p>
              <p className="text-4xl font-bold mt-2">
                {stats.totalReferrals > 0
                  ? Math.round((referrals.filter(r => ["HIRED", "BONUS_PAID"].includes(r.referral_status)).length / stats.totalReferrals) * 100)
                  : 0}%
              </p>
            </div>
            <TrendingUp className="h-12 w-12 text-purple-500 opacity-20" />
          </div>
        </Card>
      </div>

      {/* Referrals List */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Your Referrals</h2>

        {loading ? (
          <div className="text-center text-gray-500 py-8">Loading your referrals...</div>
        ) : referrals.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p className="mb-2">You haven't referred any candidates yet.</p>
            <p className="text-sm">Click "Refer a Candidate" to add someone you know, with you as the referrer.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {referrals.map((referral) => {
              const status = referral.referral_status || "PENDING";
              const StatusIcon = STATUS_ICONS[status] || AlertCircle;
              const statusColor = STATUS_COLORS[status] || "bg-gray-100 text-gray-800";

              return (
                <div key={referral.referral_id} className="border rounded-lg p-4 hover:bg-gray-50 transition">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-semibold text-lg">{referral.referred_candidate_name}</h3>
                        <span className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 ${statusColor}`}>
                          <StatusIcon className="h-3 w-3" />
                          {status.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{referral.referred_candidate_email}</p>
                      <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-gray-600">
                        <span>💼 {referral.job_title || "No specific job"}</span>
                        <span>👤 Referred by {referral.referring_employee_name}</span>
                        <span>📅 {referral.created_at ? new Date(referral.created_at).toLocaleDateString() : ""}</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="flex items-center gap-1">
                        <Gift className="h-4 w-4 text-green-600" />
                        <span className="font-bold text-lg">${Number(referral.referral_bonus_amount || 0).toFixed(2)}</span>
                      </div>
                      {referral.bonus_paid ? (
                        <p className="text-xs text-green-600 font-medium mt-1">✓ Bonus Paid</p>
                      ) : status === "REJECTED" ? (
                        <p className="text-xs text-gray-500 mt-1">Not eligible</p>
                      ) : status === "SUPERSEDED" ? (
                        <p className="text-xs text-gray-500 mt-1">Replaced by a later referral</p>
                      ) : status === "HIRED" ? (
                        <p className="text-xs text-blue-600 font-medium mt-1">⏳ Pending Payment</p>
                      ) : (
                        <p className="text-xs text-gray-500 mt-1">Potential</p>
                      )}
                    </div>
                  </div>

                  {/* Status Timeline */}
                  <div className="mt-4 pt-4 border-t">
                    <p className="text-xs text-gray-600 font-medium mb-2">Timeline</p>
                    <div className="flex flex-wrap gap-2 text-xs">
                      {status === "REJECTED" ? (
                        <>
                          <span className="bg-gray-100 text-gray-700 px-2 py-1 rounded">Referred</span>
                          <span className="bg-red-100 text-red-700 px-2 py-1 rounded">Not selected</span>
                        </>
                      ) : (
                        TIMELINE.slice(0, Math.max(TIMELINE.findIndex((s) => s.status === status), 0) + 1).map((step) => (
                          <span
                            key={step.status}
                            className={`px-2 py-1 rounded ${step.status === status ? (STATUS_COLORS[status] || "bg-green-100 text-green-700") : "bg-gray-100 text-gray-700"}`}
                          >
                            {step.label}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Info Section */}
      <Card className="p-6 bg-blue-50 border-blue-200">
        <h3 className="font-semibold text-blue-900 mb-2">💡 How It Works</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Refer a candidate, for an open job or in general</li>
          <li>✓ They go through our screening and interview process; their progress shows here</li>
          <li>✓ If hired, you earn the referral bonus shown for that referral</li>
          <li>✓ Bonus is paid 90 days after they start</li>
        </ul>
      </Card>
    </div>
  );
}
