import { useEffect, useState } from "react";
import { Gift, Briefcase, Clock, CheckCircle2, AlertCircle, TrendingUp, Plus } from "lucide-react";
import { Card, Button } from "../components/ui";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";

const STATUS_COLORS = {
  PENDING: "bg-yellow-100 text-yellow-800",
  SCREENING: "bg-blue-100 text-blue-800",
  INTERVIEW_SCHEDULED: "bg-purple-100 text-purple-800",
  HIRED: "bg-green-100 text-green-800",
  BONUS_PAID: "bg-emerald-100 text-emerald-800",
  REJECTED: "bg-red-100 text-red-800",
};

const STATUS_ICONS = {
  PENDING: Clock,
  SCREENING: AlertCircle,
  INTERVIEW_SCHEDULED: Briefcase,
  HIRED: CheckCircle2,
  BONUS_PAID: Gift,
  REJECTED: AlertCircle,
};

export default function MyReferralsScreen() {
  const navigate = useNavigate();
  const [referrals, setReferrals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalReferrals: 0,
    totalPotentialBonus: 0,
    employeeName: "",
  });

  useEffect(() => {
    loadMyReferrals();
  }, []);

  const loadMyReferrals = async () => {
    setLoading(true);
    try {
      const response = await fetch("/referrals/my-referrals", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });

      if (!response.ok) throw new Error("Failed to load referrals");

      const data = await response.json();

      setReferrals(data.referrals || []);
      setStats({
        totalReferrals: data.total_referrals || 0,
        totalPotentialBonus: data.total_potential_bonus || 0,
        employeeName: data.employee_name || "You",
      });
    } catch (err) {
      toast.error(err.message);
      setReferrals([]);
    } finally {
      setLoading(false);
    }
  };

  const handleReferCandidate = () => {
    // Mark that we're coming from referrals so we can redirect back
    sessionStorage.setItem("referralRedirect", "true");
    navigate("/candidates/create");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">My Referrals</h1>
          <p className="text-gray-600 mt-1">Track your referrals and potential bonuses</p>
        </div>
        <div className="flex gap-2">
          <Button variant="primary" onClick={handleReferCandidate}>
            <Plus className="h-4 w-4 mr-2" /> Refer a Candidate
          </Button>
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
              <p className="text-4xl font-bold mt-2">${(stats.totalPotentialBonus / 100).toFixed(2)}</p>
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
                  ? Math.round((referrals.filter(r => r.status === "HIRED").length / stats.totalReferrals) * 100)
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
            <p className="text-sm">Start by opening a job and using the referral form to refer someone!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {referrals.map((referral) => {
              const StatusIcon = STATUS_ICONS[referral.status] || AlertCircle;
              const statusColor = STATUS_COLORS[referral.status] || "bg-gray-100 text-gray-800";

              return (
                <div key={referral.referral_id} className="border rounded-lg p-4 hover:bg-gray-50 transition">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-semibold text-lg">{referral.candidate_name}</h3>
                        <span className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 ${statusColor}`}>
                          <StatusIcon className="h-3 w-3" />
                          {referral.status.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{referral.candidate_email}</p>
                      <div className="flex items-center gap-4 mt-3 text-sm text-gray-600">
                        <span>💼 Job ID: {referral.job_id}</span>
                        <span>📅 {new Date(referral.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="flex items-center gap-1">
                        <Gift className="h-4 w-4 text-green-600" />
                        <span className="font-bold text-lg">${(referral.bonus_potential / 100).toFixed(2)}</span>
                      </div>
                      {referral.bonus_paid ? (
                        <p className="text-xs text-green-600 font-medium mt-1">✓ Bonus Paid</p>
                      ) : referral.status === "HIRED" ? (
                        <p className="text-xs text-blue-600 font-medium mt-1">⏳ Pending Payment</p>
                      ) : (
                        <p className="text-xs text-gray-500 mt-1">Potential</p>
                      )}
                    </div>
                  </div>

                  {/* Status Timeline */}
                  <div className="mt-4 pt-4 border-t">
                    <p className="text-xs text-gray-600 font-medium mb-2">Timeline</p>
                    <div className="flex gap-2 text-xs">
                      <span className="bg-green-100 text-green-700 px-2 py-1 rounded">Referred</span>
                      {["SCREENING", "INTERVIEW_SCHEDULED", "HIRED", "BONUS_PAID"].includes(referral.status) && (
                        <span className={`px-2 py-1 rounded ${["SCREENING"].includes(referral.status) ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-700"}`}>
                          Screening
                        </span>
                      )}
                      {["INTERVIEW_SCHEDULED", "HIRED", "BONUS_PAID"].includes(referral.status) && (
                        <span className={`px-2 py-1 rounded ${["INTERVIEW_SCHEDULED"].includes(referral.status) ? "bg-purple-100 text-purple-700" : "bg-gray-100 text-gray-700"}`}>
                          Interview
                        </span>
                      )}
                      {["HIRED", "BONUS_PAID"].includes(referral.status) && (
                        <span className={`px-2 py-1 rounded ${["HIRED"].includes(referral.status) ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}`}>
                          Hired
                        </span>
                      )}
                      {["BONUS_PAID"].includes(referral.status) && (
                        <span className="bg-emerald-100 text-emerald-700 px-2 py-1 rounded">Bonus Paid</span>
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
          <li>✓ Refer a candidate for an open job</li>
          <li>✓ They go through our screening and interview process</li>
          <li>✓ If hired, you earn a bonus based on their experience level</li>
          <li>✓ Bonus is paid 90 days after they start</li>
        </ul>
      </Card>
    </div>
  );
}
