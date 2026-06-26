import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  Eye,
  EyeOff,
  ListChecks,
  LayoutDashboard,
  User,
  FileText,
  BadgeCheck,
  Briefcase,
} from "lucide-react";
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
import {
  getMyOffers,
  respondToOffer,
  signOfferLetter,
} from "../services/api/offerLetters";
import {
  uploadPan,
  uploadAadhar,
  uploadEducationCertificate,
  uploadExperienceLetter,
  uploadSalarySlip,
  uploadBankStatement,
  uploadUanPfDocument,
  getMyDocuments,
} from "../services/api/documents";
import { getActiveJobs, applyForJob } from "../services/api/jobs";
import {
  candidateCompleteChecklistItem,
  getMyChecklists,
} from "../services/api/checklists";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import SignatureModal from "../components/ui/SignatureModal";
import { getHrAssignmentByCandidate } from "../services/api/users";
import { sendEventNotification } from "../services/api/email";
import { getOfferAcceptedNotificationTemplate } from "../utils/offerAcceptedEmailTemplate";

const today = () => new Date().toISOString().slice(0, 10);

const DOC_LABELS = {
  resume: "Resume",
  pan: "PAN Card",
  aadhar: "Aadhar Card",
  education: "Education Certificate",
  experience: "Experience Letter",
  salary_slip: "Salary Slip",
  bank_statement: "Bank Statement",
  uan_pf: "UAN / PF Document",
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
  const [profile, setProfile] = useState(null);
  const [onboardingStatus, setOnboardingStatus] = useState(null);
  const [activeSection, setActiveSection] = useState("dashboard");
  const [passwordForm, setPasswordForm] = useState({
    new_password: "",
    confirm_password: "",
  });
  const [myOffers, setMyOffers] = useState([]);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedOffer, setSelectedOffer] = useState(null);
  const [signatureLoading, setSignatureLoading] = useState(false);
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

  const showNotice = (message, type = "error") => {
    if (type === "success") {
      toast.success(message, {
        position: "top-right",
        autoClose: 3000,
      });
    } else {
      toast.error(message, {
        position: "top-right",
        autoClose: 3000,
      });
    }
  };
  const clearNotice = () => {};

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
  const notifyAssignedHr = async (documentName) => {
    try {
      const candidateId = profile?.candidate_id;
      if (!candidateId) return;
      const assignment = await getHrAssignmentByCandidate(candidateId);
      const hr = assignment?.hr1;
      if (!hr?.user_email) {
        console.warn("No HR email found for candidate");
        return;
      }
      const candidateName = profile?.candidate_name || "Candidate";
      await sendEventNotification({
        toEmail: hr.user_email,
        recipientName: hr.user_name,
        heading: "Candidate Document Uploaded",
        message: `${candidateName} has uploaded ${documentName} for verification.`,
        metadata: {
          Candidate: candidateName,
          Document: documentName,
        },
      });
    } catch (error) {
      console.error("Failed to notify assigned HR", error);
    }
  };
  const notifyOfferAcceptedHr = async (offer) => {
    try {
      const candidateId = offer?.candidate_id;

      if (!candidateId) {
        console.warn("Candidate ID not found for offer");
        return;
      }
      const assignment = await getHrAssignmentByCandidate(candidateId);
      const hr = assignment?.hr1;
      if (!hr?.user_email) {
        console.warn("No assigned HR email found");
        return;
      }
      const notification = getOfferAcceptedNotificationTemplate({
        candidateName: offer?.candidate_name,
        position: offer?.position,
        offerId: offer?.id,
      });
      await sendEventNotification({
        toEmail: hr.user_email,
        recipientName: hr?.user_name || "HR",
        ...notification,
      });
    } catch (error) {
      console.error("Failed to send offer accepted notification", error);
    }
  };

  const handleUpload = async (uploadFn, label, file) => {
    if (!file) return;

    try {
      setUploadingType(label);
      clearNotice();
      await uploadFn(file);
      await fetchDocuments();
      await notifyAssignedHr(label);

      showNotice(`✅ ${label} uploaded successfully.`, "success");
    } catch (err) {
      showNotice(`❌ ${err.message || `Failed to upload ${label}.`}`, "error");
    } finally {
      setUploadingType(null);
    }
  };
  const handleSignatureSave = async (signatureFile) => {
    if (!selectedOffer?.id || !signatureFile) return;

    try {
      setSignatureLoading(true);
      clearNotice();

      const formData = new FormData();
      formData.append("signature", signatureFile);

      await signOfferLetter(selectedOffer.id, formData);

      try {
        await notifyOfferAcceptedHr(selectedOffer);
      } catch (error) {
        console.error(
          "Failed to send HR notification after offer acceptance",
          error,
        );
      }

      // await respondToOffer({
      //   offerId: selectedOffer.id,
      //   action: "accept",
      // });

      const refreshed = await getMyOffers();

      setMyOffers(refreshed?.offers || []);
      setShowSignatureModal(false);
      setSelectedOffer(null);

      showNotice("Offer accepted successfully.", "success");
    } catch (err) {
      showNotice(err?.message || "Failed to sign and accept offer.", "error");
    } finally {
      setSignatureLoading(false);
    }
  };
  const downloadOfferLetter = async (url, fileName = "OfferLetter.docx") => {
    if (!url) {
      showNotice("Offer letter download URL is unavailable.");
      return;
    }

    try {
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("hrms_token")}`,
        },
      });
      if (!response.ok) {
        throw new Error("Failed to download offer letter.");
      }
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      showNotice(error?.message || "Failed to download offer letter.");
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
  const menuItems = [
    {
      key: "dashboard",
      label: "Dashboard",
      icon: <LayoutDashboard size={18} />,
    },
    {
      key: "profile",
      label: "Profile",
      icon: <User size={18} />,
    },
    {
      key: "documents",
      label: "Documents",
      icon: <FileText size={18} />,
    },
    {
      key: "offers",
      label: "Offers",
      icon: <BadgeCheck size={18} />,
    },
    {
      key: "jobs",
      label: "Jobs",
      icon: <Briefcase size={18} />,
    },
  ];
  const renderSection = () => {
    switch (activeSection) {
      case "dashboard":
        return (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border bg-white p-5 shadow-sm">
                <div className="text-sm text-slate-500">Documents Uploaded</div>
                <div className="mt-2 text-3xl font-bold text-[#1F3766]">
                  {myDocuments?.documents?.length || 0} / 8
                </div>

                <p className="mt-2 text-xs text-slate-500">
                  Get started by uploading your required documents.
                </p>
              </div>

              <div className="rounded-2xl border bg-white p-5 shadow-sm">
                <div className="text-sm text-slate-500">
                  Onboarding Progress
                </div>

                <div className="mt-2 text-3xl font-bold text-[#1F3766]">
                  {Number(onboardingStatus?.overall_completion || 0).toFixed(0)}
                  %
                </div>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-[#1F3766]"
                    style={{
                      width: `${Number(onboardingStatus?.overall_completion || 0)}%`,
                    }}
                  />
                </div>

                <p className="mt-2 text-xs text-slate-500">
                  Complete your onboarding journey
                </p>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };
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
      <ToastContainer
        position="top-right"
        autoClose={3000}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        pauseOnHover
      />
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <aside className="rounded-2xl border bg-white p-4 shadow-sm h-fit">
            <div className="mb-6 border-b border-slate-200 pb-5">
              <div className="flex flex-col items-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#1F3766] text-2xl font-extrabold text-white shadow-md">
                  BX
                </div>

                <p className="mt-3 text-sm font-semibold uppercase tracking-[0.em] text-slate-500">
                  Candidate Portal
                </p>
              </div>
            </div>
            <div className="space-y-1">
              {menuItems.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setActiveSection(item.key)}
                  className={`w-full rounded-xl px-4 py-3 text-left text-sm font-medium transition ${
                    activeSection === item.key
                      ? "bg-[#1F3766] text-white"
                      : "text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {item.icon}
                    <span>{item.label}</span>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <div className="space-y-6 ">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-[#1F3766] px-5 py-4 shadow-sm">
              <div>
                <h2 className="text-2xl font-bold text-white">
                  Welcome back, {candidateName}
                </h2>

                <p className="mt-1 text-sm text-blue-100">
                  Track your onboarding progress and complete pending documents.
                </p>
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
            {renderSection()}

            {activeSection === "offers" &&
              (myOffers?.length > 0 ? (
                <Card
                  title="Offer Letters"
                  subtitle="View, download and respond to your offer letters."
                >
                  <div className="space-y-3">
                    {myOffers.map((o) => (
                      <div
                        key={o.id}
                        className="rounded-lg border bg-slate-50 p-3"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex gap-2">
                            <Button
                              variant="secondary"
                              onClick={() =>
                                o?.sharepoint_url &&
                                window.open(
                                  o.sharepoint_url,
                                  "_blank",
                                  "noopener,noreferrer",
                                )
                              }
                              disabled={!o?.sharepoint_url}
                            >
                              View
                            </Button>

                            <Button
                              variant="secondary"
                              onClick={() =>
                                downloadOfferLetter(
                                  o?.download_url,
                                  `${o?.position || "Offer"}-Letter.docx`,
                                )
                              }
                              disabled={!o?.download_url}
                            >
                              Download
                            </Button>
                          </div>

                          {String(o?.offer_status).toLowerCase() ===
                            "released" &&
                            !o?.candidate_response && (
                              <div className="flex gap-2">
                                <Button
                                  onClick={() => {
                                    setSelectedOffer(o);
                                    setShowSignatureModal(true);
                                  }}
                                  disabled={loading}
                                >
                                  Accept
                                </Button>

                                <Button
                                  variant="secondary"
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
                                        err?.message ||
                                          "Failed to decline offer.",
                                      );
                                    }
                                  }}
                                  disabled={loading}
                                >
                                  Decline
                                </Button>
                              </div>
                            )}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              ) : (
                <Card
                  title="Offer Letters"
                  subtitle="View, download and respond to your offer letters."
                >
                  <div className="rounded-lg border bg-slate-50 p-3 text-sm text-slate-600">
                    You don't have any offer letters yet.
                  </div>
                </Card>
              ))}

            {activeSection === "profile" && (
              <Card title="Personal Information">
                <div className="grid gap-3 md:grid-cols-2">
                  <Input
                    label="Department (Previous Company)"
                    value={personal.department}
                    onChange={(v) =>
                      setPersonal((p) => ({ ...p, department: v }))
                    }
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
                    label="Nationality"
                    value={personal.nationality}
                    onChange={(v) =>
                      setPersonal((p) => ({ ...p, nationality: v }))
                    }
                  />
                  <TextArea
                    label="Current Residential Address"
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
                        showNotice("Personal Information Saved.", "success");
                      } catch (err) {
                        showNotice(
                          err.message || "Failed to save personal info.",
                        );
                      }
                    }}
                    disabled={loading}
                  >
                    Save Personal Information
                  </Button>
                </div>
              </Card>
            )}
            {activeSection === "documents" && (
              <Card
                title="Document Verification Status"
                subtitle="Track the verification status of all uploaded documents."
              >
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
                              {DOC_LABELS[doc.document_type] ||
                                doc.document_type}
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
                      No documents uploaded yet. Upload your required documents
                      to begin verification.
                    </div>
                  )}
                </div>
              </Card>
            )}
            {activeSection === "documents" && (
              <Card
                title="Education Details"
                subtitle="Please provide details of your SSC, HSC, Bachelor's Degree, and Master's Degree (if completed)."
              >
                <div className="space-y-4">
                  {education.map((row, idx) => (
                    <div
                      key={idx}
                      className="grid gap-3 rounded-xl border p-3 md:grid-cols-2"
                    >
                      <Input
                        label="Institute / School / College"
                        value={row.education_institute}
                        onChange={(v) => {
                          const next = [...education];
                          next[idx].education_institute = v;
                          setEducation(next);
                        }}
                      />
                      <Input
                        label="Degree / Qualification"
                        value={row.degree}
                        onChange={(v) => {
                          const next = [...education];
                          next[idx].degree = v;
                          setEducation(next);
                        }}
                      />
                      <Input
                        label="Specialization / Field of Study"
                        value={row.field_of_study}
                        onChange={(v) => {
                          const next = [...education];
                          next[idx].field_of_study = v;
                          setEducation(next);
                        }}
                      />
                      <Input
                        label="Start Year"
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
                        label="Percentage / CGPA"
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
                        Document Submitted
                      </label>

                      <div className="flex items-center justify-between text-xs text-slate-500 md:col-span-2">
                        <span>
                          {row.id ? `Record ID: ${row.id}` : "New record"}
                        </span>

                        <Button
                          variant="danger"
                          onClick={async () => {
                            clearNotice();

                            if (row.id) {
                              setLoading(true);

                              try {
                                await deleteCandidateEducation(row.id);
                                const refreshed =
                                  await listCandidateEducation();

                                if (refreshed?.records?.length) {
                                  setEducation(
                                    refreshed.records.map(
                                      normalizeEducationRecord,
                                    ),
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

                                showNotice(
                                  "Education record deleted.",
                                  "success",
                                );
                              } catch (err) {
                                showNotice(
                                  err.message ||
                                    "Failed to delete education record.",
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
                    disabled={
                      loading || uploadingType === "Education Certificate"
                    }
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

                        showNotice("Education Details Saved.", "success");
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
            )}

            {activeSection === "documents" && (
              <Card
                title="Experience Details"
                subtitle="Please provide details of your previous employment and upload your experience letter."
              >
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
                        label="Designation / Job Title"
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
                        label="Total Experience (Years)"
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
                        Experience Letter Submitted
                      </label>

                      <div className="flex items-center justify-between text-xs text-slate-500 md:col-span-2">
                        <span>
                          {row.id ? `Record ID: ${row.id}` : "New record"}
                        </span>

                        <Button
                          variant="danger"
                          onClick={async () => {
                            clearNotice();

                            if (row.id) {
                              setLoading(true);

                              try {
                                await deleteCandidateExperience(row.id);
                                const refreshed =
                                  await listCandidateExperience();

                                if (refreshed?.records?.length) {
                                  setExperience(
                                    refreshed.records.map(
                                      normalizeExperienceRecord,
                                    ),
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

                                showNotice(
                                  "Experience record deleted.",
                                  "success",
                                );
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
                      handleUpload(
                        uploadExperienceLetter,
                        "Experience Letter",
                        file,
                      )
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

                        showNotice("Experience Details Saved.", "success");
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
            )}

            {activeSection === "documents" && (
              <Card
                title="PAN Details"
                subtitle="Please upload a clear copy of your PAN Card for identity verification."
              >
                <div className="grid gap-3 md:grid-cols-2">
                  <Input
                    label="PAN Number"
                    value={pan.pan}
                    onChange={(v) => setPan((p) => ({ ...p, pan: v }))}
                  />
                  <Input
                    label="Name as per PAN"
                    value={pan.name_in_pan}
                    onChange={(v) => setPan((p) => ({ ...p, name_in_pan: v }))}
                  />
                  <Input
                    label="Father's Name as per PAN"
                    value={pan.father_name_in_pan}
                    onChange={(v) =>
                      setPan((p) => ({ ...p, father_name_in_pan: v }))
                    }
                  />

                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={pan.pan_is_submitted}
                      onChange={(e) =>
                        setPan((p) => ({
                          ...p,
                          pan_is_submitted: e.target.checked,
                        }))
                      }
                    />
                    PAN Submitted
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
                    onUpload={(file) =>
                      handleUpload(uploadPan, "PAN Card", file)
                    }
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
                        showNotice("PAN Details Saved.", "success");
                      } catch (err) {
                        showNotice(
                          err.message || "Failed to Save PAN Details.",
                        );
                      }
                    }}
                  >
                    Save PAN
                  </Button>
                </div>
              </Card>
            )}

            {activeSection === "documents" && (
              <Card
                title="Aadhaar Details"
                subtitle="Please upload a clear copy of your Aadhaar Card for identity and address verification."
              >
                <div className="grid gap-3 md:grid-cols-2">
                  <Input
                    label="Aadhaar Number"
                    value={aadhar.aadhar}
                    onChange={(v) => setAadhar((a) => ({ ...a, aadhar: v }))}
                  />
                  <Input
                    label="Name as per Aadhaar"
                    value={aadhar.name_in_aadhar}
                    onChange={(v) =>
                      setAadhar((a) => ({ ...a, name_in_aadhar: v }))
                    }
                  />
                  <Input
                    label="Aadhaar Enrollment Number"
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
                    Aadhaar Submitted
                  </label>

                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={aadhar.is_verified}
                      onChange={(e) =>
                        setAadhar((a) => ({
                          ...a,
                          is_verified: e.target.checked,
                        }))
                      }
                    />
                    Aadhaar Verified
                  </label>
                </div>

                <div className="mt-4 flex items-center justify-between gap-3">
                  <DocumentUploadRow
                    label="Aadhaar Card"
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
                        showNotice("Aadhaar Details Saved.", "success");
                      } catch (err) {
                        showNotice(
                          err.message || "Failed to Save Aadhaar Details.",
                        );
                      }
                    }}
                  >
                    Save Aadhaar
                  </Button>
                </div>
              </Card>
            )}
            {activeSection === "documents" && (
              <Card
                title="UAN / PF Details"
                subtitle="Please upload your UAN / PF document for verification."
              >
                <DocumentUploadRow
                  label="UAN / PF Document"
                  onUpload={(file) =>
                    handleUpload(uploadUanPfDocument, "UAN / PF Document", file)
                  }
                  disabled={loading || uploadingType === "UAN / PF Document"}
                />
              </Card>
            )}
            {activeSection === "documents" && (
              <Card
                title="Bank Statements"
                subtitle="Please upload your bank statements for the last 3 months showing salary credits."
              >
                <DocumentUploadRow
                  label="Last 3 Months Bank Statements"
                  onUpload={(file) =>
                    handleUpload(uploadBankStatement, "Bank Statement", file)
                  }
                  disabled={loading || uploadingType === "Bank Statement"}
                />
              </Card>
            )}
            {activeSection === "documents" && (
              <Card
                title="Salary Slips"
                subtitle="Please upload your salary slips for the last 3 months."
              >
                <DocumentUploadRow
                  label="Last 3 Months Salary Slips"
                  onUpload={(file) =>
                    handleUpload(uploadSalarySlip, "Salary Slip", file)
                  }
                  disabled={loading || uploadingType === "Salary Slip"}
                />
              </Card>
            )}

            <div className="mt-4"></div>

            {activeSection === "dashboard" && onboardingStatus ? (
              <Card title="Onboarding Status">
                <div className="grid gap-3 md:grid-cols-1">
                  <div>
                    <div className="text-xs text-slate-500">
                      Overall completion
                    </div>
                    <div className="text-lg font-semibold">
                      {Number(
                        onboardingStatus?.overall_completion || 0,
                      ).toFixed(0)}
                      %
                    </div>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-green-500"
                        style={{
                          width: `${Number(
                            onboardingStatus?.overall_completion || 0,
                          )}%`,
                        }}
                      />
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
                            {{
                              personal_info: "Personal Information",
                              education: "Education",
                              experience: "Experience",
                              pan: "PAN",
                              aadhar: "Aadhaar",
                            }[key] ||
                              String(key)
                                .replace(/_/g, " ")
                                .replace(/\b\w/g, (c) => c.toUpperCase())}
                          </div>
                          <div>
                            Completed: {value?.completed ? "Yes" : "No"}
                          </div>
                          {"verified" in (value || {}) ? (
                            <div>
                              Verified: {value?.verified ? "Yes" : "No"}
                            </div>
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
            {activeSection === "jobs" && (
              <Card
                title={`Jobs & Apply (${activeJobs?.length || 0})`}
                subtitle="Browse available positions and submit applications."
              >
                <div className="space-y-3">
                  {activeJobs?.length ? (
                    activeJobs.slice(0, 10).map((j) => (
                      <div
                        key={j?.job_id || j?.id}
                        className="rounded-lg border bg-white p-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold">
                              {j?.job_title || "Untitled Job"}
                            </div>
                            <div className="text-xs text-slate-600">
                              {j?.job_location || "—"} •{" "}
                              {j?.company_name || "—"}
                            </div>
                            <div className="mt-1 flex items-center gap-2">
                              <StatusBadge
                                status={normalizeJobStatus(j?.job_status)}
                              />
                              <span className="text-xs text-slate-500">
                                {j?.job_id || "-"}
                              </span>
                            </div>
                          </div>
                          <Button
                            onClick={() => handleApplyForJob(j?.job_id)}
                            disabled={!profile?.candidate_mobile || !j?.job_id}
                          >
                            Apply
                          </Button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-slate-600">
                      No job openings are available at the moment.
                    </div>
                  )}
                  <div className="rounded-xl border bg-slate-50 p-3 text-xs text-slate-600">
                    <div className="mb-2 font-semibold text-slate-700">
                      Resume for Application (Optional)
                    </div>
                    <input
                      type="file"
                      accept=".pdf,.doc,.docx"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        setJobResumeFile(file || null);
                      }}
                    />
                    <div className="mt-1">
                      {jobResumeFile
                        ? `Selected: ${jobResumeFile.name} (${(
                            jobResumeFile.size / 1024
                          ).toFixed(1)} KB)`
                        : "No resume selected."}
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">
                    Jobs list is sourced from active/public jobs.
                  </div>
                </div>
              </Card>
            )}
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

        <SignatureModal
          isOpen={showSignatureModal}
          onClose={() => {
            setShowSignatureModal(false);
            setSelectedOffer(null);
          }}
          onSave={handleSignatureSave}
          loading={signatureLoading}
          submitButtonText="Sign & Accept"
        />
      </div>
    </div>
  );
}
