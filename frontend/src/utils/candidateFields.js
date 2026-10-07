// One definition of the candidate fields' choices and storage formats,
// shared by Add Candidate and the profile's edit sections so a value saved
// in one is always shown and editable in the other.

export const GENDER_OPTIONS = ["Female", "Male", "Other", "Prefer not to say"];

export const SOURCE_OPTIONS = [
  "LinkedIn", "Career Site", "Employee Referral", "Campus Hiring", "Conference",
  "Indeed", "Naukri", "Monster", "Job Board", "Direct Application", "Other",
];

export const SALARY_RATE_TYPES = ["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year"];
export const DEFAULT_SALARY_RATE_TYPE = "$/Year";

export const EDUCATION_LEVELS = [
  "High School", "Diploma", "Bachelor", "Master", "PhD", "Postdoctoral", "Certificate", "Other",
];

// Source is stored as one string; a value outside the list is a custom
// "Other" source. Returns { choice, custom } for the two form controls.
export function splitSource(stored) {
  if (!stored) return { choice: "", custom: "" };
  return SOURCE_OPTIONS.includes(stored) ? { choice: stored, custom: "" } : { choice: "Other", custom: stored };
}

export function joinSource(choice, custom) {
  if (choice === "Other") return (custom || "").trim() || "Other";
  return choice || "";
}

// Years in a role from its dates (end empty = current job); mirrors the
// backend's experience_years so Add shows what will be stored.
export function experienceYears(startDate, endDate) {
  if (!startDate) return "";
  const start = new Date(startDate);
  const end = endDate ? new Date(endDate) : new Date();
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return "";
  return String(Math.round(((end - start) / (365.25 * 24 * 3600 * 1000)) * 10) / 10);
}
