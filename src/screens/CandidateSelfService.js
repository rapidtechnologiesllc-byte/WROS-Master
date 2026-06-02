// Candidate portal for personal info, education, experience, and documents.
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Eye, EyeOff, ListChecks } from "lucide-react";
import {
  Button,
  Card,
  Input,
  Select,
  StatusBadge,
  TextArea,
} from "../components/ui";
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
  listCandidateEducation,
  listCandidateExperience,
  submitCandidateAadharForm,
  submitCandidateInfoForm,
  submitCandidatePanForm,
  updateCandidateEducation,
  updateCandidateExperience,
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
} from "../services/api/documents";
import { getActiveJobs, applyForJob } from "../services/api/jobs";
import {
  candidateCompleteChecklistItem,
  getMyChecklists,
} from "../services/api/checklists";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const today = () => new Date().toISOString().slice(0, 10);

const DOC_LABELS = {
  resume: "Resume",
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement",
};

function canCandidateCompleteItem(item) {
  if (!item || item.status === "completed") return false;
  if (item.item_type === "todo") return item.status === "pending";
  if (item.item_type === "queue") return item.status === "active";
  return false;
}

const normalizeJobStatus = (rawStatus) => {
  const raw = String(rawStatus || "")
    .trim()
    .toLowerCase();
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
        onChange={(e) => setFile(e.target.files?.[0] || null)}
        className="text-xs"
        disabled={disabled}
      />

      <Button
        variant="secondary"
        onClick={() => file && onUpload(file)}
        disabled={!file || disabled}
      >
        {disabled ? "Uploading..." : "Upload"}
      </Button>
    </div>
  );
}

export default function CandidateSelfService({ onLogout }) {
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("error");
  const [profile, setProfile] = useState(null);
  const [onboardingStatus, setOnboardingStatus] = useState(null);
  const [passwordForm, setPasswordForm] = useState({
    new_password: "",
    confirm_password: "",
  });
  const [myOffers, setMyOffers] = useState([]);
  const [myDocuments, setMyDocuments] = useState(null);
  const [activeJobs, setActiveJobs] = useState([]);
  const [uploadingType, setUploadingType] = useState(null);
  const [jobResumeFile, setJobResumeFile] = useState(null);
  const [myChecklistsPayload, setMyChecklistsPayload] = useState(null);
  const [checklistCompletingId, setChecklistCompletingId] = useState(null);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);

  const profileMenuRef = useRef(null);

  const [candidatePasswordForm, setCandidatePasswordForm] = useState({
    new_password: "",
    confirm_password: "",
  });

  const storedCandidateName = localStorage.getItem("hrms_user_name") || "";
  const storedCandidateEmail = localStorage.getItem("hrms_user_email") || "";

  let noticeTimer;

  const showNotice = (message, type = "error", scroll = true) => {
    setNotice(message);
    setNoticeType(type);

    if (scroll) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    if (noticeTimer) clearTimeout(noticeTimer);

    noticeTimer = setTimeout(() => {
      setNotice("");
    }, 3000);
  };

  const clearNotice = () => {
    setNotice("");
    setNoticeType("error");
  };

  const normalizeEducationRecord = (record = {}) => ({
    id: record.formID ?? record.id ?? null,
    education_institute: record.education_institute || "",
    degree: record.degree || "",
    field_of_study: record.field_of_study || "",
    starting_year: record.starting_year || "",
    year_of_passing: record.year_of_passing || "",
    percentage: record.percentage || "",
    submitted_at: record.submitted_at || record.submittedAt || today(),
    document_is_submitted: Boolean(record.document_is_submitted),
  });

  const normalizeExperienceRecord = (record = {}) => ({
    id: record.formID ?? record.id ?? null,
    company_name: record.company_name || "",
    job_title: record.job_title || "",
    start_date: record.start_date || "",
    end_date: record.end_date || "",
    year_of_experience: record.year_of_experience || "",
    submitted_at: record.submitted_at || record.submittedAt || today(),
    document_is_submitted: Boolean(record.document_is_submitted),
  });

  const toEducationPayload = (record) => ({
    education_institute: record.education_institute,
    degree: record.degree,
    field_of_study: record.field_of_study,
    starting_year: record.starting_year,
    year_of_passing: record.year_of_passing,
    percentage: record.percentage,
    submitted_at: record.submitted_at || today(),
    document_is_submitted: Boolean(record.document_is_submitted),
  });

  const toExperiencePayload = (record) => ({
    company_name: record.company_name,
    job_title: record.job_title,
    start_date: record.start_date,
    end_date: record.end_date,
    year_of_experience: record.year_of_experience,
    submitted_at: record.submitted_at || today(),
    document_is_submitted: Boolean(record.document_is_submitted),
  });
  const handleApplyForJob = async (jobId) => {
    if (!jobId) return;

    if (!profile?.candidate_email) {
      showNotice("Candidate email is missing. Please login again.");
      return;
    }

    if (!profile?.candidate_mobile) {
      showNotice(
        "Candidate phone is missing. Please update your phone number before applying.",
      );
      return;
    }

    try {
      clearNotice();

      const educationEntries = (education || [])
        .filter((e) => e.education_institute || e.degree || e.field_of_study)
        .map((e) => ({
          institution: e.education_institute,
          degree: e.degree,
          field_of_study: e.field_of_study,
          start_year: e.starting_year,
          end_year: e.year_of_passing,
          percentage: e.percentage || null,
        }));

      const experienceEntries = (experience || [])
        .filter((e) => e.company_name || e.job_title)
        .map((e) => ({
          company_name: e.company_name,
          job_title: e.job_title,
          start_date: e.start_date,
          end_date: e.end_date || null,
          years_of_experience: e.year_of_experience || null,
        }));

      const res = await applyForJob({
        jobId,
        fullName: profile?.candidate_name || "Candidate",
        email: profile?.candidate_email,
        phone: profile?.candidate_mobile,
        educationEntries,
        experienceEntries,
        resumeFile: jobResumeFile,
      });

      showNotice(res?.message || "Applied successfully.", "success");
    } catch (err) {
      showNotice(err.message || "Failed to apply for job.");
    }
  };

  const fetchDocuments = async () => {
    try {
      const docs = await getMyDocuments();
      setMyDocuments(docs);
    } catch (err) {
      showNotice(err.message || "Failed to refresh documents.");
    }
  };

  const handleUpload = async (uploadFn, label, file) => {
    if (!file) return;

    try {
      setUploadingType(label);
      clearNotice();

      await uploadFn(file);
      await fetchDocuments();

      showNotice(`✅ ${label} uploaded successfully.`, "success");
    } catch (err) {
      showNotice(`❌ ${err.message || `Failed to upload ${label}.`}`, "error");
    } finally {
      setUploadingType(null);
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
    submitted_at: today(),
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
      document_is_submitted: false,
    },
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
      document_is_submitted: false,
    },
  ]);

  const [aadhar, setAadhar] = useState({
    aadhar: "",
    name_in_aadhar: "",
    enrollment_number: "",
    aadhar_is_submitted: false,
    submitted_at: today(),
    is_verified: false,
  });

  const [pan, setPan] = useState({
    pan: "",
    name_in_pan: "",
    father_name_in_pan: "",
    pan_is_submitted: false,
    submitted_at: today(),
    is_verified: false,
  });
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!isProfileMenuOpen) return;

      if (
        profileMenuRef.current &&
        !profileMenuRef.current.contains(event.target)
      ) {
        setIsProfileMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isProfileMenuOpen]);

  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      setLoading(true);

      try {
        const [
          myInfoResult,
          educationResult,
          experienceResult,
          aadharResult,
          panResult,
          onboardingResult,
          offersResult,
          documentsResult,
          jobsResult,
          checklistsResult,
        ] = await Promise.allSettled([
          getCandidateMyInfo(),
          listCandidateEducation(),
          listCandidateExperience(),
          getCandidateAadhar(),
          getCandidatePan(),
          getCandidateOnboardingStatus(),
          getMyOffers(),
          getMyDocuments(),
          getActiveJobs(),
          getMyChecklists(),
        ]);

        if (!isMounted) return;

        if (myInfoResult.status === "fulfilled") {
          setProfile(myInfoResult.value);
          const personalInfo = myInfoResult.value?.personal_info || {};
          setPersonal((prev) => ({
            ...prev,
            ...personalInfo,
            dob: myInfoResult.value.dob || prev.dob,
            submitted_at: today(),
          }));
        }

        if (
          educationResult.status === "fulfilled" &&
          educationResult.value?.records?.length
        ) {
          setEducation(
            educationResult.value.records.map(normalizeEducationRecord),
          );
        }

        if (
          experienceResult.status === "fulfilled" &&
          experienceResult.value?.records?.length
        ) {
          setExperience(
            experienceResult.value.records.map(normalizeExperienceRecord),
          );
        }

        if (aadharResult.status === "fulfilled" && aadharResult.value) {
          setAadhar((prev) => ({
            ...prev,
            ...aadharResult.value,
            submitted_at: today(),
          }));
        }

        if (panResult.status === "fulfilled" && panResult.value) {
          setPan((prev) => ({
            ...prev,
            ...panResult.value,
            submitted_at: today(),
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
          setActiveJobs(
            Array.isArray(jobsResult.value?.jobs) ? jobsResult.value.jobs : [],
          );
        }

        if (checklistsResult.status === "fulfilled" && checklistsResult.value) {
          setMyChecklistsPayload(checklistsResult.value);
        }

        const errors = [
          myInfoResult,
          educationResult,
          experienceResult,
          aadharResult,
          panResult,
          onboardingResult,
          offersResult,
          documentsResult,
          jobsResult,
          checklistsResult,
        ]
          .filter((result) => result.status === "rejected")
          .map((result) => result.reason);

        if (errors.length) {
          showNotice(
            errors[0]?.message || "Failed to load some data.",
            "error",
            false,
          );
        }
      } catch (err) {
        if (!isMounted) return;
        showNotice(
          err.message || "Failed to load candidate profile.",
          "error",
          false,
        );
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
    profile?.pipeline_status ||
      profile?.pipline_status ||
      profile?.status ||
      "",
  )
    .trim()
    .toLowerCase();

  const isPreBoarding = profilePipeline.includes("pre");
  const shouldShowChecklists = checklistList.length > 0 || isPreBoarding;

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-white px-5 py-4 shadow-sm">
          <div>
            <div className="text-xs font-semibold text-slate-500">
              Candidate Portal
            </div>
            <div className="text-xl font-bold">{candidateName}</div>
            {candidateEmail ? (
              <div className="text-xs text-slate-500">{candidateEmail}</div>
            ) : null}
          </div>

          <div className="relative" ref={profileMenuRef}>
            <button
              type="button"
              onClick={() => setIsProfileMenuOpen((prev) => !prev)}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                {candidateName?.[0]?.toUpperCase() || "C"}
              </span>

              <span className="hidden max-w-[160px] truncate sm:inline">
                {candidateName || "Candidate"}
              </span>

              <ChevronDown className="h-4 w-4 text-slate-500" />
            </button>

            {isProfileMenuOpen ? (
              <div className="absolute right-0 top-12 z-50 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
                <button
                  type="button"
                  onClick={() => {
                    setShowProfileModal(true);
                    setIsProfileMenuOpen(false);
                  }}
                  className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                >
                  View Profile
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setCandidatePasswordForm({
                      new_password: "",
                      confirm_password: "",
                    });
                    setShowNewPassword(false);
                    setShowConfirmPassword(false);
                    setShowPasswordModal(true);
                    setIsProfileMenuOpen(false);
                  }}
                  className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                >
                  Change Password
                </button>

                <button
                  type="button"
                  onClick={onLogout}
                  className="block w-full px-4 py-2.5 text-left text-sm font-medium text-rose-600 transition hover:bg-rose-50"
                >
                  Logout
                </button>
              </div>
            ) : null}
          </div>
        </div>
        {showProfileModal ? (
          <div
            onClick={() => setShowProfileModal(false)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 backdrop-blur-sm"
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
            >
              <h2 className="mb-5 text-xl font-semibold text-slate-900">
                Candidate Profile
              </h2>

              <div className="space-y-3 text-sm">
                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">Name</span>
                  <span className="text-right font-medium text-slate-900">
                    {profile?.candidate_name || candidateName || "-"}
                  </span>
                </div>

                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">Email</span>
                  <span className="text-right font-medium text-slate-900">
                    {profile?.candidate_email || candidateEmail || "-"}
                  </span>
                </div>

                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">Mobile</span>
                  <span className="text-right font-medium text-slate-900">
                    {profile?.candidate_mobile || "-"}
                  </span>
                </div>

                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">Status</span>
                  <span className="text-right font-medium text-slate-900">
                    {profile?.pipeline_status ||
                      profile?.pipline_status ||
                      profile?.status ||
                      "-"}
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setShowProfileModal(false)}
                className="mt-6 w-full rounded-xl bg-slate-900 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        ) : null}

        {showPasswordModal ? (
          <div
            onClick={() => setShowPasswordModal(false)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 backdrop-blur-sm"
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
            >
              <h2 className="mb-5 text-xl font-semibold text-slate-900">
                Change Password
              </h2>

              <div className="space-y-3">
                <div className="relative">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    placeholder="New Password"
                    value={candidatePasswordForm.new_password}
                    onChange={(e) =>
                      setCandidatePasswordForm((prev) => ({
                        ...prev,
                        new_password: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm outline-none transition focus:border-slate-400"
                  />

                  <button
                    type="button"
                    onClick={() => setShowNewPassword((prev) => !prev)}
                    className="absolute right-3 top-2.5 text-slate-500"
                  >
                    {showNewPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>

                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Confirm Password"
                    value={candidatePasswordForm.confirm_password}
                    onChange={(e) =>
                      setCandidatePasswordForm((prev) => ({
                        ...prev,
                        confirm_password: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm outline-none transition focus:border-slate-400"
                  />

                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    className="absolute right-3 top-2.5 text-slate-500"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>

              <div className="mt-5 flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  className="w-1/2 rounded-xl border border-slate-300 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                  disabled={passwordSubmitting}
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={async () => {
                    const newPassword =
                      candidatePasswordForm?.new_password?.trim();
                    const confirmPassword =
                      candidatePasswordForm?.confirm_password?.trim();

                    if (!newPassword || !confirmPassword) {
                      showNotice(
                        "Please fill all password fields.",
                        "error",
                        false,
                      );
                      return;
                    }

                    if (newPassword !== confirmPassword) {
                      showNotice(
                        "New password and confirm password do not match.",
                        "error",
                        false,
                      );
                      return;
                    }

                    try {
                      setPasswordSubmitting(true);
                      clearNotice();

                      await changeCandidatePassword({
                        new_password: newPassword,
                        confirm_password: confirmPassword,
                      });

                      showNotice(
                        "Password updated successfully.",
                        "success",
                        false,
                      );

                      setCandidatePasswordForm({
                        new_password: "",
                        confirm_password: "",
                      });

                      setShowPasswordModal(false);
                    } catch (err) {
                      showNotice(
                        err?.message || "Failed to update password.",
                        "error",
                        false,
                      );
                    } finally {
                      setPasswordSubmitting(false);
                    }
                  }}
                  className="w-1/2 rounded-xl bg-slate-900 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={passwordSubmitting}
                >
                  {passwordSubmitting ? "Updating..." : "Update"}
                </button>
              </div>
            </div>
          </div>
        ) : null}
        {notice ? (
          <div
            className={`rounded-lg border px-3 py-2 text-sm ${
              noticeType === "success"
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            {notice}
          </div>
        ) : null}

        {myOffers?.length > 0 ? (
          <Card title="Offer Letters">
            <div className="space-y-3">
              {myOffers.map((o) => (
                <div key={o.id} className="rounded-lg border bg-slate-50 p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold">{o.position}</div>
                      <div className="text-xs text-slate-600">
                        Salary: ${o.salary} | Joining: {o.joining_date}
                      </div>
                      <div className="mt-1 text-xs">
                        Status:{" "}
                        <span className="font-medium">{o.offer_status}</span>
                      </div>
                    </div>

                    {o.offer_status === "Pending" ? (
                      <div className="flex gap-2">
                        <Button
                          variant="danger"
                          onClick={async () => {
                            clearNotice();

                            try {
                              await respondToOffer({
                                offerId: o.id,
                                action: "reject",
                              });

                              const refreshed = await getMyOffers();
                              setMyOffers(refreshed?.offers || []);
                              showNotice("Offer declined.", "success");
                            } catch (err) {
                              showNotice(
                                err.message || "Failed to decline offer.",
                              );
                            }
                          }}
                          disabled={loading}
                        >
                          Decline
                        </Button>

                        <Button
                          onClick={async () => {
                            clearNotice();

                            try {
                              await respondToOffer({
                                offerId: o.id,
                                action: "accept",
                              });

                              const refreshed = await getMyOffers();
                              setMyOffers(refreshed?.offers || []);
                              showNotice("Offer accepted!", "success");
                            } catch (err) {
                              showNotice(
                                err.message || "Failed to accept offer.",
                              );
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
                        <StatusBadge
                          status={
                            cl.status === "completed"
                              ? "Completed"
                              : "Scheduled"
                          }
                        />
                      </div>

                      <ul className="space-y-2">
                        {(cl.items || [])
                          .slice()
                          .sort(
                            (a, b) =>
                              (a.order_index ?? 0) - (b.order_index ?? 0),
                          )
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
                                  <div className="text-sm font-medium">
                                    {item.title}
                                  </div>
                                  {item.description ? (
                                    <div className="text-xs text-slate-600">
                                      {item.description}
                                    </div>
                                  ) : null}
                                  <div className="mt-1">
                                    <StatusBadge status={item.status} />
                                  </div>
                                  {waitingQueue ? (
                                    <div className="mt-1 text-xs text-amber-700">
                                      Awaiting previous step
                                    </div>
                                  ) : null}
                                </div>

                                {item.status !== "completed" ? (
                                  <Button
                                    variant="secondary"
                                    onClick={async () => {
                                      clearNotice();
                                      setChecklistCompletingId(item.id);

                                      try {
                                        await candidateCompleteChecklistItem(
                                          item.id,
                                        );
                                        const refreshed =
                                          await getMyChecklists();
                                        setMyChecklistsPayload(refreshed);
                                        showNotice(
                                          "Task marked complete.",
                                          "success",
                                        );
                                      } catch (err) {
                                        showNotice(
                                          err.message ||
                                            "Could not complete task.",
                                        );
                                      } finally {
                                        setChecklistCompletingId(null);
                                      }
                                    }}
                                    disabled={
                                      !actionable ||
                                      checklistCompletingId === item.id
                                    }
                                  >
                                    {checklistCompletingId === item.id
                                      ? "Saving…"
                                      : "Mark complete"}
                                  </Button>
                                ) : (
                                  <span className="text-xs font-semibold text-green-700">
                                    Done
                                  </span>
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

        <Card title="Personal Information">
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              label="Position"
              value={personal.position}
              onChange={(v) => setPersonal((p) => ({ ...p, position: v }))}
            />
            <Input
              label="Department"
              value={personal.department}
              onChange={(v) => setPersonal((p) => ({ ...p, department: v }))}
            />
            <Input
              label="Date of Birth"
              type="date"
              value={personal.dob || ""}
              onChange={(v) => setPersonal((p) => ({ ...p, dob: v }))}
            />
            <Select
              label="Gender"
              value={personal.gender || ""}
              onChange={(v) => setPersonal((p) => ({ ...p, gender: v }))}
              options={["", "Male", "Female", "Other"]}
            />
            <Input
              label="Marital Status"
              value={personal.marital_status}
              onChange={(v) =>
                setPersonal((p) => ({ ...p, marital_status: v }))
              }
            />
            <Input
              label="Nationality"
              value={personal.nationality}
              onChange={(v) => setPersonal((p) => ({ ...p, nationality: v }))}
            />
            <TextArea
              label="Current Address"
              value={personal.current_address}
              onChange={(v) =>
                setPersonal((p) => ({ ...p, current_address: v }))
              }
              rows={3}
            />
            <TextArea
              label="Permanent Address"
              value={personal.permanent_address}
              onChange={(v) =>
                setPersonal((p) => ({ ...p, permanent_address: v }))
              }
              rows={3}
            />
          </div>

          <div className="mt-4 flex justify-end">
            <Button
              onClick={async () => {
                clearNotice();

                try {
                  await submitCandidateInfoForm(personal);
                  showNotice("Personal info saved.", "success");
                } catch (err) {
                  showNotice(err.message || "Failed to save personal info.");
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
              <div
                key={idx}
                className="grid gap-3 rounded-xl border p-3 md:grid-cols-2"
              >
                <Input
                  label="Institute"
                  value={row.education_institute}
                  onChange={(v) => {
                    const next = [...education];
                    next[idx].education_institute = v;
                    setEducation(next);
                  }}
                />
                <Input
                  label="Degree"
                  value={row.degree}
                  onChange={(v) => {
                    const next = [...education];
                    next[idx].degree = v;
                    setEducation(next);
                  }}
                />
                <Input
                  label="Field of Study"
                  value={row.field_of_study}
                  onChange={(v) => {
                    const next = [...education];
                    next[idx].field_of_study = v;
                    setEducation(next);
                  }}
                />
                <Input
                  label="Starting Year"
                  value={row.starting_year}
                  onChange={(v) => {
                    const next = [...education];
                    next[idx].starting_year = v;
                    setEducation(next);
                  }}
                />
                <Input
                  label="Year of Passing"
                  value={row.year_of_passing}
                  onChange={(v) => {
                    const next = [...education];
                    next[idx].year_of_passing = v;
                    setEducation(next);
                  }}
                />
                <Input
                  label="Percentage"
                  value={row.percentage}
                  onChange={(v) => {
                    const next = [...education];
                    next[idx].percentage = v;
                    setEducation(next);
                  }}
                />

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
                      clearNotice();

                      if (row.id) {
                        setLoading(true);

                        try {
                          await deleteCandidateEducation(row.id);
                          const refreshed = await listCandidateEducation();

                          if (refreshed?.records?.length) {
                            setEducation(
                              refreshed.records.map(normalizeEducationRecord),
                            );
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
                                document_is_submitted: false,
                              },
                            ]);
                          }

                          showNotice("Education record deleted.", "success");
                        } catch (err) {
                          showNotice(
                            err.message || "Failed to delete education record.",
                          );
                        } finally {
                          setLoading(false);
                        }
                      } else {
                        setEducation((prev) =>
                          prev.filter((_, index) => index !== idx),
                        );
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between gap-3">
            <DocumentUploadRow
              label="Education Certificate"
              onUpload={(file) =>
                handleUpload(
                  uploadEducationCertificate,
                  "Education Certificate",
                  file,
                )
              }
              disabled={loading || uploadingType === "Education Certificate"}
            />
            <div className="ml-auto">
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
                      document_is_submitted: false,
                    },
                  ])
                }
              >
                Add Education
              </Button>
            </div>

            <Button
              onClick={async () => {
                clearNotice();

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
                    setEducation(
                      refreshed.records.map(normalizeEducationRecord),
                    );
                  }

                  showNotice("Education saved.", "success");
                } catch (err) {
                  showNotice(err.message || "Failed to save education.");
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
              <div
                key={idx}
                className="grid gap-3 rounded-xl border p-3 md:grid-cols-2"
              >
                <Input
                  label="Company Name"
                  value={row.company_name}
                  onChange={(v) => {
                    const next = [...experience];
                    next[idx].company_name = v;
                    setExperience(next);
                  }}
                />
                <Input
                  label="Job Title"
                  value={row.job_title}
                  onChange={(v) => {
                    const next = [...experience];
                    next[idx].job_title = v;
                    setExperience(next);
                  }}
                />
                <Input
                  label="Start Date"
                  type="date"
                  value={row.start_date || ""}
                  onChange={(v) => {
                    const next = [...experience];
                    next[idx].start_date = v;
                    setExperience(next);
                  }}
                />
                <Input
                  label="End Date"
                  type="date"
                  value={row.end_date || ""}
                  onChange={(v) => {
                    const next = [...experience];
                    next[idx].end_date = v;
                    setExperience(next);
                  }}
                />
                <Input
                  label="Years of Experience"
                  value={row.year_of_experience}
                  onChange={(v) => {
                    const next = [...experience];
                    next[idx].year_of_experience = v;
                    setExperience(next);
                  }}
                />

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
                      clearNotice();

                      if (row.id) {
                        setLoading(true);

                        try {
                          await deleteCandidateExperience(row.id);
                          const refreshed = await listCandidateExperience();

                          if (refreshed?.records?.length) {
                            setExperience(
                              refreshed.records.map(normalizeExperienceRecord),
                            );
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
                                document_is_submitted: false,
                              },
                            ]);
                          }

                          showNotice("Experience record deleted.", "success");
                        } catch (err) {
                          showNotice(
                            err.message ||
                              "Failed to delete experience record.",
                          );
                        } finally {
                          setLoading(false);
                        }
                      } else {
                        setExperience((prev) =>
                          prev.filter((_, index) => index !== idx),
                        );
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between gap-3">
            <DocumentUploadRow
              label="Experience Letter"
              onUpload={(file) =>
                handleUpload(uploadExperienceLetter, "Experience Letter", file)
              }
              disabled={loading || uploadingType === "Experience Letter"}
            />
            <div className="ml-auto">
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
                      document_is_submitted: false,
                    },
                  ])
                }
              >
                Add Experience
              </Button>
            </div>

            <Button
              onClick={async () => {
                clearNotice();

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
                    setExperience(
                      refreshed.records.map(normalizeExperienceRecord),
                    );
                  }

                  showNotice("Experience saved.", "success");
                } catch (err) {
                  showNotice(err.message || "Failed to save experience.");
                } finally {
                  setLoading(false);
                }
              }}
            >
              Save Experience
            </Button>
          </div>
        </Card>

        <Card title="PAN Details">
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              label="PAN"
              value={pan.pan}
              onChange={(v) => setPan((p) => ({ ...p, pan: v }))}
            />
            <Input
              label="Name in PAN"
              value={pan.name_in_pan}
              onChange={(v) => setPan((p) => ({ ...p, name_in_pan: v }))}
            />
            <Input
              label="Father's Name"
              value={pan.father_name_in_pan}
              onChange={(v) => setPan((p) => ({ ...p, father_name_in_pan: v }))}
            />

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={pan.pan_is_submitted}
                onChange={(e) =>
                  setPan((p) => ({ ...p, pan_is_submitted: e.target.checked }))
                }
              />
              PAN submitted
            </label>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={pan.is_verified}
                onChange={(e) =>
                  setPan((p) => ({ ...p, is_verified: e.target.checked }))
                }
              />
              Verified
            </label>
          </div>

          <div className="mt-4 flex items-center justify-between gap-3">
            <DocumentUploadRow
              label="PAN Card"
              onUpload={(file) => handleUpload(uploadPan, "PAN Card", file)}
              disabled={loading || uploadingType === "PAN Card"}
            />
            <Button
              onClick={async () => {
                clearNotice();

                try {
                  await submitCandidatePanForm({
                    ...pan,
                    submitted_at: pan.submitted_at || today(),
                  });
                  showNotice("PAN saved.", "success");
                } catch (err) {
                  showNotice(err.message || "Failed to save PAN.");
                }
              }}
            >
              Save PAN
            </Button>
          </div>
        </Card>

        <Card title="Aadhar Details">
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              label="Aadhar"
              value={aadhar.aadhar}
              onChange={(v) => setAadhar((a) => ({ ...a, aadhar: v }))}
            />
            <Input
              label="Name in Aadhar"
              value={aadhar.name_in_aadhar}
              onChange={(v) => setAadhar((a) => ({ ...a, name_in_aadhar: v }))}
            />
            <Input
              label="Enrollment Number"
              value={aadhar.enrollment_number}
              onChange={(v) =>
                setAadhar((a) => ({ ...a, enrollment_number: v }))
              }
            />

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={aadhar.aadhar_is_submitted}
                onChange={(e) =>
                  setAadhar((a) => ({
                    ...a,
                    aadhar_is_submitted: e.target.checked,
                  }))
                }
              />
              Aadhar submitted
            </label>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={aadhar.is_verified}
                onChange={(e) =>
                  setAadhar((a) => ({ ...a, is_verified: e.target.checked }))
                }
              />
              Verified
            </label>
          </div>

          <div className="mt-4 flex items-center justify-between gap-3">
            <DocumentUploadRow
              label="Aadhar Card"
              onUpload={(file) =>
                handleUpload(uploadAadhar, "Aadhar Card", file)
              }
              disabled={loading || uploadingType === "Aadhar Card"}
            />
            <Button
              onClick={async () => {
                clearNotice();

                try {
                  await submitCandidateAadharForm({
                    ...aadhar,
                    submitted_at: aadhar.submitted_at || today(),
                  });
                  showNotice("Aadhar saved.", "success");
                } catch (err) {
                  showNotice(err.message || "Failed to save Aadhar.");
                }
              }}
            >
              Save Aadhar
            </Button>
          </div>
        </Card>
        <Card title="Bank Statement">
          <div className="mb-3 text-sm text-slate-600">
            Please upload bank statements for the last 3 months showing salary
            credits.
          </div>

          <DocumentUploadRow
            label="Bank Statement"
            onUpload={(file) =>
              handleUpload(uploadBankStatement, "Bank Statement", file)
            }
            disabled={loading || uploadingType === "Bank Statement"}
          />
        </Card>
        <Card title="Salary Slip">
          <div className="mb-3 text-sm text-slate-600">
            Please upload your last 3 months payslips.
          </div>

          <DocumentUploadRow
            label="Salary Slip"
            onUpload={(file) =>
              handleUpload(uploadSalarySlip, "Salary Slip", file)
            }
            disabled={loading || uploadingType === "Salary Slip"}
          />
        </Card>

        <div className="mt-4"></div>

        {onboardingStatus ? (
          <Card title="Onboarding Status">
            <div className="grid gap-3 md:grid-cols-1">
              <div>
                <div className="text-xs text-slate-500">Overall completion</div>
                <div className="text-lg font-semibold">
                  {Number(onboardingStatus?.overall_completion || 0).toFixed(0)}
                  %
                </div>
              </div>
            </div>

            {onboardingStatus.forms_status ? (
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {Object.entries(onboardingStatus?.forms_status).map(
                  ([key, value]) => (
                    <div
                      key={key}
                      className="rounded-lg border bg-slate-50 px-3 py-2 text-xs"
                    >
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
                  ),
                )}
              </div>
            ) : null}
          </Card>
        ) : null}
        <Card title="My Documents">
          <div className="space-y-2">
            {myDocuments?.documents?.length ? (
              myDocuments.documents.map((doc) => {
                return (
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
                        {doc.uploaded_at
                          ? new Date(doc.uploaded_at).toLocaleDateString()
                          : "-"}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <StatusBadge
                        status={
                          doc.is_verified
                            ? "Verified"
                            : doc.notes
                              ? "Rejected"
                              : "Pending"
                        }
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-sm text-slate-600">
                No documents uploaded yet.
              </div>
            )}
          </div>
        </Card>

        <Card title="Change Password">
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              label="New Password"
              type="password"
              value={passwordForm.new_password}
              onChange={(v) =>
                setPasswordForm((p) => ({ ...p, new_password: v }))
              }
            />
            <Input
              label="Confirm Password"
              type="password"
              value={passwordForm.confirm_password}
              onChange={(v) =>
                setPasswordForm((p) => ({ ...p, confirm_password: v }))
              }
            />
          </div>

          <div className="mt-4 flex justify-end">
            <Button
              onClick={async () => {
                clearNotice();
                setLoading(true);

                try {
                  await changeCandidatePassword(passwordForm);
                  showNotice("Password updated.", "success");
                  setPasswordForm({ new_password: "", confirm_password: "" });
                } catch (err) {
                  showNotice(err.message || "Failed to update password.");
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
