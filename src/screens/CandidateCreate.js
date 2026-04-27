// HR create-candidate screen with optional resume upload and email.
import { useEffect, useState } from "react";
import { FileText, Users } from "lucide-react";
import { createCandidate } from "../services/api/candidates";
import { uploadResume } from "../services/api/documents";
import { getMicrosoftSigninUrl, sendGraphMail } from "../services/api/msgraph";
import { Button, Card, Input, Select } from "../components/ui";
import {
  extractResumeText,
  inferFieldsFromResumeText,
} from "../utils/resumeAutofill";
import { assignJob, getAllJobs } from "../services/api/jobs";
import { mapJobFromApi } from "../App";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

export default function CandidateCreate({ onBack, onSave }) {
  // These fields map 1:1 to CandidateCreateRequest on the backend.
  const [candidateRole, setCandidateRole] = useState("Candidate");
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
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [isAssigning, setIsAssigning] = useState(false);
  const [jobName, setJobName] = useState("");

  const jobOptions = [
    { label: "Please select job", value: "", disabled: true },
    ...(jobs?.map((job) => ({
      label: job?.title,
      value: job?.id,
    })) || []),
  ];

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        const refreshed = await getAllJobs();
        if (!isMounted) return;
        const mappedJobs = (refreshed?.jobs || []).map((j) =>
          mapJobFromApi(j, users),
        );
        setJobs(mappedJobs);
      } catch (err) {
        console.error(err);
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, []);

  const clearFieldError = (field) => {
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const inferEducationRows = (text) => {
    const normalized = String(text || "").replace(/\r/g, "\n");
    const lines = normalized
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const eduStart = lines.findIndex((l) =>
      /^(education|academic|academics)\b/i.test(l),
    );
    if (eduStart === -1) return [];
    const windowLines = lines.slice(eduStart + 1, eduStart + 20);
    const joined = windowLines.join(" ");
    const degreeMatch = joined.match(
      /(b\.?\s?tech|m\.?\s?tech|b\.?\s?e|m\.?\s?e|bca|mca|bsc|msc|mba|phd|diploma|bachelor|master)/i,
    );
    const years = joined.match(/\b(19|20)\d{2}\b/g) || [];
    const instituteLine = windowLines.find((l) =>
      /(university|college|institute|school)/i.test(l),
    );
    if (!degreeMatch && !instituteLine) return [];
    const startYear = years[0] || "";
    const endYear = years.length > 1 ? years[1] : "";
    return [
      {
        education_institute: instituteLine || "",
        degree: degreeMatch
          ? degreeMatch[0].toUpperCase().replace(/\s+/g, " ").trim()
          : "",
        field_of_study: "",
        starting_year: startYear,
        year_of_passing: endYear,
        percentage: "",
      },
    ];
  };

  const inferExperienceRows = (text, nameLine = "", jobTitle = "") => {
    const normalized = String(text || "").replace(/\r/g, "\n");
    const lines = normalized
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const cleanName = (nameLine || "").toLowerCase().replace(/\s+/g, "");
    const cleanJob = (jobTitle || "").toLowerCase();
    const expStart = lines.findIndex((l) =>
      /^(experience|work experience|employment)\b/i.test(l),
    );
    if (expStart === -1) return [];
    const windowLines = lines.slice(expStart + 1, expStart + 25);
    const joined = windowLines.join(" ");
    const years = joined.match(/\b(19|20)\d{2}\b/g) || [];

    let titleLine = "";
    let companyLine = "";
    for (let rawLine of windowLines) {
      if (!rawLine) continue;
      const line = rawLine.split(/[\|\-–]/)[0].trim();
      const lower = line.toLowerCase();
      const normalizedLine = lower.replace(/\s+/g, "");
      if (cleanName && normalizedLine.includes(cleanName)) continue;
      if (cleanJob && lower.includes(cleanJob)) continue;
      if (/email|phone|mobile|linkedin|github|address/i.test(lower)) continue;
      if (line.length < 3 || line.length > 80) continue;
      if (!/[a-zA-Z]/.test(line)) continue;
      if (
        !titleLine &&
        /(engineer|developer|analyst|consultant|manager|intern|designer|lead|architect)/i.test(
          line,
        )
      ) {
        titleLine = line;
        continue;
      }
      if (
        !companyLine &&
        /(pvt|llp|ltd|inc|corp|technologies|solutions|systems|labs|company|services)/i.test(
          line,
        )
      ) {
        companyLine = line;
        continue;
      }
    }

    if (!titleLine && !companyLine) return [];
    const startYear = years[0] || "";
    const endYear = years.length > 1 ? years[1] : "";
    return [
      {
        company_name: companyLine || "",
        job_title: titleLine || "",
        start_date: startYear ? `${startYear}-01-01` : "",
        end_date: endYear ? `${endYear}-12-31` : "",
        year_of_experience: "",
      },
    ];
  };

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
      // Best-effort defaults for structured sections from resume text.
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
      setActionNotice("Please fill all required fields.");
      return;
    }
    if (!selectedJobId.trim()) {
      setActionNotice("Job ID is required.");
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
      return {
        id: createdCandidateId,
        name: candidateName || "New Candidate",
        email,
        phone: mobile,
        jobTitle: candidateJobTitle || "",
        skills: skills
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        status: "New",
      };
      let nextNotice = `Candidate created. Password: ${data?.candidate_password || "N/A"}`;

      if (sendLoginEmail && data?.candidate_password) {
        //NEED THIS CODE FOR IMPLEMENTING EMAIL FUNCTIONALITY.
        //COMMENTED THIS AS THE CURRENT API IS INCORRECT
        // try {
        //   // Uses Microsoft Graph to email credentials to the candidate.
        //   await sendGraphMail({
        //     to: email.trim(),
        //     subject: "Your HRMS Candidate Login",
        //     bodyText: `Hello ${candidateName || "Candidate"},\n\nYour HRMS account is ready.\n\nLogin email: ${email.trim()}\nTemporary password: ${data.candidate_password}\n\nPlease sign in and change your password.\n\nThanks`
        //   });
        //   nextNotice = `${nextNotice}. Login email sent.`;
        // } catch (mailErr) {
        //   nextNotice = `${nextNotice}. Email failed: ${
        //     mailErr.message || "Connect Microsoft and try again."
        //   }`;
        // }
      }

      if (resumeFile) {
        if (!createdCandidateId) {
          nextNotice = `${nextNotice}. Resume skipped (missing candidate id).`;
        } else {
          try {
            // HR/Admin resume upload (candidate_id is required by backend).
            await uploadResume({
              candidateId: createdCandidateId,
              file: resumeFile,
            });
            nextNotice = `${nextNotice}. Resume uploaded.`;
          } catch (uploadErr) {
            nextNotice = `${nextNotice}. Resume upload failed: ${uploadErr.message || "Unknown error"
              }`;
          }
        }
      }

      setActionNotice(nextNotice);
      return createdCandidateId;
    } catch (err) {
      setActionNotice(err.message || "Failed to create candidate.");
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
    const candidate = await handleCreateCandidate();
    if (candidate) {
      onSave(candidate);
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Create Candidate"
        icon={<Users className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={onBack}>
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
            options={["Candidate", "Employee", "Contractor"]}
          />
          <Input
            label="Job Title"
            value={jobName}
            onChange={setJobName}
            actionNotice={actionNotice}
          />
          <Select
            label="Select Job *"
            value={selectedJobId}
            onChange={(value) => setSelectedJobId(value)}
            options={jobOptions}
          />
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
            {errors.email ? <div className="mt-1 text-xs text-red-500">{errors.email}</div> : null}
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
            {errors.firstName ? <div className="mt-1 text-xs text-red-500">{errors.firstName}</div> : null}
          </div>

          <Input label="Middle Name" value={middleName} onChange={setMiddleName} />

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
            {errors.lastName ? <div className="mt-1 text-xs text-red-500">{errors.lastName}</div> : null}
          </div>

          <div>
            <Input
              label="Mobile *"
              value={mobile}
              onChange={(value) => {
                setMobile(value);
                clearFieldError("mobile");
              }}
              actionNotice={actionNotice}
              error={errors.mobile}
            />
            {errors.mobile ? <div className="mt-1 text-xs text-red-500">{errors.mobile}</div> : null}
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
            {errors.gender ? <div className="mt-1 text-xs text-red-500">{errors.gender}</div> : null}
          </div>

          <Input label="Date of Birth" value={dob} onChange={setDob} type="date" />
          <Input label="Source" value={source} onChange={setSource} />
          <Input label="Experience" value={experience} onChange={setExperience} />
          <Input label="Skills (comma separated)" value={skills} onChange={setSkills} />

          <Input
            label="Joining Date"
            value={joiningDate}
            onChange={setJoiningDate}
            type="date"
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
            label="Assigned HR Manager ID"
            value={assignedHrManagerId}
            onChange={setAssignedHrManagerId}
          />

          <Input
            label="Assigned Reporting Manager ID"
            value={assignedReportManagerId}
            onChange={setAssignedReportManagerId}
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

        <div className="mt-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sendLoginEmail}
              onChange={(event) => setSendLoginEmail(event.target.checked)}
            />
            Send login email to candidate (requires Microsoft connection).
            <button
              type="button"
              className="ml-2 text-xs font-semibold text-blue-600 hover:text-blue-700"
              onClick={() => window.open(getMicrosoftSigninUrl(), "_blank")}
            >
              Connect Microsoft
            </button>
          </label>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onBack}>
            Cancel
          </Button>
          <Button onClick={handleSaveOnly} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
          <Button onClick={handleSaveAndAssignJob} disabled={isAssigning}>
            {isAssigning ? "Assigning..." : "Save and Submit Job"}
          </Button>
        </div>

        {actionNotice ? (
          <div className="mt-2 text-xs text-gray-500">{actionNotice}</div>
        ) : null}
      </Card>
    </div>
  );
}