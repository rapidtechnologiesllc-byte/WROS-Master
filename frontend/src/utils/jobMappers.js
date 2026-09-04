/**
 * Utility functions for mapping job data from API responses
 */

export const mapJobFromApi = (j, users = []) => {
  const usersList = Array.isArray(users) ? users : [];
  const hmId = j?.hiring_manager_id || "";
  const hmUser = usersList.find(
    (u) => String(u?.user_id || "") === String(hmId || "")
  );
  const hiringManagerName =
    hmUser?.user_name || hmUser?.user_email || (hmId ? String(hmId) : "");

  return ({
  id: j.job_id,
  title: j.job_title,
  dept: "",
  location: j.job_location || "",
  skills: String(j.job_skills || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  hiringManager: hmId,
  hiringManagerName,
  status: (() => {
    const raw = String(j.job_status || "").trim().toLowerCase();
    if (raw === "active") return "Open";
    if (raw === "public") return "Public";
    if (raw === "draft") return "Draft";
    if (raw === "submitted") return "Submitted";
    if (raw === "closed") return "Closed";
    return j.job_status || "Draft";
  })(),
  experienceLevel: j.job_experience || "",
  companyType: j.company_type || "",
  companyClient: j.company_name || "",
  contactPerson: j.contact_person || "",
  startDate: j.start_date || "",
  endDate: j.end_date || "",
  jobDescription: j.job_description || ""
});
};
