import { useEffect, useMemo, useState } from "react";
import { Edit2, Save, X, Loader, ChevronDown, ChevronRight, Download, Upload } from "lucide-react";
import { Button, Input, Select, Card } from "../../components/ui";
import RateField from "../../components/ui/RateField";
import { toast } from "react-toastify";
import {
  getCandidateById,
  getCandidateContacts,
  updateCandidate,
} from "../../services/api/candidates";
import { getHrCandidateFullDetails } from "../../services/api/candidateSelfService";
import { getCandidateDocuments, uploadResume } from "../../services/api/documents";
import { getAllUsers } from "../../services/api/users";

const GENDERS = ["Male", "Female", "Other", "Prefer not to say"];
const SOURCES = ["LinkedIn", "Indeed", "Referral", "Direct Application", "Job Board", "Other"];
const CURRENCY_OPTIONS = ["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year"];
const GOVT_ID_TYPES = ["Aadhar Card", "Pan Card", "Driver License", "Election Card", "State ID", "Passport", "Other"];
const EDUCATION_LEVELS = ["High School", "Diploma", "Bachelor", "Master", "PhD", "Postdoctoral", "Other"];

export default function ProfileTabEditable({ candidateId, candidate = {}, onRefresh }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [users, setUsers] = useState([]);
  const [candidateFullDetails, setCandidateFullDetails] = useState(null);

  // Edit mode state
  const [editingSection, setEditingSection] = useState(null);
  const [savingSection, setSavingSection] = useState(null);

  // Form state
  const [editForm, setEditForm] = useState({});

  // Resume state
  const [resumeExpanded, setResumeExpanded] = useState(false);
  const [resumeData, setResumeData] = useState(null);

  // Skills state
  const [showSkillsModal, setShowSkillsModal] = useState(false);
  const [skills, setSkills] = useState([]);
  const [skillForm, setSkillForm] = useState({
    name: "",
    yearsOfExperience: "",
    lastUsedDate: "",
    isPrimary: false,
  });
  const [editingSkillIdx, setEditingSkillIdx] = useState(null);

  // Education state
  const [showEducationModal, setShowEducationModal] = useState(false);
  const [educationList, setEducationList] = useState([]);
  const [educationForm, setEducationForm] = useState({
    level: "",
    school: "",
    university: "",
    start_date: "",
    end_date: "",
    degree: "",
  });
  const [editingEducationIdx, setEditingEducationIdx] = useState(null);

  // Experience state
  const [showExperienceModal, setShowExperienceModal] = useState(false);
  const [experienceList, setExperienceList] = useState([]);
  const [experienceForm, setExperienceForm] = useState({
    company: "",
    job_title: "",
    start_date: "",
    end_date: "",
    job_responsibilities: "",
  });
  const [editingExperienceIdx, setEditingExperienceIdx] = useState(null);

  // Certifications state
  const [showCertificationsModal, setShowCertificationsModal] = useState(false);
  const [certificationsList, setCertificationsList] = useState([]);
  const [certificationsForm, setCertificationsForm] = useState({
    name: "",
    title: "",
    issuer: "",
    organization: "",
    issue_date: "",
    expiry_date: "",
    credential_id: "",
  });
  const [editingCertificationsIdx, setEditingCertificationsIdx] = useState(null);

  // Resume upload state
  const [resumeFile, setResumeFile] = useState(null);
  const [uploadingResume, setUploadingResume] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [candidateData, fullDetails, userList] = await Promise.all([
          getCandidateById(candidateId),
          getHrCandidateFullDetails(candidateId),
          getAllUsers(),
        ]);
        setData(candidateData);
        setCandidateFullDetails(fullDetails);
        setUsers(userList || []);

        // Load resume data
        try {
          const docs = await getCandidateDocuments(candidateId);
          if (docs && docs.resume) {
            setResumeData(docs.resume);
          }
        } catch (docErr) {
          console.warn("Could not load resume:", docErr?.message);
        }
      } catch (err) {
        setError(err?.message || "Failed to load profile");
      } finally {
        setLoading(false);
      }
    };

    if (candidateId) load();
  }, [candidateId]);

  // Initialize education, experience, and certifications from candidateFullDetails
  useEffect(() => {
    if (candidateFullDetails) {
      setEducationList(candidateFullDetails.education || []);
      setExperienceList(candidateFullDetails.experience || []);
      setCertificationsList(candidateFullDetails.certifications || []);
    }
  }, [candidateFullDetails]);

  const profile = useMemo(() => {
    const merged = { ...(candidate || {}), ...(data || {}) };
    return merged && Object.keys(merged).length > 0 ? merged : {};
  }, [candidate, data]);

  const handleEditSection = (section) => {
    try {
      if (!profile || Object.keys(profile).length === 0) {
        toast.error("Profile data not loaded yet. Please wait.");
        return;
      }
      setEditingSection(section);
      setEditForm({
        first_name: profile?.candidate_first_name || "",
        middle_name: profile?.candidate_middle_name || "",
        last_name: profile?.candidate_last_name || "",
        email: profile?.candidate_email || "",
        mobile: profile?.candidate_mobile || "",
        job_title: profile?.candidate_job_title || "",
        gender: profile?.candidate_gender || "",
        dob: profile?.candidate_date_of_birth || "",
        current_location: profile?.candidate_current_location || "",
        experience: profile?.candidate_experience || "",
        joining_date: profile?.candidate_joining_date || "",
        expected_salary: profile?.candidate_expected_salary || "",
        expected_salary_type: profile?.candidate_expected_salary_type || "$/Year",
        current_salary: profile?.candidate_current_salary || "",
        current_salary_type: profile?.candidate_current_salary_type || "$/Year",
        source: profile?.candidate_source || "",
        govt_id_type: profile?.candidate_govt_id_type || "",
        govt_id_number: profile?.candidate_govt_id_number || "",
      });
    } catch (err) {
      console.error("Error loading edit form:", err);
      toast.error("Error loading form data. Please refresh and try again.");
    }
  };

  const handleCancelEdit = () => {
    setEditingSection(null);
    setEditForm({});
  };

  const handleSaveSection = async (section) => {
    setSavingSection(section);
    try {
      const updatePayload = {};

      if (section === "basic") {
        updatePayload.candidate_first_name = editForm.first_name || null;
        updatePayload.candidate_middle_name = editForm.middle_name || null;
        updatePayload.candidate_last_name = editForm.last_name || null;
        updatePayload.candidate_mobile = editForm.mobile || null;
        updatePayload.candidate_job_title = editForm.job_title || null;
        updatePayload.candidate_gender = editForm.gender || null;
        updatePayload.candidate_date_of_birth = editForm.dob || null;
        updatePayload.candidate_current_location = editForm.current_location || null;
      } else if (section === "professional") {
        updatePayload.candidate_experience = editForm.experience || null;
        updatePayload.candidate_source = editForm.source || null;
        updatePayload.candidate_joining_date = editForm.joining_date || null;
        updatePayload.candidate_expected_salary = editForm.expected_salary || null;
        updatePayload.candidate_expected_salary_type = editForm.expected_salary_type || null;
        updatePayload.candidate_current_salary = editForm.current_salary || null;
        updatePayload.candidate_current_salary_type = editForm.current_salary_type || null;
      } else if (section === "identity") {
        updatePayload.candidate_govt_id_type = editForm.govt_id_type || null;
        updatePayload.candidate_govt_id_number = editForm.govt_id_number || null;
      }

      if (onRefresh) {
        await onRefresh(candidateId, updatePayload);
      } else {
        // Fallback: call updateCandidate directly if onRefresh not provided
        await updateCandidate(candidateId, updatePayload);
      }

      // Force complete refresh of ALL candidate data after successful update
      // Small delay ensures server has processed the update
      setTimeout(async () => {
        try {
          const [refreshedData, fullDetails] = await Promise.all([
            getCandidateById(candidateId),
            getHrCandidateFullDetails(candidateId),
          ]);
          if (refreshedData && Object.keys(refreshedData).length > 0) {
            setData(refreshedData);
          }
          if (fullDetails) {
            setCandidateFullDetails(fullDetails);
          }
        } catch (refreshErr) {
          console.warn("Could not refresh complete profile data:", refreshErr?.message);
        }
      }, 300);

      toast.success("Profile updated successfully");
      setEditingSection(null);
      setEditForm({});
    } catch (err) {
      toast.error(err?.message || "Failed to save changes");
    } finally {
      setSavingSection(null);
    }
  };

  if (loading) return <div className="p-6 text-center text-gray-500">Loading profile...</div>;

  const userOptions = Array.isArray(users)
    ? users.map(u => ({ value: u.id, label: `${u.first_name} ${u.last_name}` }))
    : [];

  return (
    <div className="space-y-4">
      {/* Basic Information */}
      <EditableSection
        title="Basic Information"
        isEditing={editingSection === "basic"}
        isSaving={savingSection === "basic"}
        onEdit={() => handleEditSection("basic")}
        onCancel={handleCancelEdit}
        onSave={() => handleSaveSection("basic")}
      >
        {editingSection === "basic" ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Input
              label="First Name"
              value={editForm.first_name || ""}
              onChange={(v) => setEditForm({...editForm, first_name: v})}
            />
            <Input
              label="Middle Name"
              value={editForm.middle_name || ""}
              onChange={(v) => setEditForm({...editForm, middle_name: v})}
            />
            <Input
              label="Last Name"
              value={editForm.last_name || ""}
              onChange={(v) => setEditForm({...editForm, last_name: v})}
            />
            <Input
              label="Email"
              type="email"
              value={editForm.email || ""}
              onChange={(v) => setEditForm({...editForm, email: v})}
              disabled
            />
            <Input
              label="Mobile"
              value={editForm.mobile || ""}
              onChange={(v) => setEditForm({...editForm, mobile: v})}
            />
            <Input
              label="Job Title"
              value={editForm.job_title || ""}
              onChange={(v) => setEditForm({...editForm, job_title: v})}
            />
            <Select
              label="Gender"
              value={editForm.gender || ""}
              onChange={(v) => setEditForm({...editForm, gender: v})}
              options={GENDERS}
            />
            <Input
              label="Date of Birth"
              type="date"
              value={editForm.dob || ""}
              onChange={(v) => setEditForm({...editForm, dob: v})}
            />
            <Input
              label="Current Location"
              value={editForm.current_location || ""}
              onChange={(v) => setEditForm({...editForm, current_location: v})}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <InfoDisplay label="First Name" value={profile?.candidate_first_name} />
            <InfoDisplay label="Middle Name" value={profile?.candidate_middle_name} />
            <InfoDisplay label="Last Name" value={profile?.candidate_last_name} />
            <InfoDisplay label="Email" value={profile?.candidate_email} />
            <InfoDisplay label="Mobile" value={profile?.candidate_mobile} />
            <InfoDisplay label="Job Title" value={profile?.candidate_job_title} />
            <InfoDisplay label="Gender" value={profile?.candidate_gender} />
            <InfoDisplay label="Date of Birth" value={profile?.candidate_date_of_birth} />
            <InfoDisplay label="Current Location" value={profile?.candidate_current_location} />
          </div>
        )}
      </EditableSection>

      {/* Professional Information */}
      <EditableSection
        title="Professional Information"
        isEditing={editingSection === "professional"}
        isSaving={savingSection === "professional"}
        onEdit={() => handleEditSection("professional")}
        onCancel={handleCancelEdit}
        onSave={() => handleSaveSection("professional")}
      >
        {editingSection === "professional" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Experience (Years)"
              type="number"
              min="0"
              max="99"
              value={editForm.experience || ""}
              onChange={(v) => {
                const numVal = v === "" ? "" : String(Math.max(0, Math.min(99, parseInt(v) || 0)));
                setEditForm({...editForm, experience: numVal});
              }}
              placeholder="e.g., 5"
            />
            <Select
              label="Source"
              value={editForm.source || ""}
              onChange={(v) => setEditForm({...editForm, source: v})}
              options={SOURCES}
            />
            <Input
              label="Notice Period (days)"
              placeholder="e.g., 30, 45, 60"
              value={editForm.joining_date || ""}
              onChange={(v) => setEditForm({...editForm, joining_date: v})}
            />
            <div />
            <RateField
              label="Expected Salary"
              value={editForm.expected_salary}
              rateType={editForm.expected_salary_type}
              onValueChange={(v) => setEditForm({...editForm, expected_salary: v})}
              onRateTypeChange={(v) => setEditForm({...editForm, expected_salary_type: v})}
              rateTypeOptions={CURRENCY_OPTIONS}
            />
            <RateField
              label="Current Salary"
              value={editForm.current_salary}
              rateType={editForm.current_salary_type}
              onValueChange={(v) => setEditForm({...editForm, current_salary: v})}
              onRateTypeChange={(v) => setEditForm({...editForm, current_salary_type: v})}
              rateTypeOptions={CURRENCY_OPTIONS}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InfoDisplay label="Experience (Auto-calculated)" value={candidateFullDetails?.experience && candidateFullDetails.experience.length > 0 ? `${Math.round(candidateFullDetails.experience.length)} roles` : profile?.candidate_experience || "—"} suffix=" years" />
            <InfoDisplay label="Source" value={profile?.candidate_source} />
            <InfoDisplay label="Notice Period" value={profile?.candidate_joining_date} />
            <div />
            <InfoDisplay
              label="Expected Salary"
              value={profile?.candidate_expected_salary ? `${profile?.candidate_expected_salary} ${profile?.candidate_expected_salary_type || '$/Year'}` : null}
            />
            <InfoDisplay
              label="Current Salary"
              value={profile?.candidate_current_salary ? `${profile?.candidate_current_salary} ${profile?.candidate_current_salary_type || '$/Year'}` : null}
            />
          </div>
        )}
      </EditableSection>

      {/* Resume Section */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setResumeExpanded(!resumeExpanded)}
              className="p-1 hover:bg-gray-100 rounded-lg transition"
            >
              {resumeExpanded ? (
                <ChevronDown className="h-5 w-5 text-gray-600" />
              ) : (
                <ChevronRight className="h-5 w-5 text-gray-600" />
              )}
            </button>
            <h3 className="text-sm font-semibold text-gray-900">RESUME</h3>
          </div>
          <div className="flex gap-2">
            <label className="flex items-center gap-2 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition text-xs font-medium cursor-pointer">
              <Upload className="h-4 w-4" />
              Upload Resume
              <input
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                className="hidden"
              />
            </label>
            {resumeData?.file_url && (
              <a
                href={resumeData.file_url}
                download
                className="flex items-center gap-2 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg transition text-xs font-medium text-gray-700"
              >
                <Download className="h-4 w-4" />
                Download
              </a>
            )}
          </div>
        </div>
        {resumeFile && (
          <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-xs text-blue-900"><strong>Selected:</strong> {resumeFile.name}</p>
            <button
              onClick={async () => {
                setUploadingResume(true);
                try {
                  await uploadResume({ candidateId, file: resumeFile });
                  toast.success("Resume uploaded successfully");
                  setResumeFile(null);
                  // Refresh candidate data to show updated resume
                  if (onRefresh) onRefresh();
                } catch (err) {
                  toast.error(err?.message || "Failed to upload resume");
                } finally {
                  setUploadingResume(false);
                }
              }}
              disabled={uploadingResume || !resumeFile}
              className="mt-2 px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded text-xs font-medium transition"
            >
              {uploadingResume ? "Uploading..." : "Upload"}
            </button>
          </div>
        )}
        {resumeData?.file_name && (
          <div className="text-xs text-blue-600 mb-3 hover:text-blue-700 cursor-pointer">
            {resumeData.file_name}
          </div>
        )}
        {resumeExpanded && resumeData?.content && (
          <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200 max-h-96 overflow-y-auto text-sm text-gray-700 whitespace-pre-wrap">
            {resumeData.content}
          </div>
        )}
        {!resumeData && (
          <p className="text-sm text-gray-600">No resume available. Click "Upload Resume" to add one.</p>
        )}
      </div>

      {/* Skills */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">SKILLS</h3>
            <p className="text-xs text-gray-500 mt-1">Extracted from resume - Select top 5-10 skills</p>
          </div>
          <button
            onClick={() => setShowSkillsModal(true)}
            className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition font-medium"
          >
            Manage Skills
          </button>
        </div>

        <div>
          {skills && skills.length > 0 ? (
            <div className="space-y-2">
              {skills.map((skill, idx) => (
                <div key={idx} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                  {skill.isPrimary && <span className="px-2 py-1 bg-orange-100 text-orange-700 text-xs rounded font-semibold">Primary</span>}
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">{skill.name}</p>
                    <p className="text-xs text-gray-600">
                      {skill.yearsOfExperience && `${skill.yearsOfExperience} years`}
                      {skill.yearsOfExperience && skill.lastUsedDate && " • "}
                      {skill.lastUsedDate && `Last used: ${skill.lastUsedDate}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600">No skills selected. Click "Manage Skills" to add your top skills.</p>
          )}
        </div>
      </div>

      {/* Skills Management Modal */}
      {showSkillsModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
            <div className="border-b px-6 py-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Manage Skills</h2>
              <button onClick={() => setShowSkillsModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 max-h-[600px] overflow-y-auto space-y-4">
              <p className="text-sm text-gray-600 mb-4">
                Select your top 5-10 skills from your resume. Mark your primary skill and add years of experience and last used date.
              </p>

              {/* Add New Skill Form */}
              <div className="border-b pb-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  {editingSkillIdx !== null ? "Edit Skill" : "Add New Skill"}
                </h3>
                <Input
                  label="Skill Name"
                  value={skillForm.name}
                  onChange={(v) => setSkillForm({...skillForm, name: v})}
                  placeholder="e.g., React, Project Management"
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Years of Experience"
                    type="number"
                    value={skillForm.yearsOfExperience}
                    onChange={(v) => setSkillForm({...skillForm, yearsOfExperience: v})}
                    placeholder="e.g., 5"
                  />
                  <Input
                    label="Last Used Date"
                    type="date"
                    value={skillForm.lastUsedDate}
                    onChange={(v) => setSkillForm({...skillForm, lastUsedDate: v})}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={skillForm.isPrimary}
                    onChange={(e) => setSkillForm({...skillForm, isPrimary: e.target.checked})}
                    className="w-4 h-4"
                  />
                  <label className="text-sm text-gray-700">Mark as Primary Skill</label>
                </div>
                <button
                  onClick={() => {
                    if (!skillForm.name.trim()) {
                      toast.warning("Please enter skill name");
                      return;
                    }
                    if (editingSkillIdx !== null) {
                      const updated = [...skills];
                      updated[editingSkillIdx] = skillForm;
                      setSkills(updated);
                      setEditingSkillIdx(null);
                    } else {
                      setSkills([...skills, skillForm]);
                    }
                    setSkillForm({ name: "", yearsOfExperience: "", lastUsedDate: "", isPrimary: false });
                  }}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
                >
                  {editingSkillIdx !== null ? "Update Skill" : "Add Skill"}
                </button>
              </div>

              {/* Skills List */}
              {skills.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">Your Skills ({skills.length})</h3>
                  {skills.map((skill, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">
                          {skill.name}
                          {skill.isPrimary && <span className="ml-2 text-orange-600 font-semibold">(Primary)</span>}
                        </p>
                        <p className="text-xs text-gray-600">
                          {skill.yearsOfExperience && `${skill.yearsOfExperience} years`}
                          {skill.yearsOfExperience && skill.lastUsedDate && " • "}
                          {skill.lastUsedDate && `Last used: ${skill.lastUsedDate}`}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setSkillForm(skill);
                            setEditingSkillIdx(idx);
                          }}
                          className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setSkills(skills.filter((_, i) => i !== idx))}
                          className="p-1 text-red-600 hover:bg-red-50 rounded"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t bg-gray-50 px-6 py-4 flex items-center justify-end gap-3">
              <button
                onClick={() => setShowSkillsModal(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition text-sm font-medium"
              >
                Close
              </button>
              <button
                onClick={() => {
                  if (skills.length === 0) {
                    toast.warning("Please add at least one skill");
                    return;
                  }
                  const primarySkill = skills.find(s => s.isPrimary);
                  if (!primarySkill) {
                    toast.warning("Please mark a primary skill");
                    return;
                  }
                  setShowSkillsModal(false);
                  toast.success("Skills updated successfully");
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
              >
                Save Skills
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Education Management Modal */}
      {showEducationModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
            <div className="border-b px-6 py-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Manage Education Details</h2>
              <button onClick={() => setShowEducationModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 max-h-[600px] overflow-y-auto space-y-4">
              {/* Add/Edit Education Form */}
              <div className="border-b pb-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  {editingEducationIdx !== null ? "Edit Education" : "Add Education"}
                </h3>
                <Select
                  label="Education Level"
                  value={educationForm.level}
                  onChange={(v) => setEducationForm({...educationForm, level: v})}
                  options={EDUCATION_LEVELS}
                />
                <Input
                  label="University/College Name"
                  value={educationForm.school || educationForm.university || ""}
                  onChange={(v) => setEducationForm({...educationForm, school: v, university: v})}
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Start Date"
                    type="date"
                    value={educationForm.start_date}
                    onChange={(v) => setEducationForm({...educationForm, start_date: v})}
                  />
                  <Input
                    label="End Date"
                    type="date"
                    value={educationForm.end_date}
                    onChange={(v) => setEducationForm({...educationForm, end_date: v})}
                  />
                </div>
                <Input
                  label="Degree Attained"
                  value={educationForm.degree}
                  onChange={(v) => setEducationForm({...educationForm, degree: v})}
                  placeholder="e.g., B.Tech, M.A., MBA"
                />
                <button
                  onClick={() => {
                    if (!educationForm.level.trim() || !educationForm.school.trim()) {
                      toast.warning("Please fill in all required fields");
                      return;
                    }
                    if (editingEducationIdx !== null) {
                      const updated = [...educationList];
                      updated[editingEducationIdx] = educationForm;
                      setEducationList(updated);
                      setEditingEducationIdx(null);
                    } else {
                      setEducationList([...educationList, educationForm]);
                    }
                    setEducationForm({
                      level: "",
                      school: "",
                      university: "",
                      start_date: "",
                      end_date: "",
                      degree: "",
                    });
                  }}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
                >
                  {editingEducationIdx !== null ? "Update Education" : "Add Education"}
                </button>
              </div>

              {/* Education List */}
              {educationList.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">Your Education ({educationList.length})</h3>
                  {educationList.map((edu, idx) => (
                    <div key={idx} className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">{edu.degree || edu.level}</p>
                        <p className="text-xs text-gray-600">{edu.school || edu.university}</p>
                        {edu.start_date && <p className="text-xs text-gray-600">{edu.start_date} to {edu.end_date}</p>}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setEducationForm(edu);
                            setEditingEducationIdx(idx);
                          }}
                          className="text-blue-600 hover:text-blue-900 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            setEducationList(educationList.filter((_, i) => i !== idx));
                          }}
                          className="text-red-600 hover:text-red-900 text-xs font-medium"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={() => {
                  setShowEducationModal(false);
                  toast.success("Education details updated successfully");
                }}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Experience Management Modal */}
      {showExperienceModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
            <div className="border-b px-6 py-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Manage Experience Details</h2>
              <button onClick={() => setShowExperienceModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 max-h-[600px] overflow-y-auto space-y-4">
              {/* Add/Edit Experience Form */}
              <div className="border-b pb-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  {editingExperienceIdx !== null ? "Edit Experience" : "Add Experience"}
                </h3>
                <Input
                  label="Company Name"
                  value={experienceForm.company}
                  onChange={(v) => setExperienceForm({...experienceForm, company: v})}
                />
                <Input
                  label="Job Title"
                  value={experienceForm.job_title}
                  onChange={(v) => setExperienceForm({...experienceForm, job_title: v})}
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Start Date"
                    type="date"
                    value={experienceForm.start_date}
                    onChange={(v) => setExperienceForm({...experienceForm, start_date: v})}
                  />
                  <Input
                    label="End Date"
                    type="date"
                    value={experienceForm.end_date}
                    onChange={(v) => setExperienceForm({...experienceForm, end_date: v})}
                  />
                </div>
                <Input
                  label="Job Responsibilities"
                  value={experienceForm.job_responsibilities}
                  onChange={(v) => setExperienceForm({...experienceForm, job_responsibilities: v})}
                  placeholder="Describe your key responsibilities"
                />
                <button
                  onClick={() => {
                    if (!experienceForm.company.trim() || !experienceForm.job_title.trim()) {
                      toast.warning("Please fill in all required fields");
                      return;
                    }
                    if (editingExperienceIdx !== null) {
                      const updated = [...experienceList];
                      updated[editingExperienceIdx] = experienceForm;
                      setExperienceList(updated);
                      setEditingExperienceIdx(null);
                    } else {
                      setExperienceList([...experienceList, experienceForm]);
                    }
                    setExperienceForm({
                      company: "",
                      job_title: "",
                      start_date: "",
                      end_date: "",
                      job_responsibilities: "",
                    });
                  }}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
                >
                  {editingExperienceIdx !== null ? "Update Experience" : "Add Experience"}
                </button>
              </div>

              {/* Experience List */}
              {experienceList.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">Your Experience ({experienceList.length})</h3>
                  {experienceList.map((exp, idx) => (
                    <div key={idx} className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">{exp.job_title}</p>
                        <p className="text-xs text-gray-600">{exp.company}</p>
                        {exp.start_date && <p className="text-xs text-gray-600">{exp.start_date} to {exp.end_date}</p>}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setExperienceForm(exp);
                            setEditingExperienceIdx(idx);
                          }}
                          className="text-blue-600 hover:text-blue-900 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            setExperienceList(experienceList.filter((_, i) => i !== idx));
                          }}
                          className="text-red-600 hover:text-red-900 text-xs font-medium"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={() => {
                  setShowExperienceModal(false);
                  toast.success("Experience details updated successfully");
                }}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Certifications Management Modal */}
      {showCertificationsModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
            <div className="border-b px-6 py-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Manage Certifications</h2>
              <button onClick={() => setShowCertificationsModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 max-h-[600px] overflow-y-auto space-y-4">
              {/* Add/Edit Certifications Form */}
              <div className="border-b pb-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  {editingCertificationsIdx !== null ? "Edit Certification" : "Add Certification"}
                </h3>
                <Input
                  label="Certification Name"
                  value={certificationsForm.name || certificationsForm.title || ""}
                  onChange={(v) => setCertificationsForm({...certificationsForm, name: v, title: v})}
                />
                <Input
                  label="Issuing Organization"
                  value={certificationsForm.issuer || certificationsForm.organization || ""}
                  onChange={(v) => setCertificationsForm({...certificationsForm, issuer: v, organization: v})}
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Issue Date"
                    type="date"
                    value={certificationsForm.issue_date}
                    onChange={(v) => setCertificationsForm({...certificationsForm, issue_date: v})}
                  />
                  <Input
                    label="Expiry Date"
                    type="date"
                    value={certificationsForm.expiry_date}
                    onChange={(v) => setCertificationsForm({...certificationsForm, expiry_date: v})}
                  />
                </div>
                <Input
                  label="Credential ID"
                  value={certificationsForm.credential_id}
                  onChange={(v) => setCertificationsForm({...certificationsForm, credential_id: v})}
                  placeholder="Optional credential ID or URL"
                />
                <button
                  onClick={() => {
                    if (!(certificationsForm.name || certificationsForm.title)?.trim()) {
                      toast.warning("Please enter certification name");
                      return;
                    }
                    if (editingCertificationsIdx !== null) {
                      const updated = [...certificationsList];
                      updated[editingCertificationsIdx] = certificationsForm;
                      setCertificationsList(updated);
                      setEditingCertificationsIdx(null);
                    } else {
                      setCertificationsList([...certificationsList, certificationsForm]);
                    }
                    setCertificationsForm({
                      name: "",
                      title: "",
                      issuer: "",
                      organization: "",
                      issue_date: "",
                      expiry_date: "",
                      credential_id: "",
                    });
                  }}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
                >
                  {editingCertificationsIdx !== null ? "Update Certification" : "Add Certification"}
                </button>
              </div>

              {/* Certifications List */}
              {certificationsList.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">Your Certifications ({certificationsList.length})</h3>
                  {certificationsList.map((cert, idx) => (
                    <div key={idx} className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">{cert.name || cert.title}</p>
                        <p className="text-xs text-gray-600">{cert.issuer || cert.organization}</p>
                        {cert.issue_date && <p className="text-xs text-gray-600">Issued: {cert.issue_date}</p>}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setCertificationsForm(cert);
                            setEditingCertificationsIdx(idx);
                          }}
                          className="text-blue-600 hover:text-blue-900 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            setCertificationsList(certificationsList.filter((_, i) => i !== idx));
                          }}
                          className="text-red-600 hover:text-red-900 text-xs font-medium"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={() => {
                  setShowCertificationsModal(false);
                  toast.success("Certifications updated successfully");
                }}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Education Details */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">EDUCATION DETAILS</h3>
            <p className="text-xs text-gray-500 mt-1">Extracted from resume</p>
          </div>
          <button
            onClick={() => setShowEducationModal(true)}
            className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition font-medium"
          >
            Add/Edit
          </button>
        </div>
        {educationList && educationList.length > 0 ? (
          <div className="space-y-4">
            {educationList.map((edu, idx) => (
              <div key={idx} className="pb-4 border-b border-gray-200 last:border-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <InfoDisplay label="Level" value={edu.level || "—"} />
                  <InfoDisplay label="University/College" value={edu.school || edu.university || "—"} />
                  <InfoDisplay label="Start Date" value={edu.start_date || "—"} />
                  <InfoDisplay label="End Date" value={edu.end_date || "—"} />
                  <InfoDisplay label="Degree Attained" value={edu.degree || "—"} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-600">No data available. Click "Add/Edit" to add education details.</p>
        )}
      </div>

      {/* Experience Details */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">EXPERIENCE DETAILS</h3>
            <p className="text-xs text-gray-500 mt-1">Extracted from resume</p>
          </div>
          <button
            onClick={() => setShowExperienceModal(true)}
            className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition font-medium"
          >
            Add/Edit
          </button>
        </div>
        {experienceList && experienceList.length > 0 ? (
          <div className="space-y-4">
            {experienceList.map((exp, idx) => (
              <div key={idx} className="pb-4 border-b border-gray-200 last:border-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <InfoDisplay label="Company" value={exp.company || "—"} />
                  <InfoDisplay label="Job Title" value={exp.job_title || "—"} />
                  <InfoDisplay label="Start Date" value={exp.start_date || "—"} />
                  <InfoDisplay label="End Date" value={exp.end_date || "—"} />
                  <InfoDisplay label="Job Responsibilities" value={exp.job_responsibilities || "—"} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-600">No data available. Click "Add/Edit" to add experience details.</p>
        )}
      </div>

      {/* Certifications */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">CERTIFICATIONS</h3>
            <p className="text-xs text-gray-500 mt-1">Extracted from resume</p>
          </div>
          <button
            onClick={() => setShowCertificationsModal(true)}
            className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition font-medium"
          >
            Add/Edit
          </button>
        </div>
        {certificationsList && certificationsList.length > 0 ? (
          <div className="space-y-4">
            {certificationsList.map((cert, idx) => (
              <div key={idx} className="pb-4 border-b border-gray-200 last:border-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <InfoDisplay label="Certification Name" value={cert.name || cert.title || "—"} />
                  <InfoDisplay label="Issuing Organization" value={cert.issuer || cert.organization || "—"} />
                  <InfoDisplay label="Issue Date" value={cert.issue_date || cert.date || "—"} />
                  <InfoDisplay label="Expiry Date" value={cert.expiry_date || "—"} />
                  <InfoDisplay label="Credential ID" value={cert.credential_id || "—"} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-600">No data available. Click "Add/Edit" to add certifications.</p>
        )}
      </div>

      {/* Identity & Background */}
      <EditableSection
        title="Identity & Background"
        isEditing={editingSection === "identity"}
        isSaving={savingSection === "identity"}
        onEdit={() => handleEditSection("identity")}
        onCancel={handleCancelEdit}
        onSave={() => handleSaveSection("identity")}
      >
        {editingSection === "identity" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Government ID Type"
              value={editForm.govt_id_type || ""}
              onChange={(v) => setEditForm({...editForm, govt_id_type: v})}
              options={GOVT_ID_TYPES}
            />
            <Input
              label="Government ID Number"
              value={editForm.govt_id_number || ""}
              onChange={(v) => setEditForm({...editForm, govt_id_number: v})}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InfoDisplay label="Government ID Type" value={profile?.candidate_govt_id_type} />
            <InfoDisplay label="Government ID Number" value={profile?.candidate_govt_id_number} />
          </div>
        )}
      </EditableSection>

    </div>
  );
}

function EditableSection({ title, subtitle, children, isEditing, isSaving, onEdit, onCancel, onSave }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className="flex gap-2">
          {!isEditing ? (
            <button
              onClick={onEdit}
              className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
              title="Edit section"
            >
              <Edit2 className="h-4 w-4" />
            </button>
          ) : (
            <>
              <button
                onClick={onSave}
                disabled={isSaving}
                className="p-2 text-green-600 hover:text-green-900 hover:bg-green-100 rounded-lg transition disabled:opacity-50"
                title="Save changes"
              >
                {isSaving ? <Loader className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              </button>
              <button
                onClick={onCancel}
                disabled={isSaving}
                className="p-2 text-red-600 hover:text-red-900 hover:bg-red-100 rounded-lg transition disabled:opacity-50"
                title="Cancel"
              >
                <X className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      </div>
      <div>{children}</div>
    </div>
  );
}

function InfoDisplay({ label, value, suffix = "" }) {
  return (
    <div>
      <div className="text-xs font-semibold text-gray-600 mb-1">{label}</div>
      <div className="text-sm font-medium text-gray-900">
        {value || "—"} {suffix}
      </div>
    </div>
  );
}
