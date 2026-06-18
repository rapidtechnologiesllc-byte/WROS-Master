// HR create-candidate screen with optional resume upload and email.
import { useEffect, useState } from "react";
import { FileText, Users } from "lucide-react";
import { createCandidate } from "../services/api/candidates";
import { uploadResume } from "../services/api/documents";
import { getMicrosoftSigninUrl } from "../services/api/msgraph";
import { sendPlainEmail } from "../services/api/email";
import { Button, Card, Input, Select } from "../components/ui";
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
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { useNavigate } from "react-router-dom";

export default function CandidateCreate({ onBack, onSave }) {
  const [candidateRole, setCandidateRole] = useState("");
  const [candidateJobTitle, setCandidateJobTitle] = useState("");
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [gender, setGender] = useState("");
  const [dob, setDob] = useState("");
  const [source, setSource] = useState("");
  const [experience, setExperience] = useState("");
  const [skills, setSkills] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [expectedSalary, setExpectedSalary] = useState("");
  const [currentSalary, setCurrentSalary] = useState("");
  const [currentLocation, setCurrentLocation] = useState("");
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
  const [employeeType, setEmployeeType] = useState("");
  const navigate = useNavigate();

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
      if (fields.currentLocation) setCurrentLocation(fields.currentLocation);
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
    if (!email.trim()) newErrors.email = "Email is required.";
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      toast.error(Object.values(newErrors)[0]);
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
      const data = await createCandidate({
        candidate_email: email.trim(),
        candidate_role: candidateRole || "Candidate",
        candidate_job_title: candidateJobTitle || null,
        candidate_employee_type: employeeType || null,
        candidate_first_name: firstName || null,
        candidate_middle_name: middleName || null,
        candidate_last_name: lastName || null,
        candidate_mobile: mobile || null,
        candidate_gender: gender || null,
        candidate_date_of_birth: dob || null,
        candidate_source: source || null,
        candidate_experience: experience || null,
        candidate_skills: skills || null,
        candidate_joining_date: joiningDate || null,
        candidate_expected_salary: expectedSalary || null,
        candidate_current_salary: currentSalary || null,
        candidate_current_location: currentLocation || null,
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
        phone: mobile,
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
          } catch (uploadErr) {
            console.error("Resume upload failed:", uploadErr);

            nextNotice = `${nextNotice} Resume upload failed: ${
              uploadErr?.message || "Unknown error"
            }.`;
          }
        }
      }
      setActionNotice(nextNotice);
      return createdCandidate;
    } catch (err) {
      toast.error(err.message || "Failed to create candidate.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAndAssignJob = async () => {
    setIsAssigning(true);

    try {
      const candidateId = await handleCreateCandidate();
      if (!candidateId?.id) {
        toast.error("Candidate creation failed");
        return;
      }
      const result = await assignJob(selectedJobId, candidateId?.id, {
        application_status: "Applied",
      });
      if (result?.status === 201) {
        toast.success("Job assigned successfully ✅");
        onSave(candidateId);
      }
    } catch (err) {
      toast.error(
        err.message || "Candidate created but job assignment failed.",
      );
    } finally {
      setIsAssigning(false);
    }
  };

  const handleSaveOnly = async () => {
    try {
      const candidate = await handleCreateCandidate();

      if (!candidate?.id) {
        return;
      }

      await createCandidateHistoryEvent(candidate.id, {
        event_type: HISTORY_EVENT_TYPES.APPLIED,
      });

      onSave(candidate);
    } catch (error) {
      console.error("Failed to create candidate history event:", error);
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Create Candidate"
        icon={<Users className="h-4 w-4" />}
        right={
          <Button
            variant="ghost"
            onClick={() => navigate("/candidates")}
          >
            Back
          </Button>
        }
      >
        <div className="mb-4 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-800">
            <FileText className="h-4 w-4 text-blue-600" />
            Resume attachment
          </div>
          <p className="mb-3 text-xs text-gray-600">
            Upload first — we read PDF or DOCX and suggest name, email, phone,
            skills, experience, and location when we can detect them.
          </p>
          <input
            type="file"
            accept=".pdf,.doc,.docx"
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
          <Select
            label="Role"
            value={candidateRole}
            onChange={setCandidateRole}
            options={[
              { label: "Please select your option", value: "", disabled: true },
              { label: "Candidate", value: "Candidate" },
              { label: "Employee", value: "Employee" },
              { label: "Contractor", value: "Contractor" },
            ]}
          />
          <Select
            label="Employee Type"
            value={employeeType}
            onChange={setEmployeeType}
            options={[
              { label: "Please select your option", value: "", disabled: true },
              { label: "Full time employee", value: "Full Time Employee" },
              { label: "Intern", value: "Intern" },
              { label: "Guidewire Employee", value: "Guidewire" },
            ]}
          />
          <Input label="Job Title" value={jobName} onChange={setJobName} />
          <div>
            <Input
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

          <div>
            <Input
              label="Mobile *"
              value={mobile}
              onChange={(value) => {
                let cleanedValue = value.replace(/\D/g, "");
                if (cleanedValue.startsWith("91") && cleanedValue.length > 10) {
                  cleanedValue = cleanedValue.slice(2);
                }
                cleanedValue = cleanedValue.slice(0, 10);
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
          <Input label="Source" value={source} onChange={setSource} />
          <Input
            label="Skills (comma separated)"
            value={skills}
            onChange={setSkills}
          />
          <Input
            label="Expected Salary"
            value={expectedSalary}
            onChange={setExpectedSalary}
          />

          <Input
            label="Current Salary"
            value={currentSalary}
            onChange={setCurrentSalary}
          />

          <Input
            label="Current Location"
            value={currentLocation}
            onChange={setCurrentLocation}
          />

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
              {educationRows.map((row, idx) => (
                <div
                  key={`edu-${idx}`}
                  className="grid gap-2 rounded-lg border bg-white p-3 md:grid-cols-2"
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
              ))}
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
              {experienceRows.map((row, idx) => (
                <div
                  className="grid gap-2 rounded-lg border bg-white p-3 md:grid-cols-2"
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
              ))}
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

        {actionNotice ? (
          <div className="mt-2 text-xs text-gray-500">{actionNotice}</div>
        ) : null}
      </Card>
    </div>
  );
}
