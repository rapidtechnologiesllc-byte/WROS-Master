// HR create-candidate screen with optional resume upload and email.
import { useEffect, useState } from "react";
import { FileText, Users } from "lucide-react";
import { createCandidate } from "../services/api/candidates";
import { uploadResume } from "../services/api/documents";
import { getMicrosoftSigninUrl } from "../services/api/msgraph";
import { sendPlainEmail } from "../services/api/email";
import {
  Button,
  Card,
  Input,
  Select,
  LocationCascadeSelect,
  formatLocation,
  parseLocation,
} from "../components/ui";
import RateField from "../components/ui/RateField";
import {
  createCandidateHistoryEvent,
  HISTORY_EVENT_TYPES,
} from "../services/api/candidateHistory";
import {
  extractResumeText,
  inferFieldsFromResumeText,
} from "../utils/resumeAutofill";
import { assignJob, getAllJobs } from "../services/api/jobs";
import { mapJobFromApi } from "../App";
import { ScreenLevelBanner, useScreenBanner, ValidationSummary } from "../components/ScreenLevelBanner";
import { useNavigate } from "react-router-dom";
import { useRef } from "react";
import { handleApiError } from "../utils/apiErrorHandler";

// Added 2026-07-23 -- real bug: the Mobile input used to strip any
// country code the candidate typed (removed a leading "91", hard-capped
// to 10 digits) and candidateMobile was sent to WhatsApp as-is with no
// prepended code (app.services.whatsapp_routing_service.send_whatsapp_
// message uses candidate.candidateMobile directly as the "to" number),
// so a non-Indian number was silently unreachable over WhatsApp. Not an
// exhaustive ISO list -- the common countries this platform actually
// recruits in/for, easy to extend.
const COUNTRY_CODES = [
  { value: "+91", label: "+91 (India)" },
  { value: "+1", label: "+1 (US/Canada)" },
  { value: "+44", label: "+44 (UK)" },
  { value: "+61", label: "+61 (Australia)" },
  { value: "+971", label: "+971 (UAE)" },
  { value: "+65", label: "+65 (Singapore)" },
  { value: "+49", label: "+49 (Germany)" },
  { value: "+63", label: "+63 (Philippines)" },
];

const SOURCE_OPTIONS = [
  { value: "Campus Hiring", label: "Campus Hiring" },
  { value: "Conference", label: "Conference" },
  { value: "LinkedIn", label: "LinkedIn" },
  { value: "Career Site", label: "Career Site" },
  { value: "Employee Referral", label: "Employee Referral" },
  { value: "Indeed", label: "Indeed" },
  { value: "Naukri", label: "Naukri" },
  { value: "Monster", label: "Monster" },
  { value: "Other", label: "Other" },
];

export default function CandidateCreate({ onBack, onSave }) {
  const { banner, showSuccess, showError, dismiss } = useScreenBanner();
  const [candidateRole, setCandidateRole] = useState("");
  const [candidateJobTitle, setCandidateJobTitle] = useState("");
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [countryCode, setCountryCode] = useState("+91");
  const [gender, setGender] = useState("");
  const [dob, setDob] = useState("");
  const [source, setSource] = useState("");
  const [experience, setExperience] = useState("");
  const [skills, setSkills] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [expectedSalary, setExpectedSalary] = useState("");
  const [currentSalary, setCurrentSalary] = useState("");
  const [locationValue, setLocationValue] = useState({
    countryCode: "",
    stateCode: "",
    city: "",
  });
  const [assignedHrManagerId, setAssignedHrManagerId] = useState("");
  const [assignedReportManagerId, setAssignedReportManagerId] = useState("");
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeParsing, setResumeParsing] = useState(false);
  const [sendLoginEmail, setSendLoginEmail] = useState(true);
  const [actionNotice, setActionNotice] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [educationRows, setEducationRows] = useState([]);
  const [experienceRows, setExperienceRows] = useState([]);
  const [errors, setErrors] = useState({});
  const [users, setUsers] = useState([]);
  const today = new Date().toISOString().slice(0, 10);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [isAssigning, setIsAssigning] = useState(false);
  const [jobName, setJobName] = useState("");
  const [availableJobs, setAvailableJobs] = useState([]);
  const [currentSalaryRateType, setCurrentSalaryRateType] = useState("$/Year");
  const [expectedSalaryRateType, setExpectedSalaryRateType] = useState("$/Year");
  const [showSkillsModal, setShowSkillsModal] = useState(false);
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [customSource, setCustomSource] = useState("");
  const [showEmployeeReferralList, setShowEmployeeReferralList] = useState(false);
  const navigate = useNavigate();

  // Helper function to check if user is in recruitment department
  const isRecruitmentUser = () => {
    try {
      const userInfo = localStorage.getItem("user_info");
      if (!userInfo) return false;

      const user = JSON.parse(userInfo);
      // Check job title or department for recruitment keywords
      const jobTitle = (user.UserJobTitle || "").toLowerCase();
      const department = (user.department || "").toLowerCase();

      const recruitmentKeywords = ["recruit", "talent", "staffing", "hr", "hiring", "acquisition"];
      return recruitmentKeywords.some(
        keyword => jobTitle.includes(keyword) || department.includes(keyword)
      );
    } catch (error) {
      return false;
    }
  };

  // Initialize source and assignment based on recruiter status
  useEffect(() => {
    const initializeSource = () => {
      try {
        const userInfo = localStorage.getItem("user_info");
        if (userInfo) {
          const user = JSON.parse(userInfo);

          // Auto-assign to current user if they are recruitment staff
          if (isRecruitmentUser()) {
            setAssignedHrManagerId(user.UserID || "");
          }
        }
      } catch (error) {
        console.log("Could not auto-initialize recruiter source:", error);
      }
    };

    initializeSource();
  }, []);

  // Field refs for scrolling to errors
  const fieldRefs = useRef({
    firstName: null,
    lastName: null,
    email: null,
    mobile: null,
    gender: null,
  });

  useEffect(() => {
    loadAvailableJobs();
  }, []);

  const loadAvailableJobs = async () => {
    try {
      const jobs = await getAllJobs();
      const openJobs = jobs.filter(job => job.jobStatus === "OPEN" || job.status === "OPEN");
      setAvailableJobs(openJobs);
    } catch (error) {
      console.log("Could not load jobs", error);
    }
  };

  const handleFieldClick = (fieldName) => {
    const ref = fieldRefs.current[fieldName];
    if (ref) {
      ref.focus();
      ref.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const clearFieldError = (field) => {
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const inferEducationRows = (resumeText) => {
    if (!resumeText) return [];

    const text = resumeText
      .replace(/\r/g, "\n")
      .replace(/[•|]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const educationRegex = /(education|academic|academics|qualification)/i;
    const educationMatch = text.match(educationRegex);
    if (!educationMatch) return [];
    let educationSection = text.slice(educationMatch.index);
    const nextSectionRegex =
      /(experience|work experience|projects|skills|certifications|summary|profile)/i;

    const nextSectionMatch = educationSection.match(nextSectionRegex);

    if (nextSectionMatch && nextSectionMatch.index > 50) {
      educationSection = educationSection.slice(0, nextSectionMatch.index);
    }
    const degreeRegex =
      /\b(B\.?\s?TECH|M\.?\s?TECH|B\.?\s?E|M\.?\s?E|BCA|MCA|BBA|MBA|BSC|MSC|SSC|HSC|10TH|12TH|PHD|DIPLOMA|BACHELOR OF TECHNOLOGY|MASTER OF TECHNOLOGY|BACHELOR OF COMPUTER APPLICATION|MASTER OF COMPUTER APPLICATION)\b/gi;

    const degreeMatches = [...educationSection.matchAll(degreeRegex)];

    if (!degreeMatches.length) return [];

    const results = [];

    for (let i = 0; i < degreeMatches.length; i++) {
      const currentMatch = degreeMatches[i];
      const start = currentMatch.index;
      const end =
        i + 1 < degreeMatches.length
          ? degreeMatches[i + 1].index
          : educationSection.length;
      const block = educationSection.slice(start, end).trim();

      if (!block) continue;
      const degree = currentMatch[0].replace(/\s+/g, " ").toUpperCase();
      let institute = "";
      const instituteRegex =
        /([A-Z][A-Za-z0-9,&().\- ]+(College|University|Institute|School)[A-Za-z0-9,&().\- ]*)/i;
      const instituteMatch = block.match(instituteRegex);
      if (instituteMatch) {
        institute = instituteMatch[0].trim();
      }
      const yearMatches = block.match(/\b(19|20)\d{2}\b/g) || [];
      let percentage = "";
      const percentageRegex = /(\d+(\.\d+)?)\s*(%|CGPA|GPA|\/10)/i;
      const percentageMatch = block.match(percentageRegex);
      if (percentageMatch) {
        percentage = percentageMatch[1];
      }
      let field_of_study = "";
      const fieldRegex = /in\s([A-Za-z&\s]+)/i;
      const fieldMatch = block.match(fieldRegex);
      if (fieldMatch) {
        field_of_study = fieldMatch[1].trim().replace(/\s+/g, " ");
      }
      results.push({
        degree,
        education_institute: institute,
        starting_year: yearMatches[0] || "",
        year_of_passing: yearMatches[1] || "",
        field_of_study,
        percentage,
      });
    }

    const uniqueResults = results.filter(
      (item, index, self) =>
        index ===
        self.findIndex(
          (t) =>
            t.degree === item.degree && t.starting_year === item.starting_year,
        ),
    );

    return uniqueResults;
  };

  const inferExperienceRows = (resumeText) => {
    if (!resumeText) return [];

    const text = String(resumeText)
      .replace(/\r/g, "\n")
      .replace(/[•▪◦·]/g, " ")
      .replace(/\t/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const expRegex =
      /(experience|work experience|professional experience|employment|career history)/i;
    const expMatch = text.match(expRegex);

    if (!expMatch) return [];
    let experienceSection = text.slice(expMatch.index);
    const stopRegex =
      /(education|projects|skills|technical skills|certifications|achievements|summary)/i;
    const stopMatch = experienceSection.match(stopRegex);

    if (stopMatch && stopMatch.index > 100) {
      experienceSection = experienceSection.slice(0, stopMatch.index);
    }
    const dateRangeRegex =
      /((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s?\d{4}|\d{1,2}\/\d{4})\s*[-–to]+\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s?\d{4}|\d{1,2}\/\d{4}|Present|Current)/gi;

    const matches = [...experienceSection.matchAll(dateRangeRegex)];

    if (!matches.length) return [];

    const blocks = [];
    for (let i = 0; i < matches.length; i++) {
      const current = matches[i];

      const start = Math.max(0, current.index - 150);

      const end =
        i + 1 < matches.length ? matches[i + 1].index : current.index + 300;

      const block = experienceSection.slice(start, end);

      blocks.push({
        block,
        dates: current[0],
      });
    }

    const titleKeywords = [
      "engineer",
      "developer",
      "intern",
      "analyst",
      "consultant",
      "manager",
      "designer",
      "architect",
      "scientist",
      "lead",
      "trainee",
      "specialist",
      "associate",
      "executive",
    ];

    const results = [];

    for (const item of blocks) {
      const block = item.block;

      const dates =
        item.dates.match(
          /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s?\d{4}\b|\b\d{1,2}\/\d{4}\b/gi,
        ) || [];

      const start_date = normalizeDate(dates[0]);

      const end_date = normalizeDate(dates[1]);

      let company_name = "";
      const beforeDate = block.split(item.dates)[0].trim();

      const possibleLines = beforeDate
        .split(/[-–|]/)
        .map((s) => s.trim())
        .filter(Boolean);

      if (possibleLines.length) {
        company_name = possibleLines[possibleLines.length - 1];
      }
      company_name = company_name.replace(/\s+/g, " ").trim();
      let job_title = "";

      const sentences = block.split(/[.!]/);

      for (const sentence of sentences) {
        const lower = sentence.toLowerCase();

        if (titleKeywords.some((k) => lower.includes(k))) {
          job_title = sentence
            .replace(company_name, "")
            .replace(item.dates, "")
            .trim();

          break;
        }
      }

      let score = 0;

      if (company_name) score++;
      if (job_title) score++;
      if (start_date) score++;

      if (score < 2) continue;

      results.push({
        company_name,
        job_title,
        start_date,
        end_date,
      });
    }

    return results.filter(
      (item, index, self) =>
        index ===
        self.findIndex(
          (t) =>
            t.company_name === item.company_name &&
            t.start_date === item.start_date,
        ),
    );
  };

  function normalizeDate(dateStr) {
    if (!dateStr) return "";

    const months = {
      jan: "01",
      feb: "02",
      mar: "03",
      apr: "04",
      may: "05",
      jun: "06",
      jul: "07",
      aug: "08",
      sep: "09",
      oct: "10",
      nov: "11",
      dec: "12",
    };

    dateStr = dateStr.trim();
    if (/^\d{1,2}\/\d{4}$/.test(dateStr)) {
      const [month, year] = dateStr.split("/");

      return `${year}-${month.padStart(2, "0")}-01`;
    }
    const parts = dateStr.split(/\s+/);

    if (parts.length >= 2) {
      const month = months[parts[0].slice(0, 3).toLowerCase()] || "01";

      const year = parts.find((p) => /\d{4}/.test(p)) || "0000";

      return `${year}-${month}-01`;
    }

    if (/^\d{4}$/.test(dateStr)) {
      return `${dateStr}-01-01`;
    }

    return "";
  }

  const handleResumeFileChange = async (event) => {
    const file = event.target.files?.[0] || null;
    setResumeFile(file);
    if (!file) return;
    setResumeParsing(true);
    setActionNotice("");
    try {
      // Auto-set source when recruiter/HR staff uploads resume
      if (isRecruitmentUser() && !source) {
        try {
          const userInfo = localStorage.getItem("user_info");
          if (userInfo) {
            const user = JSON.parse(userInfo);
            const jobTitle = (user.UserJobTitle || "").toLowerCase();
            // Set source based on specific job title
            if (jobTitle.includes("recruiter")) {
              setSource("Recruiter");
            } else if (jobTitle.includes("hr") || jobTitle.includes("talent")) {
              setSource("HR");
            } else {
              setSource("Internal");
            }
          }
        } catch (e) {
          // If parsing fails, just continue without auto-setting source
        }
      }

      const text = await extractResumeText(file);
      const fields = inferFieldsFromResumeText(text);
      if (fields.email) {
        setEmail(fields.email);
        clearFieldError("email");
      }
      if (fields.firstName) {
        setFirstName(fields.firstName);
        clearFieldError("firstName");
      }
      if (fields.middleName) setMiddleName(fields.middleName);
      if (fields.lastName) {
        setLastName(fields.lastName);
        clearFieldError("lastName");
      }
      if (fields.mobile) {
        setMobile(fields.mobile);
        clearFieldError("mobile");
      }
      if (fields.skills) setSkills(fields.skills);
      if (fields.experience) setExperience(fields.experience);
      if (fields.currentLocation) setLocationValue(parseLocation(fields.currentLocation));
      if (fields?.jobTitle) setJobName(fields?.jobTitle);
      const inferredEducation = inferEducationRows(text);
      if (inferredEducation.length) setEducationRows(inferredEducation);
      const inferredExperience = inferExperienceRows(text, fields._nameLine);
      if (inferredExperience.length) setExperienceRows(inferredExperience);
      const filled = Object.keys(fields).filter((k) => fields[k]).length;
      setActionNotice(
        filled
          ? `Resume parsed: filled ${filled} field(s). Review and correct before saving.`
          : "Resume attached. Could not infer details — fill the form manually.",
      );
    } catch (err) {
      setActionNotice(err.message || "Could not read resume for auto-fill.");
    } finally {
      setResumeParsing(false);
    }
  };

  const handleCreateCandidate = async () => {
    const newErrors = {};

    if (!firstName.trim()) newErrors.firstName = "First Name is required.";
    if (!lastName.trim()) newErrors.lastName = "Last Name is required.";
    if (!gender.trim()) newErrors.gender = "Gender is required.";
    if (!mobile.trim()) newErrors.mobile = "Mobile is required.";
    else if (!/^\d{7,15}$/.test(mobile.replace(/\D/g, ''))) newErrors.mobile = "Mobile must be 7-15 digits.";
    if (!email.trim()) newErrors.email = "Email is required.";
    if (!locationValue?.countryCode || !locationValue?.city) newErrors.location = "Location (Country and City) is required.";
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    const filledEducationRows = educationRows.filter((row) =>
      [
        row.education_institute,
        row.degree,
        row.field_of_study,
        row.starting_year,
        row.year_of_passing,
        row.percentage,
      ].some((v) => String(v || "").trim()),
    );
    const invalidEducation = filledEducationRows.some((row) =>
      [
        row.education_institute,
        row.degree,
        row.field_of_study,
        row.starting_year,
        row.year_of_passing,
        row.percentage,
      ].some((v) => !String(v || "").trim()),
    );
    if (invalidEducation) {
      setActionNotice(
        "Please complete all education prefill fields or remove incomplete rows.",
      );
      return;
    }

    const filledExperienceRows = experienceRows.filter((row) =>
      [
        row.company_name,
        row.job_title,
        row.start_date,
        row.end_date,
        row.year_of_experience,
      ].some((v) => String(v || "").trim()),
    );
    const invalidExperience = filledExperienceRows.some((row) =>
      [
        row.company_name,
        row.job_title,
        row.start_date,
        row.end_date,
        row.year_of_experience,
      ].some((v) => !String(v || "").trim()),
    );
    if (invalidExperience) {
      setActionNotice(
        "Please complete all experience prefill fields or remove incomplete rows.",
      );
      return;
    }

    setErrors({});
    setActionNotice("");
    setIsSaving(true);

    try {
      // Create the candidate in backend and receive generated password.
      // Format location: only include if all required fields are selected
      let formattedLocation = null;
      if (locationValue?.countryCode && locationValue?.city) {
        const loc = formatLocation(locationValue);
        // Ensure it's a string, not an object
        formattedLocation = typeof loc === 'string' ? loc : null;
      }

      const data = await createCandidate({
        candidate_email: email.trim(),
        candidate_role: "Candidate",
        candidate_job_title: candidateJobTitle || null,
        candidate_first_name: firstName || null,
        candidate_middle_name: middleName || null,
        candidate_last_name: lastName || null,
        candidate_mobile: mobile ? `${countryCode}${mobile}` : null,
        candidate_gender: gender || null,
        candidate_date_of_birth: dob || null,
        candidate_source: source === "Other" ? customSource : (source || null),
        candidate_experience: experience || null,
        candidate_skills: selectedSkills.length > 0 ? selectedSkills.map(s => s.name).join(", ") : null,
        candidate_joining_date: joiningDate || null,
        candidate_expected_salary: expectedSalary || null,
        candidate_expected_salary_type: expectedSalaryRateType || null,
        candidate_current_salary: currentSalary || null,
        candidate_current_salary_type: currentSalaryRateType || null,
        candidate_current_location: formattedLocation,
        assigned_hr_manager_id: assignedHrManagerId || null,
        assigned_report_manager_id: assignedReportManagerId || null,
        education_records: filledEducationRows.length
          ? filledEducationRows.map((row) => ({
              education_institute: row.education_institute.trim(),
              degree: row.degree.trim(),
              field_of_study: row.field_of_study.trim(),
              starting_year: row.starting_year.trim(),
              year_of_passing: row.year_of_passing.trim(),
              percentage: row.percentage.trim(),
              submitted_at: today,
              document_is_submitted: false,
            }))
          : null,
        experience_records: filledExperienceRows.length
          ? filledExperienceRows.map((row) => ({
              company_name: row.company_name.trim(),
              job_title: row.job_title.trim(),
              start_date: row.start_date,
              end_date: row.end_date,
              year_of_experience: row.year_of_experience.trim(),
              submitted_at: today,
              document_is_submitted: false,
            }))
          : null,
      });
      const candidateName = [firstName, middleName, lastName]
        .filter(Boolean)
        .join(" ")
        .trim();

      const createdCandidateId = data?.candidate_id;
      const candidateEmail = email?.trim();
      const candidatePassword = data?.candidate_password;
      const candidatePortalUrl = "https://hrms.blitzenx.com/";

      const createdCandidate = {
        id: createdCandidateId,
        name: candidateName || "New Candidate",
        email: candidateEmail,
        phone: mobile ? `${countryCode}${mobile}` : mobile,
        jobTitle: candidateJobTitle || jobName || "",
        skills: String(skills || "")
          .split(",")
          .map((skill) => skill.trim())
          .filter(Boolean),
        status: "New",
      };
      let nextNotice = "Candidate created successfully.";
      if (resumeFile) {
        if (!createdCandidateId) {
          nextNotice = `${nextNotice} Resume skipped because candidate id is missing.`;
        } else {
          try {
            await uploadResume({
              candidateId: createdCandidateId,
              file: resumeFile,
            });
            nextNotice = `${nextNotice} Resume uploaded.`;
            showSuccess(nextNotice);
          } catch (uploadErr) {
            console.error("Resume upload failed:", uploadErr);
            nextNotice = `${nextNotice} Resume upload failed: ${
              uploadErr?.message || "Unknown error"
            }.`;
            showError(nextNotice);
          }
        }
      } else {
        showSuccess(nextNotice);
      }
      setActionNotice(nextNotice);
      return createdCandidate;
    } catch (err) {
      const errorMessage = handleApiError(err, "Failed to create candidate.");
      showError(errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAndAssignJob = async () => {
    setIsAssigning(true);

    try {
      const candidateId = await handleCreateCandidate();
      if (!candidateId?.id) {
        showError("Candidate creation failed");
        return;
      }
      const result = await assignJob(selectedJobId, candidateId?.id, {
        application_status: "Applied",
      });
      if (result?.status === 201) {
        showSuccess("Job assigned successfully ✅");
        onSave(candidateId);
      }
    } catch (err) {
      const errorMessage = handleApiError(err, "Candidate created but job assignment failed.");
      showError(errorMessage);
    } finally {
      setIsAssigning(false);
    }
  };

  const handleSaveOnly = async () => {
    try {
      const candidate = await handleCreateCandidate();
      console.log("Created candidate:", candidate);

      if (!candidate?.id) {
        console.error("Candidate creation returned no ID", candidate);
        return;
      }

      try {
        await createCandidateHistoryEvent(candidate.id, {
          event_type: HISTORY_EVENT_TYPES.APPLIED,
        });
      } catch (historyErr) {
        console.error("Failed to create history event (continuing anyway):", historyErr);
      }

      console.log("Calling onSave with:", candidate);
      onSave(candidate);
    } catch (error) {
      console.error("Failed in handleSaveOnly:", error);
      const errorMessage = handleApiError(error, "Failed to create candidate");
      showError(errorMessage);
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Create Candidate"
        icon={<Users className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={() => navigate("/candidates")}>
            Back
          </Button>
        }
      >
        {actionNotice && (
          <div className="mb-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-900">{actionNotice}</p>
          </div>
        )}
        {Object.keys(errors).length > 0 && (
          <ValidationSummary errors={errors} onFieldClick={handleFieldClick} />
        )}
        {banner && (
          <ScreenLevelBanner
            type={banner.type}
            message={banner.message}
            onDismiss={dismiss}
            onRetry={banner.type === "error" ? () => {} : undefined}
          />
        )}
        <div className="mb-4 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-800">
            <FileText className="h-4 w-4 text-blue-600" />
            Resume attachment
          </div>
          <p className="mb-3 text-xs text-gray-600">
            Upload the candidate's resume in PDF or DOCX format.
          </p>
          <input
            type="file"
            accept=".pdf,.docx"
            disabled={resumeParsing}
            onChange={handleResumeFileChange}
            className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-blue-600 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-blue-700"
          />
          {resumeParsing ? (
            <div className="mt-2 text-xs font-medium text-blue-700">
              Reading resume…
            </div>
          ) : resumeFile ? (
            <div className="mt-2 text-xs text-gray-600">
              Selected: {resumeFile.name}
            </div>
          ) : null}
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <Select
              label="Open Jobs (Optional)"
              value={selectedJobId}
              onChange={(jobId) => {
                setSelectedJobId(jobId);
                const selected = availableJobs.find(j => j.jobID === jobId);
                if (selected) {
                  setJobName(selected.jobTitle || selected.title || "");
                } else {
                  setJobName("");
                }
              }}
              options={[
                { value: "", label: "Select a job (optional)" },
                ...availableJobs.map(job => ({
                  value: job.jobID,
                  label: job.jobTitle || job.title
                }))
              ]}
            />
          </div>
          <div>
            <Input
              ref={(ref) => (fieldRefs.current.email = ref?.input)}
              label="Email *"
              value={email}
              onChange={(value) => {
                setEmail(value);
                clearFieldError("email");
              }}
              actionNotice={actionNotice}
              error={errors.email}
            />
            {errors.email ? (
              <div className="mt-1 text-xs text-red-500">{errors.email}</div>
            ) : null}
          </div>

          <div>
            <Input
              ref={(ref) => (fieldRefs.current.firstName = ref?.input)}
              label="First Name *"
              value={firstName}
              onChange={(value) => {
                setFirstName(value);
                clearFieldError("firstName");
              }}
              actionNotice={actionNotice}
              error={errors.firstName}
            />
            {errors.firstName ? (
              <div className="mt-1 text-xs text-red-500">
                {errors.firstName}
              </div>
            ) : null}
          </div>

          <Input
            label="Middle Name"
            value={middleName}
            onChange={setMiddleName}
          />

          <div>
            <Input
              ref={(ref) => (fieldRefs.current.lastName = ref?.input)}
              label="Last Name *"
              value={lastName}
              onChange={(value) => {
                setLastName(value);
                clearFieldError("lastName");
              }}
              actionNotice={actionNotice}
              error={errors.lastName}
            />
            {errors.lastName ? (
              <div className="mt-1 text-xs text-red-500">{errors.lastName}</div>
            ) : null}
          </div>

          <div className="grid grid-cols-[minmax(0,7rem)_1fr] gap-2">
            <Select
              label="Code"
              value={countryCode}
              onChange={setCountryCode}
              options={COUNTRY_CODES}
            />
            <Input
              label="Mobile *"
              value={mobile}
              onChange={(value) => {
                // Country code lives in its own field now -- just strip
                // non-digits, no destructive stripping/hard-capping to
                // 10 (real bug: this used to silently discard any
                // country code the candidate typed, and always cap at
                // exactly 10 digits regardless of the country).
                const cleanedValue = value.replace(/\D/g, "").slice(0, 15);
                setMobile(cleanedValue);
                clearFieldError("mobile");
              }}
              type="tel"
              actionNotice={actionNotice}
              error={errors.mobile}
            />
            {errors.mobile ? (
              <div className="mt-1 text-xs text-red-500">{errors.mobile}</div>
            ) : null}
          </div>

          <div>
            <Select
              label="Gender *"
              value={gender}
              onChange={(value) => {
                setGender(value);
                clearFieldError("gender");
              }}
              options={["", "Female", "Male", "Other"]}
              error={errors.gender}
            />
            {errors.gender ? (
              <div className="mt-1 text-xs text-red-500">{errors.gender}</div>
            ) : null}
          </div>
          <div>
            <Input
              label="Date of Birth"
              value={dob}
              onChange={(value) => {
                setDob(value);
                clearFieldError("dob");
              }}
              type="date"
            />
          </div>
          <div>
            <Select
              label="Source"
              value={source}
              onChange={(value) => {
                setSource(value);
                setCustomSource("");
                setShowEmployeeReferralList(value === "Employee Referral");
              }}
              options={[
                { value: "", label: "Select source" },
                ...SOURCE_OPTIONS.map(opt => ({ value: opt.value, label: opt.label }))
              ]}
            />
          </div>

          {source === "Other" && (
            <Input
              label="Other Source"
              value={customSource}
              onChange={setCustomSource}
              placeholder="Please specify the source"
            />
          )}

          {showEmployeeReferralList && (
            <div className="md:col-span-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-gray-700 mb-2">Select referring employee (feature coming soon)</p>
              <p className="text-xs text-gray-500">Employee list will be populated here</p>
            </div>
          )}

          <div className="md:col-span-2">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-semibold text-gray-700">Skills</div>
              <button
                type="button"
                onClick={() => setShowSkillsModal(true)}
                className="text-xs text-blue-600 hover:text-blue-700 font-semibold"
              >
                {selectedSkills.length > 0 ? `Edit (${selectedSkills.length})` : "Add Skills"}
              </button>
            </div>
            {selectedSkills.length > 0 ? (
              <div className="text-sm text-gray-600">
                {selectedSkills.map(s => s.name).join(", ")}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No skills added. Click "Add Skills" to add your top skills.</p>
            )}
          </div>

          <RateField
            label="Current Salary"
            value={currentSalary}
            onValueChange={setCurrentSalary}
            rateType={currentSalaryRateType}
            onRateTypeChange={setCurrentSalaryRateType}
            rateTypeOptions={["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year"]}
          />

          <RateField
            label="Expected Salary"
            value={expectedSalary}
            onValueChange={setExpectedSalary}
            rateType={expectedSalaryRateType}
            onRateTypeChange={setExpectedSalaryRateType}
            rateTypeOptions={["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year"]}
          />

          <div className="md:col-span-2">
            <div className="mb-1 text-xs font-semibold text-gray-700">
              Current Location *
            </div>
            <LocationCascadeSelect value={locationValue} onChange={setLocationValue} />
          </div>

          <Input
            label="Availability Date"
            value={joiningDate}
            onChange={(value) => {
              setJoiningDate(value);
            }}
            type="date"
          />
        </div>

        <div className="mt-4 space-y-3">
          <div className="rounded-xl border bg-slate-50 p-3">
            <div className="text-sm font-semibold text-slate-800">
              Education records
            </div>
            <div className="mt-3 space-y-3">
              {educationRows.map((row, idx) => {
                const isRowIncomplete = [
                  row.education_institute,
                  row.degree,
                  row.field_of_study,
                  row.starting_year,
                  row.year_of_passing,
                  row.percentage,
                ].some((v) => !String(v || "").trim());
                const hasAnyField = [
                  row.education_institute,
                  row.degree,
                  row.field_of_study,
                  row.starting_year,
                  row.year_of_passing,
                  row.percentage,
                ].some((v) => String(v || "").trim());
                const shouldHighlight = actionNotice && hasAnyField && isRowIncomplete;

                return (
                <div
                  key={`edu-${idx}`}
                  className={`grid gap-2 rounded-lg border p-3 md:grid-cols-2 ${
                    shouldHighlight
                      ? "border-red-400 bg-red-50"
                      : "border-gray-200 bg-white"
                  }`}
                >
                  <Input
                    label="Institute"
                    value={row.education_institute}
                    onChange={(v) =>
                      setEducationRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, education_institute: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Degree"
                    value={row.degree}
                    onChange={(v) =>
                      setEducationRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, degree: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Field of Study"
                    value={row.field_of_study}
                    onChange={(v) =>
                      setEducationRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, field_of_study: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Starting Year"
                    value={row.starting_year}
                    onChange={(v) =>
                      setEducationRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, starting_year: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Year of Passing"
                    value={row.year_of_passing}
                    onChange={(v) =>
                      setEducationRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, year_of_passing: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Percentage"
                    value={row.percentage}
                    onChange={(v) =>
                      setEducationRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, percentage: v } : r,
                        ),
                      )
                    }
                  />
                  <div className="md:col-span-2 flex justify-end">
                    <Button
                      variant="danger"
                      onClick={() =>
                        setEducationRows((prev) =>
                          prev.filter((_, i) => i !== idx),
                        )
                      }
                    >
                      Remove Row
                    </Button>
                  </div>
                </div>
              );
              })}
              <Button
                variant="secondary"
                onClick={() =>
                  setEducationRows((prev) => [
                    ...prev,
                    {
                      education_institute: "",
                      degree: "",
                      field_of_study: "",
                      starting_year: "",
                      year_of_passing: "",
                      percentage: "",
                    },
                  ])
                }
              >
                Add Education Row
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-slate-50 p-3">
            <div className="text-sm font-semibold text-slate-800">
              Experience records
            </div>
            <div className="mt-3 space-y-3">
              {experienceRows.map((row, idx) => {
                const isRowIncomplete = [
                  row.company_name,
                  row.job_title,
                  row.start_date,
                  row.end_date,
                  row.year_of_experience,
                ].some((v) => !String(v || "").trim());
                const hasAnyField = [
                  row.company_name,
                  row.job_title,
                  row.start_date,
                  row.end_date,
                  row.year_of_experience,
                ].some((v) => String(v || "").trim());
                const shouldHighlight = actionNotice && hasAnyField && isRowIncomplete;

                return (
                <div
                  className={`grid gap-2 rounded-lg border p-3 md:grid-cols-2 ${
                    shouldHighlight
                      ? "border-red-400 bg-red-50"
                      : "border-gray-200 bg-white"
                  }`}
                  key={`exp-${idx}`}
                >
                  <Input
                    label="Company Name"
                    value={row.company_name}
                    onChange={(v) =>
                      setExperienceRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, company_name: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Job Title"
                    value={row.job_title}
                    onChange={(v) =>
                      setExperienceRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, job_title: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Start Date"
                    type="date"
                    value={row.start_date}
                    onChange={(v) =>
                      setExperienceRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, start_date: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="End Date"
                    type="date"
                    value={row.end_date}
                    onChange={(v) =>
                      setExperienceRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, end_date: v } : r,
                        ),
                      )
                    }
                  />
                  <Input
                    label="Years of Experience"
                    value={row.year_of_experience}
                    onChange={(v) =>
                      setExperienceRows((prev) =>
                        prev.map((r, i) =>
                          i === idx ? { ...r, year_of_experience: v } : r,
                        ),
                      )
                    }
                  />
                  <div className="md:col-span-2 flex justify-end">
                    <Button
                      variant="danger"
                      onClick={() =>
                        setExperienceRows((prev) =>
                          prev.filter((_, i) => i !== idx),
                        )
                      }
                    >
                      Remove Row
                    </Button>
                  </div>
                </div>
              );
              })}
              <Button
                variant="secondary"
                onClick={() =>
                  setExperienceRows((prev) => [
                    ...prev,
                    {
                      company_name: "",
                      job_title: "",
                      start_date: "",
                      end_date: "",
                      year_of_experience: "",
                    },
                  ])
                }
              >
                Add Experience Row
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onBack}>
            Cancel
          </Button>
          <Button onClick={handleSaveOnly} disabled={isSaving}>
            {isSaving ? "Adding..." : "Add Candidate"}
          </Button>
        </div>
      </Card>

      {showSkillsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-2xl mx-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Manage Skills</h2>
              <button
                onClick={() => setShowSkillsModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 mb-6">
              {selectedSkills.length > 0 ? (
                selectedSkills.map((skill, idx) => (
                  <div key={idx} className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-semibold text-gray-900">{skill.name}</div>
                        {skill.yearsOfExperience && (
                          <div className="text-sm text-gray-600">Experience: {skill.yearsOfExperience} years</div>
                        )}
                        {skill.lastUsedDate && (
                          <div className="text-sm text-gray-600">Last used: {skill.lastUsedDate}</div>
                        )}
                        {skill.isPrimary && (
                          <div className="text-xs font-semibold text-blue-600 mt-1">Primary Skill</div>
                        )}
                      </div>
                      <button
                        onClick={() => setSelectedSkills(prev => prev.filter((_, i) => i !== idx))}
                        className="text-red-600 hover:text-red-700 text-sm font-semibold"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-gray-500 text-center py-4">No skills added yet</p>
              )}
            </div>

            <div className="border-t pt-4 space-y-3">
              <Input
                label="Skill Name"
                placeholder="e.g., Java, React, Project Management"
                id="skill-name-modal"
              />
              <Input
                label="Years of Experience"
                type="number"
                placeholder="e.g., 5"
                id="years-exp-modal"
              />
              <Input
                label="Last Used Date"
                type="date"
                id="last-used-modal"
              />
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is-primary-skill"
                  className="w-4 h-4"
                />
                <label htmlFor="is-primary-skill" className="text-sm font-medium">
                  Mark as Primary Skill
                </label>
              </div>
              <Button
                onClick={() => {
                  const nameInput = document.getElementById('skill-name-modal');
                  const yearsInput = document.getElementById('years-exp-modal');
                  const dateInput = document.getElementById('last-used-modal');
                  const primaryInput = document.getElementById('is-primary-skill');

                  if (nameInput.value.trim()) {
                    const newSkill = {
                      name: nameInput.value.trim(),
                      yearsOfExperience: yearsInput.value ? parseInt(yearsInput.value) : null,
                      lastUsedDate: dateInput.value || null,
                      isPrimary: primaryInput.checked,
                    };

                    setSelectedSkills(prev => {
                      if (primaryInput.checked) {
                        return [...prev.map(s => ({ ...s, isPrimary: false })), newSkill];
                      }
                      return [...prev, newSkill];
                    });

                    nameInput.value = '';
                    yearsInput.value = '';
                    dateInput.value = '';
                    primaryInput.checked = false;
                  }
                }}
                className="w-full"
              >
                Add Skill
              </Button>
            </div>

            <div className="mt-6 flex items-center justify-end gap-2 border-t pt-4">
              <Button variant="secondary" onClick={() => setShowSkillsModal(false)}>
                Done
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
