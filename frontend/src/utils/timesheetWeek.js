// The seven days of a timesheet week, in local calendar dates (toISOString() would shift to UTC
// and give the previous day east of UTC).
export function weekDays(weekStartingDate) {
  const start = new Date(`${weekStartingDate}T00:00:00`);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  });
}

const at = (isoDate) => new Date(`${isoDate}T00:00:00`);

// "Mon" and "Nov 9": the day and its date, so nobody has to count from the week's Monday
export const dayName = (isoDate) => at(isoDate).toLocaleDateString(undefined, { weekday: "short" });
export const dayDate = (isoDate) => at(isoDate).toLocaleDateString(undefined, { month: "short", day: "numeric" });

// "Nov 9 - Nov 15, 2026"
export function weekRange(weekStartingDate) {
  const days = weekDays(weekStartingDate);
  return `${dayDate(days[0])} - ${dayDate(days[6])}, ${at(days[6]).getFullYear()}`;
}

export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Where the time is logged, as a coloured tag: Staff Aug, Project, Accelerator, Certification...
export const WORK_TYPE_STYLES = {
  STAFF_AUG: "border-blue-200 bg-blue-50 text-blue-800",
  PROJECT: "border-indigo-200 bg-indigo-50 text-indigo-800",
  BENCH: "border-amber-200 bg-amber-50 text-amber-800",
  INTERNAL_TASK: "border-gray-200 bg-gray-50 text-gray-700",
};
