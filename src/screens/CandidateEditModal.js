import { useEffect, useMemo, useState } from "react";
import { CloudCog, FileText } from "lucide-react";
import { Button, Card, Input, Select } from "../components/ui";
import { uploadResume } from "../services/api/documents";
import { updateCandidateStatus } from "../services/api/candidateStatus";
import {
  extractResumeText,
  inferFieldsFromResumeText,
} from "../utils/resumeAutofill";
import { assignJob, getAllJobs } from "../services/api/jobs";
import { mapJobFromApi } from "../App";

function splitFullName(full) {
  const parts = String(full || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return { firstName: "", middleName: "", lastName: "" };
  if (parts.length === 1)
    return { firstName: parts[0], middleName: "", lastName: "" };
  if (parts.length === 2)
    return { firstName: parts[0], middleName: "", lastName: parts[1] };
  return {
    firstName: parts[0],
    middleName: parts.slice(1, -1).join(" "),
    lastName: parts[parts.length - 1],
  };
}

const PIPELINE_OPTIONS = [
  "Applied",
  "Screening",
  "Interview",
  "Pre-Boarding",
  "Onboarded",
  "Hired",
  "Rejected",
];

export default function CandidateEditModal({
  candidate,
  onClose,
  onUpdateCandidate,
  onRefreshCandidates,
}) {
  const initialName = useMemo(
    () => splitFullName(candidate?.name || ""),
    [candidate],
  );
  const candidateId = candidate?.id;
  const [candidateRole,setCandidateRole] = useState("");
  const [candidateJobTitle, setCandidateJobTitle] = useState(
    candidate?.jobTitle || "",
  );
  const [firstName, setFirstName] = useState(initialName.firstName);
  const [middleName, setMiddleName] = useState(initialName.middleName);
  const [lastName, setLastName] = useState(initialName.lastName);
  const [email, setEmail] = useState(candidate?.email || "");
  const [mobile, setMobile] = useState(candidate?.phone || "");
  const [gender, setGender] = useState(candidate?.gender || "");
  const [dob, setDob] = useState(candidate?.dob || "");
  const [source, setSource] = useState(candidate?.source || "");
  const [experience, setExperience] = useState(candidate?.experience || "");
  const [skills, setSkills] = useState(
    Array.isArray(candidate?.skills) ? candidate.skills.join(", ") : "",
  );
  const [joiningDate, setJoiningDate] = useState(candidate?.joiningDate || "");
  const [expectedSalary, setExpectedSalary] = useState(
    candidate?.expectedSalary || "",
  );
  const [currentSalary, setCurrentSalary] = useState(
    candidate?.currentSalary || "",
  );
  const [currentLocation, setCurrentLocation] = useState(
    candidate?.currentLocation || "",
  );
  const [assignedHrManagerId, setAssignedHrManagerId] = useState(
    candidate?.assignedHrManagerId || "",
  );
  const [assignedReportManagerId, setAssignedReportManagerId] = useState(
    candidate?.assignedReportManagerId || "",
  );

  const [resumeFile, setResumeFile] = useState(null);
  const [resumeParsing, setResumeParsing] = useState(false);
  const [sendLoginEmail, setSendLoginEmail] = useState(false);
  const [actionNotice, setActionNotice] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [accountStatusEdit, setAccountStatusEdit] = useState("Active");
  const [pipelineStatusEdit, setPipelineStatusEdit] = useState("Applied");
  const [statusSaving, setStatusSaving] = useState(false);
  const [users, setUsers] = useState([]);
  const [employeeType, setEmployeeType] = useState("");

  useEffect(() => {
    const nameParts = splitFullName(candidate?.name || "");
    setFirstName(nameParts.firstName);
    setMiddleName(nameParts.middleName);
    setLastName(nameParts.lastName);
    setEmail(candidate?.email || "");
    setCandidateJobTitle(candidate?.jobTitle || "");
    setMobile(candidate?.phone || "");
    setGender(candidate?.gender || "");
    setDob(candidate?.dob || "");
    setSource(candidate?.source || "");
    setExperience(candidate?.experience || "");
    setSkills(
      Array.isArray(candidate?.skills) ? candidate.skills.join(", ") : "",
    );
    setJoiningDate(candidate?.joiningDate || "");
    setExpectedSalary(candidate?.expectedSalary || "");
    setCurrentSalary(candidate?.currentSalary || "");
    setCurrentLocation(candidate?.currentLocation || "");
    setAssignedHrManagerId(candidate?.assignedHrManagerId || "");
    setAssignedReportManagerId(candidate?.assignedReportManagerId || "");
    setResumeFile(null);
    setResumeParsing(false);
    setActionNotice("");
    setAccountStatusEdit(candidate?.status || "Active");

    setPipelineStatusEdit(
      candidate?.pipelineStatus || candidate?.pipeline_status || "Applied",
    );
  }, [candidateId, candidate?.status, candidate?.pipelineStatus]);

  const handleResumeFileChange = async (event) => {
    const file = event.target.files?.[0] || null;
    setResumeFile(file);
    if (!file) return;
    setResumeParsing(true);
    setActionNotice("");
    try {
      const text = await extractResumeText(file);
      const fields = inferFieldsFromResumeText(text);
      if (fields.email) setEmail(fields.email);
      if (fields.firstName) setFirstName(fields.firstName);
      if (fields.middleName) setMiddleName(fields.middleName);
      if (fields.lastName) setLastName(fields.lastName);
      if (fields.mobile) setMobile(fields.mobile);
      if (fields.skills) setSkills(fields.skills);
      if (fields.experience) setExperience(fields.experience);
      // Best-effort only; resume parser does not infer gender reliably.
      // If we can infer location, map it to current location.
      if (fields.currentLocation) setCurrentLocation(fields.currentLocation);

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

  const handleSave = async () => {
    if (!firstName.trim()) {
      setActionNotice("First Name is required.");
      return;
    }
    if (!lastName.trim()) {
      setActionNotice("Last Name is required.");
      return;
    }
    if (!mobile.trim()) {
      setActionNotice("Mobile is required.");
      return;
    }
    if (!candidateId) {
      setActionNotice("Candidate id missing.");
      return;
    }

    setActionNotice("");
    setIsSaving(true);
    try {
      await onUpdateCandidate(candidateId, {
        candidate_job_title: candidateJobTitle.trim() || null,
        candidate_first_name: firstName.trim() || null,
        candidate_middle_name: middleName.trim() || null,
        candidate_last_name: lastName.trim() || null,
        candidate_employee_type: employeeType || null,
        candidate_mobile: mobile.trim() || null,
        candidate_gender: gender.trim() || null,
        candidate_date_of_birth: dob || null,
        candidate_source: source || null,
        candidate_experience: experience || null,
        candidate_skills: skills
          ? skills
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : null,
        candidate_joining_date: joiningDate || null,
        candidate_expected_salary: expectedSalary || null,
        candidate_current_salary: currentSalary || null,
        candidate_current_location: currentLocation || null,
        assigned_hr_manager_id: assignedHrManagerId.trim() || null,
        assigned_report_manager_id: assignedReportManagerId.trim() || null,
      });

      if (resumeFile) {
        await uploadResume({ candidateId, file: resumeFile });
      }

      if (selectedJobId) {
        setIsAssigning(true);
        const result = await assignJob(selectedJobId, candidateId);
        if (result?.status === 200) {
          toast.success("Candidate saved & job assigned ✅");
        } else {
          toast.error("Candidate saved but job assignment failed.");
        }
      }
      onClose?.();
    } catch (err) {
      setActionNotice(err.message || "Failed to update candidate.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveStatus = async () => {
    if (!candidateId) return;
    setActionNotice("");
    setStatusSaving(true);
    try {
      await updateCandidateStatus(candidateId, {
        status: accountStatusEdit,
        pipeline_status: pipelineStatusEdit,
      });
      await onRefreshCandidates?.();
      setActionNotice("Account status and pipeline updated.");
    } catch (err) {
      setActionNotice(err.message || "Failed to update status.");
    } finally {
      setStatusSaving(false);
    }
  };

  if (!candidate) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-4xl">
        <Card
          title="Edit Candidate"
          icon={<FileText className="h-4 w-4" />}
          right={
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          }
        >
          <div className="mb-4 grid gap-3 md:grid-cols-2">
            <Select
              label="Role"
              value={candidateRole}
              onChange={setCandidateRole}
              options={[
                {
                  label: "Please select your option",
                  value: "",
                  disabled: true,
                },
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
            <Input
              label="Email (read-only)"
              value={email}
              onChange={() => {}}
              disabled
            />
            <Input
              label="First Name *"
              value={firstName}
              onChange={setFirstName}
            />
            <Input
              label="Middle Name"
              value={middleName}
              onChange={setMiddleName}
            />
            <Input
              label="Last Name *"
              value={lastName}
              onChange={setLastName}
            />
            <Input label="Mobile *" value={mobile} onChange={setMobile} />
            <Select
              label="Gender"
              value={gender}
              onChange={setGender}
              options={["", "Female", "Male", "Other"]}
            />
            <Input
              label="Date of Birth"
              value={dob}
              onChange={setDob}
              type="date"
            />
            <Input label="Source" value={source} onChange={setSource} />
            <Input
              label="Experience"
              value={experience}
              onChange={setExperience}
            />
            <Input
              label="Skills (comma separated)"
              value={skills}
              onChange={setSkills}
            />
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
            <label className="block md:col-span-2">
              <div className="mb-1 text-xs font-semibold text-gray-700">
                Resume attachment (optional)
              </div>
              <input
                type="file"
                accept=".pdf,.doc,.docx"
                disabled={resumeParsing}
                onChange={handleResumeFileChange}
                className="w-full rounded-xl border bg-white px-3 py-2 text-sm"
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
            </label>
          </div>
          <div className="mt-4 flex items-center justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save"}
            </Button>
          </div>

          {actionNotice ? (
            <div className="mt-2 text-xs text-gray-500">{actionNotice}</div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
