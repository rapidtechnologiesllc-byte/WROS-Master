import { useEffect, useMemo, useRef, useState } from "react";
import { FileText } from "lucide-react";
import { Button, Card, Input, Select } from "../components/ui";
import { uploadResume } from "../services/api/documents";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import {
  extractResumeText,
  inferFieldsFromResumeText,
} from "../utils/resumeAutofill";

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

export default function CandidateEditModal({
  candidate,
  onClose,
  onUpdateCandidate,
}) {
  const initialName = useMemo(
    () => splitFullName(candidate?.candidate_name || ""),
    [candidate],
  );
  const candidateId = candidate?.id;
  // Permission Gate: Only users with candidates.edit can edit candidates.
  // Evaluated before any early return so hook order stays stable.
  const canEditCandidates = hasPermission('candidates', 'edit');
  // Latest candidate snapshot, read by the reset effect below. The form is only
  // re-seeded when a different candidate is opened (candidateId changes), so a
  // background refresh of the candidate list does not wipe in-progress edits.
  const candidateRef = useRef(candidate);
  candidateRef.current = candidate;
  const [candidateJobTitle, setCandidateJobTitle] = useState(
    candidate?.candidate_job_title || "",
  );
  const [firstName, setFirstName] = useState(initialName.firstName);
  const [middleName, setMiddleName] = useState(initialName.middleName);
  const [lastName, setLastName] = useState(initialName.lastName);
  const [email, setEmail] = useState(candidate?.candidate_email || "");
  const [mobile, setMobile] = useState(candidate?.candidate_mobile || "");
  const [gender, setGender] = useState(candidate?.candidate_gender || "");
  const [dob, setDob] = useState(candidate?.candidate_date_of_birth || "");
  const [source, setSource] = useState(candidate?.candidate_source || "");
  const [experience, setExperience] = useState(candidate?.candidate_experience || "");
  const [skills, setSkills] = useState("");
  const [joiningDate, setJoiningDate] = useState(candidate?.candidate_joining_date || "");
  const [expectedSalary, setExpectedSalary] = useState(
    candidate?.candidate_expected_salary || "",
  );
  const [currentSalary, setCurrentSalary] = useState(
    candidate?.candidate_current_salary || "",
  );
  const [currentLocation, setCurrentLocation] = useState(
    candidate?.candidate_current_location || "",
  );
  const [assignedHrManagerId, setAssignedHrManagerId] = useState(
    candidate?.assignedHrManagerId || "",
  );
  const [assignedReportManagerId, setAssignedReportManagerId] = useState(
    candidate?.assignedReportManagerId || "",
  );

  const [resumeFile, setResumeFile] = useState(null);
  const [resumeParsing, setResumeParsing] = useState(false);
  const [actionNotice, setActionNotice] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [employeeType, setEmployeeType] = useState("");

  useEffect(() => {
    const candidate = candidateRef.current;
    const nameParts = splitFullName(candidate?.candidate_name || "");
    setFirstName(nameParts.firstName);
    setMiddleName(nameParts.middleName);
    setLastName(nameParts.lastName);
    setEmail(candidate?.candidate_email || "");
    setCandidateJobTitle(candidate?.candidate_job_title || "");
    setMobile(candidate?.candidate_mobile || "");
    setGender(candidate?.candidate_gender || "");
    setDob(candidate?.candidate_date_of_birth || "");
    setSource(candidate?.candidate_source || "");
    setExperience(candidate?.candidate_experience || "");
    setSkills(
      Array.isArray(candidate?.candidate_skills)
        ? candidate.candidate_skills.join(", ")
        : candidate?.candidate_skills || "",
    );
    setJoiningDate(candidate?.candidate_joining_date || "");
    setExpectedSalary(candidate?.candidate_expected_salary || "");
    setCurrentSalary(candidate?.candidate_current_salary || "");
    setCurrentLocation(candidate?.candidate_current_location || "");
    setAssignedHrManagerId(candidate?.assigned_hr_manager_id || "");
    setAssignedReportManagerId(candidate?.assigned_report_manager_id || "");
    setResumeFile(null);
    setResumeParsing(false);
    setActionNotice("");
  }, [candidateId]);

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
      console.error("[CandidateEditModal] Failed to parse resume:", err);
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
        candidate_skills: skills.trim() || null,
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
      onClose?.();
    } catch (err) {
      console.error("[CandidateEditModal] Failed to update candidate:", err);
      setActionNotice(err.message || "Failed to update candidate.");
    } finally {
      setIsSaving(false);
    }
  };

  if (!canEditCandidates) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg p-6 max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">You do not have permission to edit candidates.</p>
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

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
              label="Employee Type"
              value={employeeType}
              onChange={setEmployeeType}
              options={[
                {
                  label: "Please select your option",
                  value: "",
                  disabled: true,
                },
                { label: "Full time employee", value: "Full Time Employee" },
                { label: "Intern", value: "Intern" },
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
