// Candidate portal for personal info, education, experience, and documents.
import { useEffect, useMemo, useState } from "react";
import { ListChecks } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge, TextArea } from "../components/ui";
import {
  addCandidateEducation,
  addCandidateExperience,
  changeCandidatePassword,
  deleteCandidateEducation,
  deleteCandidateExperience,
  getCandidateAadhar,
  getCandidateMyInfo,
  getCandidateOnboardingStatus,
  getCandidatePan,
  getCandidatePersonalInfo,
  listCandidateEducation,
  listCandidateExperience,
  submitCandidateAadharForm,
  submitCandidateInfoForm,
  submitCandidatePanForm,
  updateCandidateEducation,
  updateCandidateExperience
} from "../services/api/candidateSelfService";
import { getMyOffers, respondToOffer } from "../services/api/offerLetters";
import {
  uploadPan,
  uploadAadhar,
  uploadEducationCertificate,
  uploadExperienceLetter,
  uploadSalarySlip,
  uploadBankStatement,
  getMyDocuments,
  viewDocument
} from "../services/api/documents";
import { getActiveJobs, applyForJob } from "../services/api/jobs";
import {
  candidateCompleteChecklistItem,
  getMyChecklists
} from "../services/api/checklists";

const today = () => new Date().toISOString().slice(0, 10);

const DOC_LABELS = {
  resume: "Resume",
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement"
};

function canCandidateCompleteItem(item) {
  if (!item || item.status === "completed") return false;
  if (item.item_type === "todo") return item.status === "pending";
  if (item.item_type === "queue") return item.status === "active";
  return false;
}

const normalizeJobStatus = (rawStatus) => {
  const raw = String(rawStatus || "").trim().toLowerCase();
  if (raw === "active") return "Open";
  if (raw === "public") return "Public";
  if (raw === "draft") return "Draft";
  if (raw === "submitted") return "Submitted";
  if (raw === "closed") return "Closed";
  return rawStatus || "Draft";
};

function DocumentUploadRow({ label, onUpload, disabled }) {
  const [file, setFile] = useState(null);
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-slate-50 p-3">
      <span className="text-sm font-medium flex-1">{label}</span>
      <input
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        onChange={(e) => setFile(e.target.files?.[0])}
        className="text-xs"
      />
      <Button
        variant="secondary"
        onClick={() => file && onUpload(file)}
        disabled={!file || disabled}
      >
        Upload
      </Button>
    </div>
  );
}

export default function CandidateSelfService({ onLogout }) {
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [profile, setProfile] = useState(null);
  const [onboardingStatus, setOnboardingStatus] = useState(null);
  const [passwordForm, setPasswordForm] = useState({
    new_password: "",
    confirm_password: ""
  });
  const [myOffers, setMyOffers] = useState([]);
  const [myDocuments, setMyDocuments] = useState(null);
  const [activeJobs, setActiveJobs] = useState([]);
  const [jobResumeFile, setJobResumeFile] = useState(null);
  const [myChecklistsPayload, setMyChecklistsPayload] = useState(null);
  const [checklistCompletingId, setChecklistCompletingId] = useState(null);
  const storedCandidateName = localStorage.getItem("hrms_user_name") || "";
  const storedCandidateEmail = localStorage.getItem("hrms_user_email") || "";

  // Normalize backend records into UI-friendly state shape.
  const normalizeEducationRecord = (record = {}) => ({
    id: record.formID ?? record.id ?? null,
    education_institute: record.education_institute || "",
    degree: record.degree || "",
    field_of_study: record.field_of_study || "",
    starting_year: record.starting_year || "",
    year_of_passing: record.year_of_passing || "",
    percentage: record.percentage || "",
    submitted_at: record.submitted_at || record.submittedAt || today(),
    document_is_submitted: Boolean(record.document_is_submitted)
  });

  const normalizeExperienceRecord = (record = {}) => ({
    id: record.formID ?? record.id ?? null,
    company_name: record.company_name || "",
    job_title: record.job_title || "",
    start_date: record.start_date || "",
    end_date: record.end_date || "",
    year_of_experience: record.year_of_experience || "",
    submitted_at: record.submitted_at || record.submittedAt || today(),
    document_is_submitted: Boolean(record.document_is_submitted)
  });

  // Convert UI state back to backend payloads.
  const toEducationPayload = (record) => ({
    education_institute: record.education_institute,
    degree: record.degree,
    field_of_study: record.field_of_study,
    starting_year: record.starting_year,
    year_of_passing: record.year_of_passing,
    percentage: record.percentage,
    submitted_at: record.submitted_at || today(),
    document_is_submitted: Boolean(record.document_is_submitted)
  });

  const toExperiencePayload = (record) => ({
    company_name: record.company_name,
    job_title: record.job_title,
    start_date: record.start_date,
    end_date: record.end_date,
    year_of_experience: record.year_of_experience,
    submitted_at: record.submitted_at || today(),
    document_is_submitted: Boolean(record.document_is_submitted)
  });

  const handleViewDocument = async (documentId) => {
    try {
      const { blob } = await viewDocument(documentId);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 15000);
    } catch (err) {
      setNotice(err.message || "Failed to view document.");
    }
  };

  const handleApplyForJob = async (jobId) => {
    if (!jobId) return;
    if (!profile?.candidate_email) {
      setNotice("Candidate email is missing. Please login again.");
      return;
    }
    if (!profile?.candidate_mobile) {
      setNotice("Candidate phone is missing. Please update your phone number before applying.");
      return;
    }

    try {
      setNotice("");
      const educationEntries = (education || [])
        .filter((e) => e.education_institute || e.degree || e.field_of_study)
        .map((e) => ({
          institution: e.education_institute,
          degree: e.degree,
          field_of_study: e.field_of_study,
          start_year: e.starting_year,
          end_year: e.year_of_passing,
          percentage: e.percentage || null
        }));

      const experienceEntries = (experience || [])
        .filter((e) => e.company_name || e.job_title)
        .map((e) => ({
          company_name: e.company_name,
          job_title: e.job_title,
          start_date: e.start_date,
          end_date: e.end_date || null,
          years_of_experience: e.year_of_experience || null
        }));

      const res = await applyForJob({
        jobId,
        fullName: profile?.candidate_name || "Candidate",
        email: profile?.candidate_email,
        phone: profile?.candidate_mobile,
        educationEntries,
        experienceEntries,
        resumeFile: jobResumeFile
      });

      setNotice(res?.message || "Applied successfully.");
    } catch (err) {
      setNotice(err.message || "Failed to apply for job.");
    }
  };

  const [personal, setPersonal] = useState({
    position: "",
    department: "",
    dob: "",
    gender: "",
    marital_status: "",
    nationality: "",
    current_address: "",
    permanent_address: "",
    submitted_at: today()
  });

  const [education, setEducation] = useState([
    {
      id: null,
      education_institute: "",
      degree: "",
      field_of_study: "",
      starting_year: "",
      year_of_passing: "",
      percentage: "",
      submitted_at: today(),
      document_is_submitted: false
    }
  ]);

  const [experience, setExperience] = useState([
    {
      id: null,
      company_name: "",
      job_title: "",
      start_date: "",
      end_date: "",
      year_of_experience: "",
      submitted_at: today(),
      document_is_submitted: false
    }
  ]);

  const [aadhar, setAadhar] = useState({
    aadhar: "",
    name_in_aadhar: "",
    enrollment_number: "",
    aadhar_is_submitted: false,
    submitted_at: today(),
    is_verified: false
  });

  const [pan, setPan] = useState({
    pan: "",
    name_in_pan: "",
    father_name_in_pan: "",
    pan_is_submitted: false,
    submitted_at: today(),
    is_verified: false
  });

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setLoading(true);
      try {
        // Load all candidate profile slices in parallel.
        const [
          myInfoResult,
          personalResult,
          educationResult,
          experienceResult,
          aadharResult,
          panResult,
          onboardingResult,
          offersResult,
          documentsResult,
          jobsResult,
          checklistsResult
        ] = await Promise.allSettled([
          getCandidateMyInfo(),
          getCandidatePersonalInfo(),
          listCandidateEducation(),
          listCandidateExperience(),
          getCandidateAadhar(),
          getCandidatePan(),
          getCandidateOnboardingStatus(),
          getMyOffers(),
          getMyDocuments(),
          getActiveJobs(),
          getMyChecklists()
        ]);

        if (!isMounted) return;

        if (myInfoResult.status === "fulfilled") {
          setProfile(myInfoResult.value);
        }

        if (personalResult.status === "fulfilled" && personalResult.value) {
          setPersonal((prev) => ({
            ...prev,
            ...personalResult.value,
            dob: personalResult.value.dob || prev.dob,
            submitted_at: today()
          }));
        }

        if (
          educationResult.status === "fulfilled" &&
          educationResult.value?.records?.length
        ) {
          setEducation(educationResult.value.records.map(normalizeEducationRecord));
        }

        if (
          experienceResult.status === "fulfilled" &&
          experienceResult.value?.records?.length
        ) {
          setExperience(experienceResult.value.records.map(normalizeExperienceRecord));
        }

        if (aadharResult.status === "fulfilled" && aadharResult.value) {
          setAadhar((prev) => ({
            ...prev,
            ...aadharResult.value,
            submitted_at: today()
          }));
        }

        if (panResult.status === "fulfilled" && panResult.value) {
          setPan((prev) => ({
            ...prev,
            ...panResult.value,
            submitted_at: today()
          }));
        }

        if (onboardingResult.status === "fulfilled" && onboardingResult.value) {
          setOnboardingStatus(onboardingResult.value);
        }

        if (offersResult.status === "fulfilled" && offersResult.value?.offers) {
          setMyOffers(offersResult.value.offers);
        }

        if (documentsResult.status === "fulfilled" && documentsResult.value) {
          setMyDocuments(documentsResult.value);
        }

        if (jobsResult.status === "fulfilled" && jobsResult.value) {
          setActiveJobs(Array.isArray(jobsResult.value?.jobs) ? jobsResult.value.jobs : []);
        }

        if (checklistsResult.status === "fulfilled" && checklistsResult.value) {
          setMyChecklistsPayload(checklistsResult.value);
        }

        const errors = [
          myInfoResult,
          personalResult,
          educationResult,
          experienceResult,
          aadharResult,
          panResult,
          onboardingResult,
          offersResult,
          documentsResult,
          jobsResult,
          checklistsResult
        ]
          .filter((result) => result.status === "rejected")
          .map((result) => result.reason);

        if (errors.length) {
          setNotice(errors[0]?.message || "Failed to load some data.");
        }
      } catch (err) {
        if (!isMounted) return;
        setNotice(err.message || "Failed to load candidate profile.");
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  const candidateName = useMemo(() => {
    return profile?.candidate_name || storedCandidateName || "Candidate";
  }, [profile, storedCandidateName]);

  const candidateEmail = useMemo(() => {
    return profile?.candidate_email || storedCandidateEmail || "";
  }, [profile, storedCandidateEmail]);

  const checklistList = myChecklistsPayload?.checklists || [];
  const profilePipeline = String(
    profile?.pipeline_status || profile?.pipline_status || profile?.status || ""
  )
    .trim()
    .toLowerCase();
  const isPreBoarding = profilePipeline.includes("pre");
  const shouldShowChecklists = checklistList.length > 0 || isPreBoarding;

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold text-slate-500">Candidate Portal</div>
            <div className="text-xl font-bold">{candidateName}</div>
            {candidateEmail ? (
              <div className="text-xs text-slate-500">{candidateEmail}</div>
            ) : null}
          </div>
          <Button variant="secondary" onClick={onLogout}>
            Logout
          </Button>
        </div>

        {notice ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {notice}
          </div>
        ) : null}

        {myOffers?.length > 0 ? (
          <Card title="Offer Letters">
            <div className="space-y-3">
              {myOffers.map((o) => (
                <div
                  key={o.id}
                  className="rounded-lg border bg-slate-50 p-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold">{o.position}</div>
                      <div className="text-xs text-slate-600">
                        Salary: ${o.salary} | Joining: {o.joining_date}
                      </div>
                      <div className="mt-1 text-xs">
                        Status: <span className="font-medium">{o.offer_status}</span>
                      </div>
                    </div>
                    {o.offer_status === "Pending" ? (
                      <div className="flex gap-2">
                        <Button
                          variant="danger"
                          onClick={async () => {
                            setNotice("");
                            try {
                              await respondToOffer({
                                offerId: o.id,
                                action: "reject"
                              });
                              const refreshed = await getMyOffers();
                              setMyOffers(refreshed?.offers || []);
                              setNotice("Offer declined.");
                            } catch (err) {
                              setNotice(err.message || "Failed to decline offer.");
                            }
                          }}
                          disabled={loading}
                        >
                          Decline
                        </Button>
                        <Button
                          onClick={async () => {
                            setNotice("");
                            try {
                              await respondToOffer({
                                offerId: o.id,
                                action: "accept"
                              });
                              const refreshed = await getMyOffers();
                              setMyOffers(refreshed?.offers || []);
                              setNotice("Offer accepted!");
                            } catch (err) {
                              setNotice(err.message || "Failed to accept offer.");
                            }
                          }}
                          disabled={loading}
                        >
                          Accept
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        {shouldShowChecklists ? (
          <Card title="My checklists" icon={<ListChecks className="h-4 w-4" />}>
            {checklistList.length ? (
              <>
                <p className="mb-3 text-sm text-slate-600">
                  Complete assigned tasks. Queue steps unlock in order.
                </p>
                <div className="space-y-4">
                  {checklistList.map((cl) => (
                    <div key={cl.id} className="rounded-xl border bg-white p-3">
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <div className="font-semibold text-slate-900">
                          {cl.template_name || `Checklist ${cl.id}`}
                        </div>
                        <StatusBadge status={cl.status === "completed" ? "Completed" : "Scheduled"} />
                      </div>
                      <ul className="space-y-2">
                        {(cl.items || [])
                          .slice()
                          .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
                          .map((item) => {
                            const actionable = canCandidateCompleteItem(item);
                            const waitingQueue =
                              item.item_type === "queue" &&
                              item.status === "pending" &&
                              !actionable;
                            return (
                              <li
                                key={item.id}
                                className="flex flex-col gap-2 rounded-lg border border-slate-100 bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between"
                              >
                                <div>
                                  <div className="text-sm font-medium">{item.title}</div>
                                  {item.description ? (
                                    <div className="text-xs text-slate-600">{item.description}</div>
                                  ) : null}
                                  <div className="mt-1">
                                    <StatusBadge status={item.status} />
                                  </div>
                                  {waitingQueue ? (
                                    <div className="mt-1 text-xs text-amber-700">Awaiting previous step</div>
                                  ) : null}
                                </div>
                                {item.status !== "completed" ? (
                                  <Button
                                    variant="secondary"
                                    onClick={async () => {
                                      setNotice("");
                                      setChecklistCompletingId(item.id);
                                      try {
                                        await candidateCompleteChecklistItem(item.id);
                                        const refreshed = await getMyChecklists();
                                        setMyChecklistsPayload(refreshed);
                                        setNotice("Task marked complete.");
                                      } catch (err) {
                                        setNotice(err.message || "Could not complete task.");
                                      } finally {
                                        setChecklistCompletingId(null);
                                      }
                                    }}
                                    disabled={!actionable || checklistCompletingId === item.id}
                                  >
                                    {checklistCompletingId === item.id ? "Saving…" : "Mark complete"}
                                  </Button>
                                ) : (
                                  <span className="text-xs font-semibold text-green-700">Done</span>
                                )}
                              </li>
                            );
                          })}
                      </ul>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="rounded-lg border bg-slate-50 p-3 text-sm text-slate-600">
                No checklist assigned yet.
              </div>
            )}
          </Card>
        ) : null}

        {onboardingStatus ? (
          <Card title="Onboarding Status">
            <div className="grid gap-3 md:grid-cols-1">
              <div>
                <div className="text-xs text-slate-500">Overall completion</div>
                <div className="text-lg font-semibold">
                  {Number(onboardingStatus.overall_completion || 0).toFixed(0)}%
                </div>
              </div>
            </div>
            {onboardingStatus.forms_status ? (
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {Object.entries(onboardingStatus.forms_status).map(([key, value]) => (
                  <div key={key} className="rounded-lg border bg-slate-50 px-3 py-2 text-xs">
                    <div className="font-semibold">
                      {String(key).replace(/_/g, " ")}
                    </div>
                    <div>Completed: {value?.completed ? "Yes" : "No"}</div>
                    {"verified" in (value || {}) ? (
                      <div>Verified: {value?.verified ? "Yes" : "No"}</div>
                    ) : null}
                    {"count" in (value || {}) ? (
                      <div>Count: {value?.count ?? 0}</div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </Card>
        ) : null}

        <Card title="Jobs & Apply">
          <div className="space-y-3">
            {activeJobs?.length ? (
              activeJobs.slice(0, 10).map((j) => (
                <div
                  key={j.job_id}
                  className="rounded-lg border bg-white p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{j.job_title}</div>
                      <div className="text-xs text-slate-600">
                        {j.job_location || "—"} • {j.company_name || "—"}
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <StatusBadge status={normalizeJobStatus(j.job_status)} />
                        <span className="text-xs text-slate-500">{j.job_id}</span>
                      </div>
                    </div>
                    <Button
                      onClick={() => handleApplyForJob(j.job_id)}
                      disabled={!profile?.candidate_mobile}
                    >
                      Apply
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-600">
                No active jobs right now.
              </div>
            )}
            <div className="rounded-xl border bg-slate-50 p-3 text-xs text-slate-600">
              <div className="mb-2 font-semibold text-slate-700">Optional: Resume for application</div>
              <input
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={(e) => setJobResumeFile(e.target.files?.[0] || null)}
              />
              <div className="mt-1">
                {jobResumeFile ? `Selected: ${jobResumeFile.name}` : "No resume selected."}
              </div>
            </div>
            <div className="text-xs text-slate-500">
              Jobs list is sourced from the public “active/public” jobs endpoint.
            </div>
          </div>
        </Card>

        <Card title="My Documents">
          <div className="space-y-2">
            {myDocuments?.documents?.length ? (
              myDocuments.documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between gap-3 rounded-lg border bg-white p-3"
                >
                  <div>
                    <div className="text-sm font-semibold">
                      {DOC_LABELS[doc.document_type] || doc.document_type}
                    </div>
                    <div className="text-xs text-slate-500">
                      {doc.original_filename} •{" "}
                      {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : "-"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={doc.is_verified ? "Verified" : "Pending"} />
                    <Button
                      variant="secondary"
                      onClick={() => handleViewDocument(doc.id)}
                      disabled={!doc.id}
                    >
                      View
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-600">
                No documents uploaded yet.
              </div>
            )}
          </div>
        </Card>

        <Card title="Personal Information">
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Position" value={personal.position} onChange={(v) => setPersonal((p) => ({ ...p, position: v }))} />
            <Input label="Department" value={personal.department} onChange={(v) => setPersonal((p) => ({ ...p, department: v }))} />
            <Input label="Date of Birth" type="date" value={personal.dob || ""} onChange={(v) => setPersonal((p) => ({ ...p, dob: v }))} />
            <Select label="Gender" value={personal.gender || ""} onChange={(v) => setPersonal((p) => ({ ...p, gender: v }))} options={["", "Male", "Female", "Other"]} />
            <Input label="Marital Status" value={personal.marital_status} onChange={(v) => setPersonal((p) => ({ ...p, marital_status: v }))} />
            <Input label="Nationality" value={personal.nationality} onChange={(v) => setPersonal((p) => ({ ...p, nationality: v }))} />
            <TextArea label="Current Address" value={personal.current_address} onChange={(v) => setPersonal((p) => ({ ...p, current_address: v }))} rows={3} />
            <TextArea label="Permanent Address" value={personal.permanent_address} onChange={(v) => setPersonal((p) => ({ ...p, permanent_address: v }))} rows={3} />
          </div>
          <div className="mt-4 flex justify-end">
            <Button
              onClick={async () => {
                setNotice("");
                try {
                  await submitCandidateInfoForm(personal);
                  setNotice("Personal info saved.");
                } catch (err) {
                  setNotice(err.message || "Failed to save personal info.");
                }
              }}
              disabled={loading}
            >
              Save Personal Info
            </Button>
          </div>
        </Card>

        <Card title="Education">
          <div className="space-y-4">
            {education.map((row, idx) => (
              <div key={idx} className="grid gap-3 rounded-xl border p-3 md:grid-cols-2">
                <Input label="Institute" value={row.education_institute} onChange={(v) => {
                  const next = [...education];
                  next[idx].education_institute = v;
                  setEducation(next);
                }} />
                <Input label="Degree" value={row.degree} onChange={(v) => {
                  const next = [...education];
                  next[idx].degree = v;
                  setEducation(next);
                }} />
                <Input label="Field of Study" value={row.field_of_study} onChange={(v) => {
                  const next = [...education];
                  next[idx].field_of_study = v;
                  setEducation(next);
                }} />
                <Input label="Starting Year" value={row.starting_year} onChange={(v) => {
                  const next = [...education];
                  next[idx].starting_year = v;
                  setEducation(next);
                }} />
                <Input label="Year of Passing" value={row.year_of_passing} onChange={(v) => {
                  const next = [...education];
                  next[idx].year_of_passing = v;
                  setEducation(next);
                }} />
                <Input label="Percentage" value={row.percentage} onChange={(v) => {
                  const next = [...education];
                  next[idx].percentage = v;
                  setEducation(next);
                }} />
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={row.document_is_submitted}
                    onChange={(e) => {
                      const next = [...education];
                      next[idx].document_is_submitted = e.target.checked;
                      setEducation(next);
                    }}
                  />
                  Document submitted
                </label>
                <div className="flex items-center justify-between text-xs text-slate-500 md:col-span-2">
                  <span>{row.id ? `Record ID: ${row.id}` : "New record"}</span>
                  <Button
                    variant="danger"
                    onClick={async () => {
                      setNotice("");
                      if (row.id) {
                        setLoading(true);
                        try {
                          await deleteCandidateEducation(row.id);
                          const refreshed = await listCandidateEducation();
                          if (refreshed?.records?.length) {
                            setEducation(refreshed.records.map(normalizeEducationRecord));
                          } else {
                            setEducation([
                              {
                                id: null,
                                education_institute: "",
                                degree: "",
                                field_of_study: "",
                                starting_year: "",
                                year_of_passing: "",
                                percentage: "",
                                submitted_at: today(),
                                document_is_submitted: false
                              }
                            ]);
                          }
                          setNotice("Education record deleted.");
                        } catch (err) {
                          setNotice(err.message || "Failed to delete education record.");
                        } finally {
                          setLoading(false);
                        }
                      } else {
                        setEducation((prev) => prev.filter((_, index) => index !== idx));
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() =>
                setEducation((prev) => [
                  ...prev,
                  {
                    id: null,
                    education_institute: "",
                    degree: "",
                    field_of_study: "",
                    starting_year: "",
                    year_of_passing: "",
                    percentage: "",
                    submitted_at: today(),
                    document_is_submitted: false
                  }
                ])
              }
            >
              Add Education
            </Button>
            <Button
              onClick={async () => {
                setNotice("");
                try {
                  setLoading(true);
                  for (const record of education) {
                    const payload = toEducationPayload(record);
                    if (record.id) {
                      await updateCandidateEducation(record.id, payload);
                    } else {
                      await addCandidateEducation(payload);
                    }
                  }
                  const refreshed = await listCandidateEducation();
                  if (refreshed?.records?.length) {
                    setEducation(refreshed.records.map(normalizeEducationRecord));
                  }
                  setNotice("Education saved.");
                } catch (err) {
                  setNotice(err.message || "Failed to save education.");
                } finally {
                  setLoading(false);
                }
              }}
            >
              Save Education
            </Button>
          </div>
        </Card>

        <Card title="Experience">
          <div className="space-y-4">
            {experience.map((row, idx) => (
              <div key={idx} className="grid gap-3 rounded-xl border p-3 md:grid-cols-2">
                <Input label="Company Name" value={row.company_name} onChange={(v) => {
                  const next = [...experience];
                  next[idx].company_name = v;
                  setExperience(next);
                }} />
                <Input label="Job Title" value={row.job_title} onChange={(v) => {
                  const next = [...experience];
                  next[idx].job_title = v;
                  setExperience(next);
                }} />
                <Input label="Start Date" type="date" value={row.start_date || ""} onChange={(v) => {
                  const next = [...experience];
                  next[idx].start_date = v;
                  setExperience(next);
                }} />
                <Input label="End Date" type="date" value={row.end_date || ""} onChange={(v) => {
                  const next = [...experience];
                  next[idx].end_date = v;
                  setExperience(next);
                }} />
                <Input label="Years of Experience" value={row.year_of_experience} onChange={(v) => {
                  const next = [...experience];
                  next[idx].year_of_experience = v;
                  setExperience(next);
                }} />
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={row.document_is_submitted}
                    onChange={(e) => {
                      const next = [...experience];
                      next[idx].document_is_submitted = e.target.checked;
                      setExperience(next);
                    }}
                  />
                  Document submitted
                </label>
                <div className="flex items-center justify-between text-xs text-slate-500 md:col-span-2">
                  <span>{row.id ? `Record ID: ${row.id}` : "New record"}</span>
                  <Button
                    variant="danger"
                    onClick={async () => {
                      setNotice("");
                      if (row.id) {
                        setLoading(true);
                        try {
                          await deleteCandidateExperience(row.id);
                          const refreshed = await listCandidateExperience();
                          if (refreshed?.records?.length) {
                            setExperience(refreshed.records.map(normalizeExperienceRecord));
                          } else {
                            setExperience([
                              {
                                id: null,
                                company_name: "",
                                job_title: "",
                                start_date: "",
                                end_date: "",
                                year_of_experience: "",
                                submitted_at: today(),
                                document_is_submitted: false
                              }
                            ]);
                          }
                          setNotice("Experience record deleted.");
                        } catch (err) {
                          setNotice(err.message || "Failed to delete experience record.");
                        } finally {
                          setLoading(false);
                        }
                      } else {
                        setExperience((prev) => prev.filter((_, index) => index !== idx));
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() =>
                setExperience((prev) => [
                  ...prev,
                  {
                    id: null,
                    company_name: "",
                    job_title: "",
                    start_date: "",
                    end_date: "",
                    year_of_experience: "",
                    submitted_at: today(),
                    document_is_submitted: false
                  }
                ])
              }
            >
              Add Experience
            </Button>
            <Button
              onClick={async () => {
                setNotice("");
                try {
                  setLoading(true);
                  for (const record of experience) {
                    const payload = toExperiencePayload(record);
                    if (record.id) {
                      await updateCandidateExperience(record.id, payload);
                    } else {
                      await addCandidateExperience(payload);
                    }
                  }
                  const refreshed = await listCandidateExperience();
                  if (refreshed?.records?.length) {
                    setExperience(refreshed.records.map(normalizeExperienceRecord));
                  }
                  setNotice("Experience saved.");
                } catch (err) {
                  setNotice(err.message || "Failed to save experience.");
                } finally {
                  setLoading(false);
                }
              }}
            >
              Save Experience
            </Button>
          </div>
        </Card>

        <Card title="Aadhar Details">
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Aadhar" value={aadhar.aadhar} onChange={(v) => setAadhar((a) => ({ ...a, aadhar: v }))} />
            <Input label="Name in Aadhar" value={aadhar.name_in_aadhar} onChange={(v) => setAadhar((a) => ({ ...a, name_in_aadhar: v }))} />
            <Input label="Enrollment Number" value={aadhar.enrollment_number} onChange={(v) => setAadhar((a) => ({ ...a, enrollment_number: v }))} />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={aadhar.aadhar_is_submitted}
                onChange={(e) => setAadhar((a) => ({ ...a, aadhar_is_submitted: e.target.checked }))}
              />
              Aadhar submitted
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={aadhar.is_verified}
                onChange={(e) => setAadhar((a) => ({ ...a, is_verified: e.target.checked }))}
              />
              Verified
            </label>
          </div>
          <div className="mt-4 flex justify-end">
            <Button
              onClick={async () => {
                setNotice("");
                try {
                  await submitCandidateAadharForm({
                    ...aadhar,
                    submitted_at: aadhar.submitted_at || today()
                  });
                  setNotice("Aadhar saved.");
                } catch (err) {
                  setNotice(err.message || "Failed to save Aadhar.");
                }
              }}
            >
              Save Aadhar
            </Button>
          </div>
        </Card>

        <Card title="PAN Details">
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="PAN" value={pan.pan} onChange={(v) => setPan((p) => ({ ...p, pan: v }))} />
            <Input label="Name in PAN" value={pan.name_in_pan} onChange={(v) => setPan((p) => ({ ...p, name_in_pan: v }))} />
            <Input label="Father's Name" value={pan.father_name_in_pan} onChange={(v) => setPan((p) => ({ ...p, father_name_in_pan: v }))} />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={pan.pan_is_submitted}
                onChange={(e) => setPan((p) => ({ ...p, pan_is_submitted: e.target.checked }))}
              />
              PAN submitted
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={pan.is_verified}
                onChange={(e) => setPan((p) => ({ ...p, is_verified: e.target.checked }))}
              />
              Verified
            </label>
          </div>
          <div className="mt-4 flex justify-end">
            <Button
              onClick={async () => {
                setNotice("");
                try {
                  await submitCandidatePanForm({
                    ...pan,
                    submitted_at: pan.submitted_at || today()
                  });
                  setNotice("PAN saved.");
                } catch (err) {
                  setNotice(err.message || "Failed to save PAN.");
                }
              }}
            >
              Save PAN
            </Button>
          </div>
        </Card>

        <Card title="Document Uploads">
          <div className="text-sm text-slate-600 mb-3">
            Upload documents (PDF, JPG, PNG). Accepted: PAN, Aadhar, Education, Experience, Salary Slip, Bank Statement.
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {[
              { key: "pan", label: "PAN Card", upload: uploadPan },
              { key: "aadhar", label: "Aadhar Card", upload: uploadAadhar },
              { key: "education", label: "Education Certificate", upload: uploadEducationCertificate },
              { key: "experience", label: "Experience Letter", upload: uploadExperienceLetter },
              { key: "salary_slip", label: "Salary Slip", upload: uploadSalarySlip },
              { key: "bank_statement", label: "Bank Statement", upload: uploadBankStatement }
            ].map(({ key, label, upload }) => (
              <DocumentUploadRow
                key={key}
                label={label}
                onUpload={async (file) => {
                  setNotice("");
                  try {
                    await upload(file);
                    setNotice(`${label} uploaded.`);
                  } catch (err) {
                    setNotice(err.message || `Failed to upload ${label}.`);
                  }
                }}
                disabled={loading}
              />
            ))}
          </div>
        </Card>

        <Card title="Change Password">
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              label="New Password"
              type="password"
              value={passwordForm.new_password}
              onChange={(v) => setPasswordForm((p) => ({ ...p, new_password: v }))}
            />
            <Input
              label="Confirm Password"
              type="password"
              value={passwordForm.confirm_password}
              onChange={(v) => setPasswordForm((p) => ({ ...p, confirm_password: v }))}
            />
          </div>
          <div className="mt-4 flex justify-end">
            <Button
              onClick={async () => {
                setNotice("");
                setLoading(true);
                try {
                  await changeCandidatePassword(passwordForm);
                  setNotice("Password updated.");
                  setPasswordForm({ new_password: "", confirm_password: "" });
                } catch (err) {
                  setNotice(err.message || "Failed to update password.");
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
            >
              Update Password
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
