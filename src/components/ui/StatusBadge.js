// Status badge with color mapping.
import cx from "../../utils/cx";
import { pill } from "../../utils/pill";

export default function StatusBadge({ status, value }) {
  const finalStatus = status || value;
  const map = {
    New: "border-gray-200 bg-gray-50 text-gray-800",
    Applied: "border-blue-200 bg-blue-50 text-blue-800",
    "Interview Scheduled": "border-purple-200 bg-purple-50 text-purple-800",
    Selected: "border-green-200 bg-green-50 text-green-800",
    Rejected: "border-red-200 bg-red-50 text-red-800",
    "Offer Sent": "border-amber-200 bg-amber-50 text-amber-800",
    "Offer Accepted": "border-green-200 bg-green-50 text-green-800",
    "Offer Declined": "border-red-200 bg-red-50 text-red-800",
    Draft: "border-gray-200 bg-gray-50 text-gray-800",
    Submitted: "border-indigo-200 bg-indigo-50 text-indigo-800",
    Open: "border-green-200 bg-green-50 text-green-800",
    Public: "border-green-200 bg-green-50 text-green-800",
    active: "border-green-200 bg-green-50 text-green-800",
    public: "border-green-200 bg-green-50 text-green-800",
    Pending: "border-amber-200 bg-amber-50 text-amber-800",
    Verified: "border-green-200 bg-green-50 text-green-800",
    Cancelled: "border-red-200 bg-red-50 text-red-800",
    "Offer Cancelled": "border-red-200 bg-red-50 text-red-800",
    Closed: "border-gray-200 bg-gray-50 text-gray-700",
    Requested: "border-indigo-200 bg-indigo-50 text-indigo-800",
    Scheduled: "border-purple-200 bg-purple-50 text-purple-800",
    Completed: "border-green-200 bg-green-50 text-green-800",
    Negotiation: "border-amber-200 bg-amber-50 text-amber-800",
    Sent: "border-blue-200 bg-blue-50 text-blue-800",
    Accepted: "border-green-200 bg-green-50 text-green-800",
    Declined: "border-red-200 bg-red-50 text-red-800",
    Screening: "border-blue-200 bg-blue-50 text-blue-800",
    Interview: "border-purple-200 bg-purple-50 text-purple-800",
    "Pre-Onboarding": "border-amber-200 bg-amber-50 text-amber-900",
    Onboarded: "border-green-200 bg-green-50 text-green-900",
    Hired: "border-green-200 bg-green-50 text-green-900",
    Active: "border-green-200 bg-green-50 text-green-800",
    Inactive: "border-gray-200 bg-gray-100 text-gray-600"
  };

  let key = status;
  const raw = String(finalStatus || "");
  const lower = raw.toLowerCase();

  if (lower.includes("offer cancelled")) key = "Offer Cancelled";
  else if (lower.includes("cancelled")) key = "Cancelled";
  else if (lower === "completed") key = "Completed";
  else if (lower === "active") key = "Requested";
  else if (lower.includes("verified")) key = "Verified";
  else if (lower.includes("pending")) key = "Pending";

  return <span className={cx(pill, map[key] || map.Draft)}>{finalStatus}</span>;
}
