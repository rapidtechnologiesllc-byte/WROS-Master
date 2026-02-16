// Status badge with color mapping.
import cx from "../../utils/cx";
import { pill } from "../../utils/pill";

export default function StatusBadge({ status }) {
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
    Closed: "border-gray-200 bg-gray-50 text-gray-700",
    Requested: "border-indigo-200 bg-indigo-50 text-indigo-800",
    Scheduled: "border-purple-200 bg-purple-50 text-purple-800",
    Completed: "border-green-200 bg-green-50 text-green-800",
    Negotiation: "border-amber-200 bg-amber-50 text-amber-800",
    Sent: "border-blue-200 bg-blue-50 text-blue-800",
    Accepted: "border-green-200 bg-green-50 text-green-800",
    Declined: "border-red-200 bg-red-50 text-red-800"
  };

  return <span className={cx(pill, map[status] || map.Draft)}>{status}</span>;
}
