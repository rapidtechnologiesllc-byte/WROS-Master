import { useEffect, useMemo, useState } from "react";
import { Edit2, Save, X, Loader, ChevronDown, ChevronRight, Download, Upload, AlertCircle, CheckCircle } from "lucide-react";
import { Input, Select } from "../../components/ui";
import RateField from "../../components/ui/RateField";
import PhoneField, { joinPhone, splitPhone } from "../../components/ui/PhoneField";
import LocationCascadeSelect, { formatLocation, parseLocation } from "../../components/ui/LocationCascadeSelect";
import {
  DEFAULT_SALARY_RATE_TYPE, EDUCATION_LEVELS, GENDER_OPTIONS, SALARY_RATE_TYPES, SOURCE_OPTIONS,
  experienceYears, joinSource, splitSource,
} from "../../utils/candidateFields";
import {
  getCandidateById,
  getEmploymentTypes,
  updateCandidate,
} from "../../services/api/candidates";
import { getHrCandidateFullDetails } from "../../services/api/candidateSelfService";
import { saveCandidateCertifications, saveCandidateEducation, saveCandidateExperience, saveCandidateSkills, saveCandidateQualifications, saveCandidateLicenses } from "../../services/api/candidates";
import { getCandidateDocuments, uploadResume } from "../../services/api/documents";

// The employment-type picker for a country: its accepted types first; types it never accepts
// (C2C, 1099) stay selectable so they can be recorded, marked as not accepted
const employmentTypeOptions = (config, countryCode) => {
  const country = config?.countries?.find((c) => c.code === countryCode);
  const options = country?.options || config?.default_options || [];
  return options.map((o) => ({
    value: o.value,
    label: o.accepted || o.value === "UNKNOWN" || !country ? o.label : `${o.label} (not accepted)`,
  }));
};

// State for action feedback (replaces toast notifications)
const useActionFeedback = () => {
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const clearError = () => setActionError(null);
  const clearSuccess = () => setActionSuccess(null);

  return { actionError, setActionError, actionSuccess, setActionSuccess, clearError, clearSuccess };
};


export default function ProfileTabEditable({ candidateId, candidate = {}, onRefresh }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [candidateFullDetails, setCandidateFullDetails] = useState(null);

  // Action feedback state
  const { actionError, setActionError, actionSuccess, setActionSuccess, clearError, clearSuccess } = useActionFeedback();

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
  const EMPTY_EDUCATION = { level: "", school: "", degree: "", field_of_study: "", start_year: "", end_year: "", percentage: "" };
  const [educationForm, setEducationForm] = useState(EMPTY_EDUCATION);
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

  // Qualifications state
  const [showQualificationsModal, setShowQualificationsModal] = useState(false);
  const [qualificationsList, setQualificationsList] = useState([]);
  const [qualificationsForm, setQualificationsForm] = useState({
    name: "",
    level: "",
    field: "",
    issuer: "",
    issue_date: "",
  });
  const [editingQualificationsIdx, setEditingQualificationsIdx] = useState(null);

  // Licenses state
  const [showLicensesModal, setShowLicensesModal] = useState(false);
  const [licensesList, setLicensesList] = useState([]);
  const [licensesForm, setLicensesForm] = useState({
    name: "",
    number: "",
    issuer: "",
    issue_date: "",
    expiry_date: "",
  });
  const [editingLicensesIdx, setEditingLicensesIdx] = useState(null);

  // Resume upload state
  const [resumeFile, setResumeFile] = useState(null);
  const [uploadingResume, setUploadingResume] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [candidateData, fullDetails] = await Promise.all([
          getCandidateById(candidateId),
          getHrCandidateFullDetails(candidateId),
        ]);
        setData(candidateData);
        setCandidateFullDetails(fullDetails);

        // Load resume data
        try {
          const docs = await getCandidateDocuments(candidateId);
          if (docs && docs.resume) {
            setResumeData(docs.resume);
          }
        } catch (docErr) {
          console.error("[ProfileTabEditable] Failed to load the resume", docErr);
          setActionError(`Could not load the resume: ${docErr.message}`);
        }
      } catch (err) {
        setError(err?.message || "Failed to load profile");
      } finally {
        setLoading(false);
      }
    };

    if (candidateId) load();
  }, [candidateId, setActionError]);

  // Initialize education, experience, and certifications from candidateFullDetails
  useEffect(() => {
    if (candidateFullDetails) {
      // API rows use DB field names; the form works with its own names
      setEducationList((candidateFullDetails.education || []).map((e) => ({
        level: e.education_level || "",
        school: e.education_institute || "",
        degree: e.degree || "",
        field_of_study: e.field_of_study || "",
        start_year: e.starting_year || "",
        end_year: e.year_of_passing || "",
        percentage: e.percentage || "",
      })));
      setExperienceList((candidateFullDetails.experience || []).map((e) => ({
        company: e.company_name || "",
        job_title: e.job_title || "",
        start_date: e.start_date || "",
        end_date: e.end_date || "",
        job_responsibilities: e.responsibilities || "",
      })));
      setCertificationsList((candidateFullDetails.certifications || []).map((c) => ({
        name: c.name || "",
        organization: c.organization || "",
        issue_date: c.issue_date || "",
        expiry_date: c.expiry_date || "",
        credential_id: c.credential_id || "",
      })));
      setSkills((candidateFullDetails.profile_skills || []).map((sk) => ({
        name: sk.name || "",
        yearsOfExperience: sk.years_of_experience || "",
        lastUsedDate: sk.last_used_date || "",
        isPrimary: Boolean(sk.is_primary),
      })));
      setQualificationsList((candidateFullDetails.qualifications || []).map((q) => ({
        name: q.name || "",
        level: q.level || "",
        field: q.field || "",
        issuer: q.issuer || "",
        issue_date: q.issue_date || "",
      })));
      setLicensesList((candidateFullDetails.licenses || []).map((l) => ({
        name: l.name || "",
        number: l.number || "",
        issuer: l.issuer || "",
        issue_date: l.issue_date || "",
        expiry_date: l.expiry_date || "",
      })));
    }
  }, [candidateFullDetails]);

  // Employment types for the candidate's country (C2C and 1099 are recorded, never accepted)
  const [employmentTypes, setEmploymentTypes] = useState(null);
  useEffect(() => {
    let active = true;
    getEmploymentTypes()
      .then((res) => { if (active) setEmploymentTypes(res); })
      .catch((err) => {
        console.error("[ProfileTabEditable] Failed to load employment types", err);
        if (active) setActionError(`Could not load employment types: ${err.message}`);
      });
    return () => { active = false; };
  }, [setActionError]);

  const profile = useMemo(() => {
    const merged = { ...(candidate || {}), ...(data || {}) };
    return merged && Object.keys(merged).length > 0 ? merged : {};
  }, [candidate, data]);

  const handleEditSection = (section) => {
    try {
      if (!profile || Object.keys(profile).length === 0) {
        setActionError("Profile data not loaded yet. Please wait.");
        return;
      }
      setEditingSection(section);
      setEditForm({
        first_name: profile?.candidate_first_name || "",
        middle_name: profile?.candidate_middle_name || "",
        last_name: profile?.candidate_last_name || "",
        email: profile?.candidate_email || "",
        mobile_code: splitPhone(profile?.candidate_mobile).code,
        mobile_number: splitPhone(profile?.candidate_mobile).number,
        job_title: profile?.candidate_job_title || "",
        gender: profile?.candidate_gender || "",
        dob: profile?.candidate_date_of_birth || "",
        location: parseLocation(profile?.candidate_current_location || ""),
        location_text: profile?.candidate_current_location || "",
        experience: profile?.candidate_experience || "",
        joining_date: profile?.candidate_joining_date || "",
        notice_period: profile?.candidate_notice_period || "",
        expected_salary: profile?.candidate_expected_salary || "",
        expected_salary_type: profile?.candidate_expected_salary_type || DEFAULT_SALARY_RATE_TYPE,
        current_salary: profile?.candidate_current_salary || "",
        current_salary_type: profile?.candidate_current_salary_type || DEFAULT_SALARY_RATE_TYPE,
        source: splitSource(profile?.candidate_source).choice,
        source_custom: splitSource(profile?.candidate_source).custom,
        employment_type: profile?.employment_type || "UNKNOWN",
      });
    } catch (err) {
      console.error("Error loading edit form:", err);
      setActionError("Error loading form data. Please refresh and try again.");
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
        updatePayload.candidate_email = editForm.email?.trim() || null;
        updatePayload.candidate_mobile = joinPhone(editForm.mobile_code, editForm.mobile_number) || null;
        updatePayload.candidate_job_title = editForm.job_title || null;
        updatePayload.candidate_gender = editForm.gender || null;
        updatePayload.candidate_date_of_birth = editForm.dob || null;
        const loc = editForm.location || {};
        if (loc.countryCode && loc.stateCode && loc.city) {
          updatePayload.candidate_current_location = formatLocation(loc);
          updatePayload.candidate_country = loc.countryCode;
        } else if (loc.countryCode || loc.stateCode || loc.city) {
          throw new Error("Select Country, State and City for the current location");
        } else if (!editForm.location_text) {
          updatePayload.candidate_current_location = null;
        }
      } else if (section === "professional") {
        updatePayload.candidate_experience = editForm.experience || null;
        updatePayload.candidate_source = joinSource(editForm.source, editForm.source_custom) || null;
        updatePayload.candidate_joining_date = editForm.joining_date || null;
        updatePayload.candidate_notice_period = editForm.notice_period || null;
        updatePayload.candidate_expected_salary = editForm.expected_salary || null;
        updatePayload.candidate_expected_salary_type = editForm.expected_salary_type || null;
        updatePayload.candidate_current_salary = editForm.current_salary || null;
        updatePayload.candidate_current_salary_type = editForm.current_salary_type || null;
        updatePayload.employment_type = editForm.employment_type || null;
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
          console.error("Failed to refresh candidate data after update:", refreshErr);
          setActionError("Changes saved but failed to refresh data. Please reload the page.");
        }
      }, 300);

      setActionSuccess("Profile updated successfully");
      setEditingSection(null);
      setEditForm({});
    } catch (err) {
      setActionError(err?.message || "Failed to save changes");
    } finally {
      setSavingSection(null);
    }
  };

  if (loading) return <div className="p-6 text-center text-gray-500">Loading profile...</div>;

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  }

  return (
    <div className="space-y-4">
      {/* Error Banner */}
      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <p className="text-sm text-red-700">{actionError}</p>
          </div>
          <button
            onClick={clearError}
            className="text-red-600 hover:text-red-700 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Success Banner */}
      {actionSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-emerald-600 flex-shrink-0" />
            <p className="text-sm text-emerald-700">{actionSuccess}</p>
          </div>
          <button
            onClick={clearSuccess}
            className="text-emerald-600 hover:text-emerald-700 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

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
            />
            <PhoneField
              label="Mobile"
              code={editForm.mobile_code}
              number={editForm.mobile_number}
              onCodeChange={(v) => setEditForm({...editForm, mobile_code: v})}
              onNumberChange={(v) => setEditForm({...editForm, mobile_number: v})}
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
              options={["", ...GENDER_OPTIONS]}
            />
            <Input
              label="Date of Birth"
              type="date"
              value={editForm.dob || ""}
              onChange={(v) => setEditForm({...editForm, dob: v})}
            />
            <div className="md:col-span-3">
              <div className="mb-1 text-xs font-semibold text-gray-700">Current Location</div>
              <LocationCascadeSelect
                value={editForm.location || { countryCode: "", stateCode: "", city: "" }}
                onChange={(v) => setEditForm({...editForm, location: v})}
              />
              {editForm.location_text && !editForm.location?.countryCode && (
                <p className="mt-1 text-xs text-amber-700">
                  Saved as "{editForm.location_text}" -- pick Country, State and City to replace it.
                </p>
              )}
            </div>
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
              options={["", ...SOURCE_OPTIONS]}
            />
            <Select
              label="Employment Type"
              value={editForm.employment_type || "UNKNOWN"}
              onChange={(v) => setEditForm({...editForm, employment_type: v})}
              options={employmentTypeOptions(employmentTypes, profile?.candidate_country)}
            />
            {editForm.source === "Other" && (
              <Input
                label="Other Source"
                value={editForm.source_custom || ""}
                onChange={(v) => setEditForm({...editForm, source_custom: v})}
              />
            )}
            <Input
              label="Notice Period (days)"
              type="number"
              placeholder="e.g., 30, 45, 60"
              value={editForm.notice_period || ""}
              onChange={(v) => setEditForm({...editForm, notice_period: v})}
            />
            <Input
              label="Availability Date"
              type="date"
              value={editForm.joining_date || ""}
              onChange={(v) => setEditForm({...editForm, joining_date: v})}
            />
            <RateField
              label="Expected Salary"
              value={editForm.expected_salary}
              rateType={editForm.expected_salary_type}
              onValueChange={(v) => setEditForm({...editForm, expected_salary: v})}
              onRateTypeChange={(v) => setEditForm({...editForm, expected_salary_type: v})}
              rateTypeOptions={SALARY_RATE_TYPES}
            />
            <RateField
              label="Current Salary"
              value={editForm.current_salary}
              rateType={editForm.current_salary_type}
              onValueChange={(v) => setEditForm({...editForm, current_salary: v})}
              onRateTypeChange={(v) => setEditForm({...editForm, current_salary_type: v})}
              rateTypeOptions={SALARY_RATE_TYPES}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InfoDisplay label="Experience (Years)" value={profile?.candidate_experience || "—"} />
            <InfoDisplay label="Source" value={profile?.candidate_source} />
            <InfoDisplay label="Employment Type" value={profile?.employment_type_label} />
            <InfoDisplay label="Notice Period" value={profile?.candidate_notice_period ? `${profile.candidate_notice_period} days` : "—"} />
            <InfoDisplay label="Availability Date" value={profile?.candidate_joining_date} />
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
                  setActionSuccess("Resume uploaded successfully");
                  setResumeFile(null);
                  // Refresh candidate data to show updated resume
                  if (onRefresh) onRefresh();
                } catch (err) {
                  setActionError(err?.message || "Failed to upload resume");
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
                      setActionError("Please enter skill name");
                      return;
                    }
                    clearError();
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
                onClick={async () => {
                  if (skills.length === 0) {
                    setActionError("Please add at least one skill");
                    return;
                  }
                  const primarySkill = skills.find(s => s.isPrimary);
                  if (!primarySkill) {
                    setActionError("Please mark a primary skill");
                    return;
                  }
                  clearError();
                  try {
                    await saveCandidateSkills(candidateId, skills.map((sk) => ({
                      name: sk.name,
                      years_of_experience: sk.yearsOfExperience ? String(sk.yearsOfExperience) : null,
                      last_used_date: sk.lastUsedDate || null,
                      is_primary: Boolean(sk.isPrimary),
                    })));
                  } catch (err) {
                    setActionError(err?.message || "Failed to save skills");
                    return;
                  }
                  setShowSkillsModal(false);
                  setActionSuccess("Skills updated successfully");
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
                <div className="grid grid-cols-2 gap-3">
                  <Select
                    label="Education Level"
                    value={educationForm.level}
                    onChange={(v) => setEducationForm({...educationForm, level: v})}
                    options={["", ...EDUCATION_LEVELS]}
                  />
                  <Input
                    label="Institute"
                    value={educationForm.school || ""}
                    onChange={(v) => setEducationForm({...educationForm, school: v})}
                  />
                  <Input
                    label="Degree"
                    value={educationForm.degree}
                    onChange={(v) => setEducationForm({...educationForm, degree: v})}
                    placeholder="e.g., B.Tech, M.A., MBA"
                  />
                  <Input
                    label="Field of Study"
                    value={educationForm.field_of_study}
                    onChange={(v) => setEducationForm({...educationForm, field_of_study: v})}
                  />
                  <Input
                    label="Start Year"
                    type="number"
                    value={educationForm.start_year}
                    onChange={(v) => setEducationForm({...educationForm, start_year: v.slice(0, 4)})}
                  />
                  <Input
                    label="Year of Passing"
                    type="number"
                    value={educationForm.end_year}
                    onChange={(v) => setEducationForm({...educationForm, end_year: v.slice(0, 4)})}
                  />
                  <Input
                    label="Percentage / CGPA"
                    value={educationForm.percentage}
                    onChange={(v) => setEducationForm({...educationForm, percentage: v.slice(0, 10)})}
                  />
                </div>
                <button
                  onClick={() => {
                    if (!educationForm.school.trim()) {
                      setActionError("Institute is required");
                      return;
                    }
                    clearError();
                    if (editingEducationIdx !== null) {
                      const updated = [...educationList];
                      updated[editingEducationIdx] = educationForm;
                      setEducationList(updated);
                      setEditingEducationIdx(null);
                    } else {
                      setEducationList([...educationList, educationForm]);
                    }
                    setEducationForm(EMPTY_EDUCATION);
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
                        <p className="text-xs text-gray-600">{edu.school}{edu.field_of_study ? ` -- ${edu.field_of_study}` : ""}</p>
                        {(edu.start_year || edu.end_year) && <p className="text-xs text-gray-600">{edu.start_year || "?"} to {edu.end_year || "?"}{edu.percentage ? ` · ${edu.percentage}` : ""}</p>}
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
                onClick={async () => {
                  try {
                    await saveCandidateEducation(candidateId, educationList.map((e) => ({
                      level: e.level || null,
                      institute: e.school || null,
                      degree: e.degree || null,
                      field_of_study: e.field_of_study || null,
                      start: e.start_year || null,
                      end: e.end_year || null,
                      percentage: e.percentage || null,
                    })));
                  } catch (err) {
                    setActionError(err?.message || "Failed to save education");
                    return;
                  }
                  setShowEducationModal(false);
                  setActionSuccess("Education details updated successfully");
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
                      setActionError("Please fill in all required fields");
                      return;
                    }
                    clearError();
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
                onClick={async () => {
                  try {
                    await saveCandidateExperience(candidateId, experienceList.map((e) => ({
                      company: e.company || null,
                      job_title: e.job_title || null,
                      start_date: e.start_date || null,
                      end_date: e.end_date || null,
                      responsibilities: e.job_responsibilities || null,
                    })));
                  } catch (err) {
                    setActionError(err?.message || "Failed to save experience");
                    return;
                  }
                  setShowExperienceModal(false);
                  setActionSuccess("Experience details updated successfully");
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
                      setActionError("Please enter certification name");
                      return;
                    }
                    clearError();
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
                onClick={async () => {
                  try {
                    await saveCandidateCertifications(candidateId, certificationsList
                      .filter((c) => (c.name || c.title || "").trim())
                      .map((c) => ({
                        name: (c.name || c.title).trim(),
                        organization: c.organization || c.issuer || null,
                        issue_date: c.issue_date || null,
                        expiry_date: c.expiry_date || null,
                        credential_id: c.credential_id || null,
                      })));
                  } catch (err) {
                    setActionError(err?.message || "Failed to save certifications");
                    return;
                  }
                  setShowCertificationsModal(false);
                  setActionSuccess("Certifications updated successfully");
                }}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Qualifications Management Modal */}
      {showQualificationsModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
            <div className="border-b px-6 py-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Manage Qualifications</h2>
              <button onClick={() => setShowQualificationsModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 max-h-[600px] overflow-y-auto space-y-4">
              {/* Add/Edit Qualifications Form */}
              <div className="border-b pb-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  {editingQualificationsIdx !== null ? "Edit Qualification" : "Add Qualification"}
                </h3>
                <Input
                  label="Qualification Name"
                  value={qualificationsForm.name || ""}
                  onChange={(v) => setQualificationsForm({...qualificationsForm, name: v})}
                />
                <Input
                  label="Level"
                  value={qualificationsForm.level || ""}
                  onChange={(v) => setQualificationsForm({...qualificationsForm, level: v})}
                  placeholder="e.g., Bachelor, Master, Diploma"
                />
                <Input
                  label="Field"
                  value={qualificationsForm.field || ""}
                  onChange={(v) => setQualificationsForm({...qualificationsForm, field: v})}
                  placeholder="e.g., Computer Science, Engineering"
                />
                <Input
                  label="Issuer"
                  value={qualificationsForm.issuer || ""}
                  onChange={(v) => setQualificationsForm({...qualificationsForm, issuer: v})}
                  placeholder="University or Institution"
                />
                <Input
                  label="Issue Date"
                  type="date"
                  value={qualificationsForm.issue_date}
                  onChange={(v) => setQualificationsForm({...qualificationsForm, issue_date: v})}
                />
                <button
                  onClick={() => {
                    if (!qualificationsForm.name?.trim()) {
                      setActionError("Please enter qualification name");
                      return;
                    }
                    clearError();
                    if (editingQualificationsIdx !== null) {
                      const updated = [...qualificationsList];
                      updated[editingQualificationsIdx] = qualificationsForm;
                      setQualificationsList(updated);
                      setEditingQualificationsIdx(null);
                    } else {
                      setQualificationsList([...qualificationsList, qualificationsForm]);
                    }
                    setQualificationsForm({ name: "", level: "", field: "", issuer: "", issue_date: "" });
                  }}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
                >
                  {editingQualificationsIdx !== null ? "Update Qualification" : "Add Qualification"}
                </button>
              </div>

              {/* Qualifications List */}
              {qualificationsList.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">Your Qualifications ({qualificationsList.length})</h3>
                  {qualificationsList.map((qual, idx) => (
                    <div key={idx} className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">{qual.name}</p>
                        <p className="text-xs text-gray-600">{qual.level} in {qual.field}</p>
                        <p className="text-xs text-gray-600">{qual.issuer}</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setQualificationsForm(qual);
                            setEditingQualificationsIdx(idx);
                          }}
                          className="text-blue-600 hover:text-blue-900 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            setQualificationsList(qualificationsList.filter((_, i) => i !== idx));
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
                onClick={async () => {
                  try {
                    await saveCandidateQualifications(candidateId, qualificationsList
                      .filter((q) => q.name?.trim())
                      .map((q) => ({
                        name: q.name.trim(),
                        level: q.level || null,
                        field: q.field || null,
                        issuer: q.issuer || null,
                        issue_date: q.issue_date || null,
                      })));
                  } catch (err) {
                    setActionError(err?.message || "Failed to save qualifications");
                    return;
                  }
                  setShowQualificationsModal(false);
                  setActionSuccess("Qualifications updated successfully");
                }}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Licenses Management Modal */}
      {showLicensesModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
            <div className="border-b px-6 py-5 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Manage Licenses</h2>
              <button onClick={() => setShowLicensesModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 max-h-[600px] overflow-y-auto space-y-4">
              {/* Add/Edit Licenses Form */}
              <div className="border-b pb-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  {editingLicensesIdx !== null ? "Edit License" : "Add License"}
                </h3>
                <Input
                  label="License Name"
                  value={licensesForm.name || ""}
                  onChange={(v) => setLicensesForm({...licensesForm, name: v})}
                />
                <Input
                  label="License Number"
                  value={licensesForm.number || ""}
                  onChange={(v) => setLicensesForm({...licensesForm, number: v})}
                />
                <Input
                  label="Issuer"
                  value={licensesForm.issuer || ""}
                  onChange={(v) => setLicensesForm({...licensesForm, issuer: v})}
                  placeholder="Government or organization"
                />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    label="Issue Date"
                    type="date"
                    value={licensesForm.issue_date}
                    onChange={(v) => setLicensesForm({...licensesForm, issue_date: v})}
                  />
                  <Input
                    label="Expiry Date"
                    type="date"
                    value={licensesForm.expiry_date}
                    onChange={(v) => setLicensesForm({...licensesForm, expiry_date: v})}
                  />
                </div>
                <button
                  onClick={() => {
                    if (!licensesForm.name?.trim()) {
                      setActionError("Please enter license name");
                      return;
                    }
                    clearError();
                    if (editingLicensesIdx !== null) {
                      const updated = [...licensesList];
                      updated[editingLicensesIdx] = licensesForm;
                      setLicensesList(updated);
                      setEditingLicensesIdx(null);
                    } else {
                      setLicensesList([...licensesList, licensesForm]);
                    }
                    setLicensesForm({ name: "", number: "", issuer: "", issue_date: "", expiry_date: "" });
                  }}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium"
                >
                  {editingLicensesIdx !== null ? "Update License" : "Add License"}
                </button>
              </div>

              {/* Licenses List */}
              {licensesList.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">Your Licenses ({licensesList.length})</h3>
                  {licensesList.map((lic, idx) => (
                    <div key={idx} className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">{lic.name}</p>
                        <p className="text-xs text-gray-600">License #: {lic.number}</p>
                        <p className="text-xs text-gray-600">{lic.issuer}</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setLicensesForm(lic);
                            setEditingLicensesIdx(idx);
                          }}
                          className="text-blue-600 hover:text-blue-900 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            setLicensesList(licensesList.filter((_, i) => i !== idx));
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
                onClick={async () => {
                  try {
                    await saveCandidateLicenses(candidateId, licensesList
                      .filter((l) => l.name?.trim())
                      .map((l) => ({
                        name: l.name.trim(),
                        number: l.number || null,
                        issuer: l.issuer || null,
                        issue_date: l.issue_date || null,
                        expiry_date: l.expiry_date || null,
                      })));
                  } catch (err) {
                    setActionError(err?.message || "Failed to save licenses");
                    return;
                  }
                  setShowLicensesModal(false);
                  setActionSuccess("Licenses updated successfully");
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
                  <InfoDisplay label="Institute" value={edu.school || "—"} />
                  <InfoDisplay label="Degree" value={edu.degree || "—"} />
                  <InfoDisplay label="Field of Study" value={edu.field_of_study || "—"} />
                  <InfoDisplay label="Start Year" value={edu.start_year || "—"} />
                  <InfoDisplay label="Year of Passing" value={edu.end_year || "—"} />
                  <InfoDisplay label="Percentage / CGPA" value={edu.percentage || "—"} />
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
                  <InfoDisplay label="End Date" value={exp.end_date || "Present"} />
                  <InfoDisplay label="Years" value={experienceYears(exp.start_date, exp.end_date) || "—"} />
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

      {/* Qualifications */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">QUALIFICATIONS</h3>
            <p className="text-xs text-gray-500 mt-1">Professional qualifications and credentials</p>
          </div>
          <button
            onClick={() => setShowQualificationsModal(true)}
            className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition font-medium"
          >
            Add/Edit
          </button>
        </div>
        {qualificationsList && qualificationsList.length > 0 ? (
          <div className="space-y-4">
            {qualificationsList.map((qual, idx) => (
              <div key={idx} className="pb-4 border-b border-gray-200 last:border-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <InfoDisplay label="Qualification Name" value={qual.name || "—"} />
                  <InfoDisplay label="Level" value={qual.level || "—"} />
                  <InfoDisplay label="Field" value={qual.field || "—"} />
                  <InfoDisplay label="Issuer" value={qual.issuer || "—"} />
                  <InfoDisplay label="Issue Date" value={qual.issue_date || "—"} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-600">No data available. Click "Add/Edit" to add qualifications.</p>
        )}
      </div>

      {/* Licenses */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">LICENSES</h3>
            <p className="text-xs text-gray-500 mt-1">Professional licenses and certifications</p>
          </div>
          <button
            onClick={() => setShowLicensesModal(true)}
            className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition font-medium"
          >
            Add/Edit
          </button>
        </div>
        {licensesList && licensesList.length > 0 ? (
          <div className="space-y-4">
            {licensesList.map((lic, idx) => (
              <div key={idx} className="pb-4 border-b border-gray-200 last:border-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <InfoDisplay label="License Name" value={lic.name || "—"} />
                  <InfoDisplay label="License Number" value={lic.number || "—"} />
                  <InfoDisplay label="Issuer" value={lic.issuer || "—"} />
                  <InfoDisplay label="Issue Date" value={lic.issue_date || "—"} />
                  <InfoDisplay label="Expiry Date" value={lic.expiry_date || "—"} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-600">No data available. Click "Add/Edit" to add licenses.</p>
        )}
      </div>

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
