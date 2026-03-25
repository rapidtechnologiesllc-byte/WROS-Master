// HR create-candidate screen with optional resume upload and email.
import { useState } from "react";
import { FileText, Users } from "lucide-react";
import { createCandidate, createCandidateAssignment } from "../services/api/candidates";
import { uploadResume } from "../services/api/documents";
import { getMicrosoftSigninUrl, sendGraphMail } from "../services/api/msgraph";
import { Button, Card, Input, Select } from "../components/ui";
import { extractResumeText, inferFieldsFromResumeText } from "../utils/resumeAutofill";

export default function CandidateCreate({ onBack, onSave }) {
  // These fields map 1:1 to CandidateCreateRequest on the backend.
  const [candidateRole, setCandidateRole] = useState("Candidate");
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
      if (fields.currentLocation) setCurrentLocation(fields.currentLocation);
      const filled = Object.keys(fields).filter((k) => fields[k]).length;
      setActionNotice(
        filled
          ? `Resume parsed: filled ${filled} field(s). Review and correct before saving.`
          : "Resume attached. Could not infer details — fill the form manually."
      );
    } catch (err) {
      setActionNotice(err.message || "Could not read resume for auto-fill.");
    } finally {
      setResumeParsing(false);
    }
  };

  const handleCreateCandidate = async () => {
    if (!firstName.trim()) {
      setActionNotice("First Name is required.");
      return;
    }
    if (!lastName.trim()) {
      setActionNotice("Last Name is required.");
      return;
    }
    if (!gender.trim()) {
      setActionNotice("Gender is required.");
      return;
    }
    if (!mobile.trim()) {
      setActionNotice("Mobile is required.");
      return;
    }
    if (!email.trim()) {
      setActionNotice("Email is required.");
      return;
    }
    setActionNotice("");
    setIsSaving(true);
    try {
      // Create the candidate in backend and receive generated password.
      const data = await createCandidate({
        candidate_email: email.trim(),
        candidate_role: candidateRole || "Candidate",
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
        assigned_report_manager_id: assignedReportManagerId || null
      });
      const candidateName = [firstName, middleName, lastName]
        .filter(Boolean)
        .join(" ")
        .trim();
      const createdCandidateId = data?.candidate_id;
      if (
        createdCandidateId &&
        (assignedHrManagerId.trim() || assignedReportManagerId.trim())
      ) {
        try {
          // Optional: assign HR/reporting managers after candidate creation.
          await createCandidateAssignment({
            candidateId: createdCandidateId,
            hiringManagerId: assignedHrManagerId.trim() || null,
            reportingManagerId: assignedReportManagerId.trim() || null
          });
        } catch (assignmentErr) {
          setActionNotice(
            assignmentErr.message || "Candidate created, but assignment failed."
          );
        }
      }
      onSave({
        id: createdCandidateId,
        name: candidateName || "New Candidate",
        email,
        phone: mobile,
        skills: skills
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        status: "New"
      });
      let nextNotice = `Candidate created. Password: ${data?.candidate_password || "N/A"}`;
      if (sendLoginEmail && data?.candidate_password) {
        try {
          // Uses Microsoft Graph to email credentials to the candidate.
          await sendGraphMail({
            to: email.trim(),
            subject: "Your HRMS Candidate Login",
            bodyText: `Hello ${candidateName || "Candidate"},\n\nYour HRMS account is ready.\n\nLogin email: ${email.trim()}\nTemporary password: ${data.candidate_password}\n\nPlease sign in and change your password.\n\nThanks`
          });
          nextNotice = `${nextNotice}. Login email sent.`;
        } catch (mailErr) {
          nextNotice = `${nextNotice}. Email failed: ${
            mailErr.message || "Connect Microsoft and try again."
          }`;
        }
      }
      if (resumeFile) {
        if (!createdCandidateId) {
          nextNotice = `${nextNotice}. Resume skipped (missing candidate id).`;
        } else {
          try {
            // HR/Admin resume upload (candidate_id is required by backend).
            await uploadResume({ candidateId: createdCandidateId, file: resumeFile });
            nextNotice = `${nextNotice}. Resume uploaded.`;
          } catch (uploadErr) {
            nextNotice = `${nextNotice}. Resume upload failed: ${
              uploadErr.message || "Unknown error"
            }`;
          }
        }
      }
      setActionNotice(nextNotice);
    } catch (err) {
      setActionNotice(err.message || "Failed to create candidate.");
    } finally {
      setIsSaving(false);
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
            Upload first — we read PDF or DOCX and suggest name, email, phone, skills, experience, and
            location when we can detect them.
          </p>
          <input
            type="file"
            accept=".pdf,.doc,.docx"
            disabled={resumeParsing}
            onChange={handleResumeFileChange}
            className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-blue-600 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-blue-700"
          />
          {resumeParsing ? (
            <div className="mt-2 text-xs font-medium text-blue-700">Reading resume…</div>
          ) : resumeFile ? (
            <div className="mt-2 text-xs text-gray-600">Selected: {resumeFile.name}</div>
          ) : null}
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <Select
            label="Role"
            value={candidateRole}
            onChange={setCandidateRole}
            options={["Candidate", "Employee", "Contractor"]}
          />
          <Input label="Email *" value={email} onChange={setEmail} />
          <Input label="First Name *" value={firstName} onChange={setFirstName} />
          <Input label="Middle Name" value={middleName} onChange={setMiddleName} />
          <Input label="Last Name *" value={lastName} onChange={setLastName} />
          <Input label="Mobile *" value={mobile} onChange={setMobile} />
          <Select
            label="Gender *"
            value={gender}
            onChange={setGender}
            options={["", "Female", "Male", "Other"]}
          />
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
          <label className="flex items-center gap-2 text-sm md:col-span-2">
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
          <Button onClick={handleCreateCandidate} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
        {actionNotice ? (
          <div className="mt-2 text-xs text-gray-500">{actionNotice}</div>
        ) : null}
      </Card>
    </div>
  );
}
