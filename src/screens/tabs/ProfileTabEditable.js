import { useEffect, useMemo, useState } from "react";
import { Edit2, Save, X, Loader } from "lucide-react";
import { Button, Input, Select, Card } from "../../components/ui";
import RateField from "../../components/ui/RateField";
import { toast } from "react-toastify";
import {
  getCandidateById,
  getCandidateContacts,
  updateCandidate,
} from "../../services/api/candidates";
import { getHrCandidateFullDetails } from "../../services/api/candidateSelfService";
import { getCandidateDocuments } from "../../services/api/documents";
import { getAllUsers } from "../../services/api/users";

const GENDERS = ["Male", "Female", "Other", "Prefer not to say"];
const SOURCES = ["LinkedIn", "Indeed", "Referral", "Direct Application", "Job Board", "Other"];
const CURRENCY_OPTIONS = ["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year"];

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
      } catch (err) {
        setError(err?.message || "Failed to load profile");
      } finally {
        setLoading(false);
      }
    };

    if (candidateId) load();
  }, [candidateId]);

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
        gender: profile?.candidate_gender || "",
        dob: profile?.candidate_date_of_birth || "",
        job_title: profile?.candidate_job_title || "",
        experience: profile?.candidate_experience || "",
        skills: profile?.candidate_skills?.join(", ") || "",
        joining_date: profile?.candidate_joining_date || "",
        expected_salary: profile?.candidate_expected_salary || "",
        expected_salary_type: profile?.candidate_expected_salary_type || "$/Year",
        current_salary: profile?.candidate_current_salary || "",
        current_salary_type: profile?.candidate_current_salary_type || "$/Year",
        current_location: profile?.candidate_current_location || "",
        source: profile?.candidate_source || "",
        assigned_hr_manager_id: profile?.assigned_hr_manager_id || "",
        assigned_report_manager_id: profile?.assigned_report_manager_id || "",
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
      } else if (section === "personal") {
        updatePayload.candidate_gender = editForm.gender || null;
        updatePayload.candidate_date_of_birth = editForm.dob || null;
        updatePayload.candidate_current_location = editForm.current_location || null;
        updatePayload.candidate_source = editForm.source || null;
      } else if (section === "professional") {
        updatePayload.candidate_experience = editForm.experience || null;
        updatePayload.candidate_skills = editForm.skills
          ? editForm.skills.split(",").map(s => s.trim()).filter(Boolean)
          : null;
        updatePayload.candidate_joining_date = editForm.joining_date || null;
        updatePayload.candidate_expected_salary = editForm.expected_salary || null;
        updatePayload.candidate_expected_salary_type = editForm.expected_salary_type || null;
        updatePayload.candidate_current_salary = editForm.current_salary || null;
        updatePayload.candidate_current_salary_type = editForm.current_salary_type || null;
      } else if (section === "assignment") {
        updatePayload.assigned_hr_manager_id = editForm.assigned_hr_manager_id || null;
        updatePayload.assigned_report_manager_id = editForm.assigned_report_manager_id || null;
      }

      if (onRefresh) {
        await onRefresh(candidateId, updatePayload);
      } else {
        // Fallback: call updateCandidate directly if onRefresh not provided
        await updateCandidate(candidateId, updatePayload);
      }
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
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <InfoDisplay label="First Name" value={profile?.candidate_first_name} />
            <InfoDisplay label="Middle Name" value={profile?.candidate_middle_name} />
            <InfoDisplay label="Last Name" value={profile?.candidate_last_name} />
            <InfoDisplay label="Email" value={profile?.candidate_email} />
            <InfoDisplay label="Mobile" value={profile?.candidate_mobile} />
            <InfoDisplay label="Job Title" value={profile?.candidate_job_title} />
          </div>
        )}
      </EditableSection>

      {/* Personal Information */}
      <EditableSection
        title="Personal Information"
        isEditing={editingSection === "personal"}
        isSaving={savingSection === "personal"}
        onEdit={() => handleEditSection("personal")}
        onCancel={handleCancelEdit}
        onSave={() => handleSaveSection("personal")}
      >
        {editingSection === "personal" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
            <Select
              label="Source"
              value={editForm.source || ""}
              onChange={(v) => setEditForm({...editForm, source: v})}
              options={SOURCES}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InfoDisplay label="Gender" value={profile?.candidate_gender} />
            <InfoDisplay label="Date of Birth" value={profile?.candidate_date_of_birth} />
            <InfoDisplay label="Current Location" value={profile?.candidate_current_location} />
            <InfoDisplay label="Source" value={profile?.candidate_source} />
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
              value={editForm.experience || ""}
              onChange={(v) => setEditForm({...editForm, experience: v})}
            />
            <Input
              label="Skills (comma-separated)"
              value={editForm.skills || ""}
              onChange={(v) => setEditForm({...editForm, skills: v})}
            />
            <Input
              label="Available to Join"
              type="date"
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
            <InfoDisplay label="Experience" value={profile?.candidate_experience} suffix=" years" />
            <InfoDisplay label="Skills" value={Array.isArray(profile?.candidate_skills) ? profile?.candidate_skills.join(", ") : profile?.candidate_skills} />
            <InfoDisplay label="Available to Join" value={profile?.candidate_joining_date} />
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

      {/* Recruitment Assignment (BU-scoped) */}
      <EditableSection
        title="Recruitment Assignment"
        subtitle="Assigned HR Manager and Report Manager (BU-scoped)"
        isEditing={editingSection === "assignment"}
        isSaving={savingSection === "assignment"}
        onEdit={() => handleEditSection("assignment")}
        onCancel={handleCancelEdit}
        onSave={() => handleSaveSection("assignment")}
      >
        {editingSection === "assignment" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="HR Manager"
              value={editForm.assigned_hr_manager_id || ""}
              onChange={(v) => setEditForm({...editForm, assigned_hr_manager_id: v})}
              options={userOptions}
            />
            <Select
              label="Report Manager"
              value={editForm.assigned_report_manager_id || ""}
              onChange={(v) => setEditForm({...editForm, assigned_report_manager_id: v})}
              options={userOptions}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.isArray(users) && (
              <>
                <InfoDisplay
                  label="HR Manager"
                  value={users.find(u => u.id === profile?.assigned_hr_manager_id)
                    ? `${users.find(u => u.id === profile?.assigned_hr_manager_id)?.first_name} ${users.find(u => u.id === profile?.assigned_hr_manager_id)?.last_name || ""}`
                    : "—"}
                />
                <InfoDisplay
                  label="Report Manager"
                  value={users.find(u => u.id === profile?.assigned_report_manager_id)
                    ? `${users.find(u => u.id === profile?.assigned_report_manager_id)?.first_name} ${users.find(u => u.id === profile?.assigned_report_manager_id)?.last_name || ""}`
                    : "—"}
                />
              </>
            )}
          </div>
        )}
      </EditableSection>

      {/* Business Unit (Read-only) */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm opacity-75">
        <div className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          Business Unit
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">Protected</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InfoDisplay label="Business Unit" value={profile?.business_unit_id || "—"} />
          <InfoDisplay label="Assigned on" value={profile?.created_at ? new Date(profile?.created_at).toLocaleDateString() : "—"} />
        </div>
        <p className="text-xs text-gray-500 mt-3">Business Unit is locked to the assigning user's BU and cannot be changed.</p>
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
