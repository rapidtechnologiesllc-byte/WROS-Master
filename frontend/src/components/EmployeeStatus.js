// How an employee and an allocation are shown everywhere (list, profile, allocations): the two
// axes the server derives (app/services/employee_standing.py) and an allocation's state.
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export const isPast = (emp) => emp.employment_status === "TERMINATED";
export const ON_PAYROLL = new Set(["EMPLOYED", "ON_LEAVE", "SERVING_NOTICE"]);
export const fullName = (emp) => `${emp.first_name || ""} ${emp.last_name || ""}`.trim();

export const ALLOCATION_STATUS_TONE = {
  ACTIVE: "bg-emerald-100 text-emerald-800",
  PENDING_MARGIN_APPROVAL: "bg-amber-100 text-amber-800",
  MARGIN_REJECTED: "bg-rose-100 text-rose-800",
};

export const statusLabel = (status) => (status || "").replace(/_/g, " ").toLowerCase();

// Where the employee stands, on two axes the server derives (app/services/employee_standing.py):
// employment, and for people on the payroll the deployment.
export const TONE = {
  green: "border-green-200 bg-green-50 text-green-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  blue: "border-blue-200 bg-blue-50 text-blue-800",
  purple: "border-purple-200 bg-purple-50 text-purple-800",
  grey: "border-gray-200 bg-gray-100 text-gray-600",
};
export const EMPLOYMENT = {
  JOINING: ["Joining", "blue"],
  EMPLOYED: ["Employed", "green"],
  ON_LEAVE: ["On leave", "blue"],
  SERVING_NOTICE: ["Serving notice", "amber"],
  TERMINATED: ["Terminated", "grey"],
};
export const DEPLOYMENT = {
  HTD: ["HTD", "blue"],
  BUDDY: ["Buddy Program", "purple"],
  BENCH: ["Bench", "amber"],
  PROJECT: ["On project", "green"],
  PROJECT_ENDING: ["Project ending", "amber"],
};
export const Pill = ({ tone, children }) => <span className={cx(pill, "whitespace-nowrap", TONE[tone])}>{children}</span>;

export function EmploymentStatus({ employee }) {
  const [label, tone] = EMPLOYMENT[employee.employment_status] || [statusLabel(employee.employment_status), "grey"];
  return <Pill tone={tone}>{label}</Pill>;
}

export function DeploymentStatus({ employee }) {
  const status = employee.deployment_status;
  if (!status) return <span className="text-gray-400">—</span>;
  const [label, tone] = DEPLOYMENT[status] || [statusLabel(status), "grey"];
  let detail = null;
  if (status === "BENCH" && employee.deployment_days != null) detail = `${employee.deployment_days}d on bench`;
  if (status === "PROJECT_ENDING") detail = `ends ${employee.deployment_until} (${employee.deployment_days}d)`;
  if (status === "PROJECT" && employee.deployment_until) detail = `until ${employee.deployment_until}`;
  return (
    <div>
      <Pill tone={tone}>{label}</Pill>
      {detail ? <div className="mt-0.5 whitespace-nowrap text-xs text-gray-500">{detail}</div> : null}
    </div>
  );
}

// An allocation's state: the record's status, sharpened for active ones by the ending window and
// the renewal decision.
export const RENEWAL_LABEL = { IN_DISCUSSION: "renewal in discussion", EXTENDED: "extension agreed", ROLLING_OFF: "rolling off" };
export function AllocationState({ alloc }) {
  let label = statusLabel(alloc.status);
  let tone = ALLOCATION_STATUS_TONE[alloc.status] || "bg-gray-100 text-gray-700";
  if (alloc.status === "ACTIVE" && alloc.ending_soon) {
    label = alloc.days_left < 0 ? `past end ${-alloc.days_left}d` : `ending in ${alloc.days_left}d`;
    tone = "bg-amber-100 text-amber-800";
  }
  return (
    <div>
      <span className={cx("whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold", tone)}>{label}</span>
      {alloc.status === "ACTIVE" && RENEWAL_LABEL[alloc.renewal_status] && (
        <div className="mt-1 whitespace-nowrap text-xs text-gray-500">{RENEWAL_LABEL[alloc.renewal_status]}</div>
      )}
    </div>
  );
}
