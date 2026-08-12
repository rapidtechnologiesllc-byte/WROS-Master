import { useEffect, useMemo, useRef, useState } from "react";
import { Card, Button } from "../components/ui";
import ProfileTabEditable from "./tabs/ProfileTabEditable";
import FeedbackTab from "./tabs/FeedbackTab";
import DocumentsTab from "./tabs/DocumentsTab";
import TasksTab from "./tabs/TasksTab";
import InterviewsTab from "./tabs/InterviewsTab";
import IntelligenceTab from "./tabs/IntelligenceTab";
import HistoryTab from "./tabs/HistoryTab";
import MessagesTab from "./tabs/MessagesTab";
import CandidateJourney from "../components/candidate/CandidateJourney";
import CandidateEditModal from "./CandidateEditModal";
import {
  getCandidateStatus,
  updateCandidateStatus,
} from "../services/api/candidateStatus";
import {
  createCandidateHistoryEvent,
  HISTORY_EVENT_TYPES,
} from "../services/api/candidateHistory";
import {
  listChecklistTemplates,
  assignChecklistToCandidate,
  getChecklistTemplate,
  getCandidateChecklists,
} from "../services/api/checklists";
import {
  createInterviewPanel,
  assignPanelMember,
  createInterview,
} from "../services/api/interviews";
import { sendPlainEmail, sendInterviewInvite } from "../services/api/email";
import { getCandidateDocuments } from "../services/api/documents";
import { getAllUsers } from "../services/api/users";
import { getCandidateById } from "../services/api/candidates";
import {
  getOnlineInterviewEmailTemplate,
  getFaceToFaceInterviewEmailTemplate,
} from "../utils/interviewEmailTemplates";
import { Mail, MessageCircle, Phone } from "lucide-react";
import CandidateAssignJobModal from "./CandidateAssignJobModal";
import StatusDropdown from "../components/ui/StatusDropdown";
import PreonboardingModal from "./PreonboardingModal";
import { getCandidateNotes, createCandidateNote } from "../services/api/notes";
import { getCandidateApplications, getActiveJobs } from "../services/api/jobs";
import ReactMarkdown from "react-markdown";
import { renderToStaticMarkup } from "react-dom/server";
import { AcceptButton } from "../styles/CandidateSearchStyles";
import { managerReviewApprove } from "../services/api/preOnboarding";
import { toast, ToastContainer } from "react-toastify";
import { getEmailBodyHTML } from "../utils/preboardingEmailTemplate";
import { getAllOffers } from "../services/api/offerLetters";
import PreviousOfferModal from "./PreviousOfferModal";

const initialScheduleForm = {
  roundName: "",
  interviewerIds: [],
  interviewDate: "",
  startTime: "",
  endTime: "",
  durationMinutes: "60",
  timezone: "Asia/Kolkata",
  meetingPlatform: "Microsoft Teams",
  location: "",
  emailTemplate: "Online Interview",
  emailSubject: "",
  emailBody: "",
  ccEmails: "",
  extraNotes: "",
};

const durationOptions = [
  { label: "30 mins", value: "30" },
  { label: "45 mins", value: "45" },
  { label: "60 mins", value: "60" },
  { label: "90 mins", value: "90" },
  { label: "120 mins", value: "120" },
];

const timezoneOptions = [
  "Asia/Kolkata",
  "UTC",
  "America/New_York",
  "Europe/London",
  "Asia/Dubai",
  "Asia/Singapore",
];

const meetingPlatformOptions = ["Microsoft Teams", "Other"];

const emailTemplateOptions = [
  "Online Interview",
  "Face to Face Interview",
  "Custom",
];
const roundNameOptions = [
  { label: "L1 Interview", value: "L1 Interview" },
  { label: "L2 Interview", value: "L2 Interview" },
];

function UsersBUDetailsPanel({ candidate, onUpdate }) {
  const [isEditing, setIsEditing] = useState(false);
  const [recruiters, setRecruiters] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [loadingRecruiters, setLoadingRecruiters] = useState(false);
  const [loadingBUs, setLoadingBUs] = useState(false);
  const [loadingJobBU, setLoadingJobBU] = useState(false);
  const [selectedRecruiter, setSelectedRecruiter] = useState(candidate?.assigned_recruiter_id || "");
  const [selectedBU, setSelectedBU] = useState(candidate?.business_unit_id || "");
  const [jobBU, setJobBU] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const loadJobBU = async () => {
      if (!candidate?.id) return;
      try {
        setLoadingJobBU(true);
        const response = await fetch(`/candidates/${candidate.id}/applications`, {
          headers: { "Authorization": `Bearer ${localStorage.getItem("access_token")}` },
        });
        if (response.ok) {
          const data = await response.json();
          const applications = data.applications || [];
          if (applications.length > 0) {
            const activeJob = applications[0];
            if (activeJob.business_unit_id && !selectedBU) {
              setJobBU(activeJob.business_unit_id);
              setSelectedBU(activeJob.business_unit_id);
            }
          }
        }
      } catch (error) {
        console.error("Failed to load candidate job BU:", error);
      } finally {
        setLoadingJobBU(false);
      }
    };

    loadJobBU();
  }, [candidate?.id]);

  useEffect(() => {
    if (!isEditing) return;

    const loadData = async () => {
      try {
        setLoadingRecruiters(true);
        const allUsers = await getAllUsers();
        const recruitersList = Array.isArray(allUsers)
          ? allUsers.filter(u => u.user_role === "Recruiter" || u.permission_role === "Recruiter")
          : allUsers?.users?.filter(u => u.user_role === "Recruiter" || u.permission_role === "Recruiter") || [];
        console.log("Loaded recruiters:", recruitersList);
        setRecruiters(recruitersList);
      } catch (error) {
        console.error("Failed to load recruiters:", error);
        setRecruiters([]);
      } finally {
        setLoadingRecruiters(false);
      }

      try {
        setLoadingBUs(true);
        const response = await fetch(`/api/business-units`, {
          headers: {
            "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
          },
        });
        if (response.ok) {
          const buData = await response.json();
          const buList = Array.isArray(buData) ? buData : buData.business_units || [];
          console.log("Loaded business units:", buList);
          setBusinessUnits(buList);
        } else {
          setBusinessUnits([]);
        }
      } catch (error) {
        console.error("Failed to load business units:", error);
        setBusinessUnits([]);
      } finally {
        setLoadingBUs(false);
      }
    };

    loadData();
  }, [isEditing]);

  const handleSave = async () => {
    if (!selectedRecruiter && !selectedBU) {
      alert("Please select at least a recruiter or business unit");
      return;
    }

    try {
      setSaving(true);
      const updates = {};

      if (selectedRecruiter) {
        const recruiter = recruiters.find(r => r.user_id === selectedRecruiter);
        updates.assigned_recruiter_id = selectedRecruiter;
        updates.assigned_recruiter_name = recruiter?.user_name || "";
      }

      if (selectedBU) {
        const bu = businessUnits.find(b => String(b.id) === String(selectedBU));
        updates.business_unit_id = selectedBU;
        updates.business_unit_name = bu?.name || bu?.bu_name || "";
      }

      if (onUpdate) {
        await onUpdate(updates);
      }
      setIsEditing(false);
    } catch (error) {
      console.error("Failed to update:", error);
      alert("Failed to save changes");
    } finally {
      setSaving(false);
    }
  };

  if (!isEditing) {
    return (
      <div className="bg-white border rounded-2xl shadow-sm">
        <div className="border-b px-5 py-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Users & BU Details</h3>
          <button
            onClick={() => {
              setSelectedRecruiter(candidate?.assigned_recruiter_id || "");
              setIsEditing(true);
            }}
            className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition font-medium"
          >
            Edit
          </button>
        </div>
        <div className="px-5 py-4 space-y-4 text-xs">
          <div>
            <div className="text-gray-600 font-medium mb-1">Recruiter</div>
            <div className="text-gray-900 font-semibold">{candidate?.assigned_recruiter_name || "—"}</div>
          </div>

          <div className="border-t pt-3">
            <div className="text-gray-600 font-medium mb-1">Business Unit</div>
            <div className="text-gray-900 font-semibold">{candidate?.business_unit_id || "—"}</div>
          </div>

          {candidate?.has_job_submission && (
            <>
              <div className="border-t pt-3">
                <div className="text-gray-600 font-medium mb-1">HR Manager</div>
                <div className="text-gray-900 font-semibold">{candidate?.assigned_hr_manager_name || "—"}</div>
              </div>

              <div>
                <div className="text-gray-600 font-medium mb-1">Hiring Manager</div>
                <div className="text-gray-900 font-semibold">{candidate?.assigned_hiring_manager_name || "—"}</div>
              </div>

              <div>
                <div className="text-gray-600 font-medium mb-1">HR BP</div>
                <div className="text-gray-900 font-semibold">{candidate?.assigned_hr_bp_name || "—"}</div>
              </div>

              <div>
                <div className="text-gray-600 font-medium mb-1">BU Head</div>
                <div className="text-gray-900 font-semibold">{candidate?.assigned_bu_head_name || "—"}</div>
              </div>

              <div>
                <div className="text-gray-600 font-medium mb-1">Report Manager</div>
                <div className="text-gray-900 font-semibold">{candidate?.assigned_report_manager_name || "—"}</div>
              </div>
            </>
          )}

          {!candidate?.has_job_submission && (
            <div className="border-t pt-3">
              <p className="text-gray-500 italic text-xs">Additional users will appear as the candidate proceeds through the recruitment process.</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border rounded-2xl shadow-sm">
      <div className="border-b px-5 py-4">
        <h3 className="text-sm font-semibold text-gray-900">Edit Users & BU</h3>
      </div>
      <div className="px-5 py-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Recruiter</label>
          <select
            value={selectedRecruiter}
            onChange={(e) => setSelectedRecruiter(e.target.value)}
            disabled={loadingRecruiters}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{loadingRecruiters ? "Loading recruiters..." : "Select a recruiter"}</option>
            {recruiters.map((recruiter) => (
              <option key={recruiter.user_id} value={recruiter.user_id}>
                {recruiter.user_name} ({recruiter.user_email})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Business Unit</label>
          <select
            value={selectedBU}
            onChange={(e) => setSelectedBU(e.target.value)}
            disabled={loadingBUs}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{loadingBUs ? "Loading business units..." : "Select a business unit"}</option>
            {businessUnits.map((bu) => (
              <option key={bu.id} value={bu.id}>
                {bu.name || bu.bu_name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="border-t px-5 py-4 flex gap-3 justify-end">
        <button
          onClick={() => setIsEditing(false)}
          disabled={saving}
          className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition font-medium text-sm disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving || (!selectedRecruiter && !selectedBU)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}

export default function CandidateDetailsScreen({
  apiState,
  candidate,
  onBack,
  onUpdateCandidate,
  onRefreshCandidates,
  setSelectedCandidate,
  limitedMode = false,
  defaultTab = "profile",
  autoOpenSchedule = false,
}) {
  const [activeTab, setActiveTab] = useState(defaultTab || "profile");
  const [statusData, setStatusData] = useState(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("success");
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [selectedTemplateData, setSelectedTemplateData] = useState(null);
  const [assigning, setAssigning] = useState(false);
  const [isChecklistAssigned, setIsChecklistAssigned] = useState(false);
  const [showScheduleMenu, setShowScheduleMenu] = useState(false);
  const scheduleMenuRef = useRef(null);
  const notesMenuRef = useRef(null);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleType, setScheduleType] = useState("");
  const [scheduleForm, setScheduleForm] = useState(initialScheduleForm);
  const [scheduleErrors, setScheduleErrors] = useState({});
  const [scheduling, setScheduling] = useState(false);
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [showPanelMemberDropdown, setShowPanelMemberDropdown] = useState(false);
  const [panelSearch, setPanelSearch] = useState("");
  const [preonboardingModal, setPreonboardingModal] = useState(false);
  const [radioStatus, setRadioStatus] = useState("");
  const [updatedStatus, setUpdatedStatus] = useState(null);
  const [notes, setNotes] = useState([]);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [noteInput, setNoteInput] = useState("");
  const [showNotesMenu, setShowNotesMenu] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [candidateJobs, setCandidateJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [loadingCandidateJobs, setLoadingCandidateJobs] = useState(false);
  const [candidateDocCount, setCandidateDocCount] = useState(null);
  const [offerId, setOfferId] = useState(null);
  const [previousOffer, setPreviousOffer] = useState([]);
  const [previousOfferModalState, setPreviousOfferModalState] = useState(false);
  const isApproved = candidate?.pipelineStatus === "Pre-Onboarding";
  const panelMemberDropdownRef = useRef(null);
  const noticeTimerRef = useRef(null);
  const currentRole = localStorage.getItem("permission_role");
  const candidateTabs = limitedMode
    ? ["feedback"]
    : [
        "profile",
        "messages",
        "interview",
        "intelligence",
        "documents",
        "tasks",
        "history",
      ];

  const canShowFullActions = !limitedMode;

  useEffect(() => {
    if (limitedMode) return;
    const fetchCandidateOffer = async () => {
      const canOffer = await getAllOffers({ candidate_id: candidate?.id });
      setPreviousOffer(canOffer?.offers);
    };
    fetchCandidateOffer();
  }, [candidate?.id, limitedMode]);

  useEffect(() => {
    if (limitedMode) {
      setActiveTab("feedback");
      return;
    }
    setActiveTab(defaultTab || "profile");
  }, [defaultTab, limitedMode]);

  useEffect(() => {
    if (!autoOpenSchedule) return;
    openScheduleModal("online");
  }, [autoOpenSchedule]);

  useEffect(() => {
    if (limitedMode || !candidate?.id) return;
    const fetchStatus = async () => {
      try {
        const res = await getCandidateStatus(candidate.id);
        setStatusData(res);
      } catch (err) {
        console.error("Failed to fetch candidate status", err);
      }
    };
    fetchStatus();
  }, [candidate?.id, updatedStatus, limitedMode]);

  useEffect(() => {
    if (limitedMode || !candidate?.id) return;
    const checkChecklist = async () => {
      try {
        const res = await getCandidateChecklists(candidate.id);
        setIsChecklistAssigned(Boolean(res && res.length > 0));
      } catch (err) {
        console.error("Failed to check checklist", err);
      }
    };
    checkChecklist();
  }, [candidate?.id, limitedMode]);

  useEffect(() => {
    if (!candidate?.id) return;
    const loadNotes = async () => {
      try {
        setLoadingNotes(true);
        const response = await getCandidateNotes(candidate?.id);
        setNotes(response?.notes || []);
      } catch (error) {
        console.error("Failed to fetch candidate notes", error);
      } finally {
        setLoadingNotes(false);
      }
    };
    loadNotes();
  }, [candidate?.id]);

  useEffect(() => {
    if (!showAssignModal) return;
    const fetchTemplates = async () => {
      try {
        setLoadingTemplates(true);
        const res = await listChecklistTemplates();
        setTemplates(res?.templates || []);
      } catch (err) {
        console.error("Failed to fetch templates", err);
      } finally {
        setLoadingTemplates(false);
      }
    };
    fetchTemplates();
  }, [showAssignModal]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        scheduleMenuRef.current &&
        !scheduleMenuRef.current.contains(event.target)
      ) {
        setShowScheduleMenu(false);
      }
    };
    if (showScheduleMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showScheduleMenu]);
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        notesMenuRef.current &&
        !notesMenuRef.current.contains(event.target)
      ) {
        setShowNotesMenu(false);
      }
    };
    if (showNotesMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showNotesMenu]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        panelMemberDropdownRef.current &&
        !panelMemberDropdownRef.current.contains(event.target)
      ) {
        setShowPanelMemberDropdown(false);
      }
    };
    if (showPanelMemberDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showPanelMemberDropdown]);

  useEffect(() => {
    if (!showScheduleModal) return;
    const fetchUsers = async () => {
      try {
        setLoadingUsers(true);
        const res = await getAllUsers();
        setUsers(Array.isArray(res) ? res : []);
      } catch (err) {
        console.error("Failed to fetch users", err);
        showNotice("Failed to load panel members", "error");
      } finally {
        setLoadingUsers(false);
      }
    };
    fetchUsers();
  }, [showScheduleModal]);

  const interviewerOptions = useMemo(() => {
    if (!Array.isArray(users)) return [];
    return users
      .filter((user) => user?.user_id)
      .map((user) => ({
        value: user.user_id,
        label: `${user.user_name || "Unknown"} (${user.user_role || "role not set"})`,
      }));
  }, [users]);

  const selectedPanelMembers = useMemo(() => {
    return interviewerOptions.filter((option) =>
      scheduleForm.interviewerIds.includes(option.value),
    );
  }, [interviewerOptions, scheduleForm.interviewerIds]);

  const filteredPanelMembers = useMemo(() => {
    if (!panelSearch.trim()) return interviewerOptions;
    return interviewerOptions.filter((member) =>
      member.label.toLowerCase().includes(panelSearch.toLowerCase()),
    );
  }, [panelSearch, interviewerOptions]);

  useEffect(() => {
    return () => {
      if (noticeTimerRef.current) {
        clearTimeout(noticeTimerRef.current);
      }
    };
  }, []);
  useEffect(() => {
    if (limitedMode) {
      setActiveTab("feedback");
    }
  }, [limitedMode]);

  const showNotice = (message, type = "success", duration = 3000) => {
    setNotice(message);
    setNoticeType(type);
    if (noticeTimerRef.current) {
      clearTimeout(noticeTimerRef.current);
    }
    noticeTimerRef.current = setTimeout(() => {
      setNotice("");
    }, duration);
  };

  useEffect(() => {
    if (limitedMode) return;
    const loadDocumentCount = async () => {
      try {
        const docs = await getCandidateDocuments(candidate?.id);
        setCandidateDocCount(docs);
      } catch (error) {
        console.error(error);
      }
    };
    if (candidate?.id) {
      loadDocumentCount();
    }

    // Load candidate job applications for Schedule button visibility
    const loadCandidateJobs = async () => {
      try {
        const candidateId = candidate?.candidate_id ?? candidate?.id ?? candidate?._id;
        const response = await getCandidateApplications(candidateId);
        const applications = response?.applications ?? [];
        setCandidateJobs(applications);
      } catch (error) {
        console.error("Failed to fetch candidate jobs:", error);
        setCandidateJobs([]);
      }
    };
    if (candidate?.id) {
      loadCandidateJobs();
    }
  }, [candidate?.id, limitedMode]);

  // Load full candidate details to populate all form fields (commented out - CandidateDetailsWrapper already loads this)
  // useEffect(() => {
  //   const loadFullCandidateDetails = async () => {
  //     try {
  //       const candidateId = candidate?.candidate_id ?? candidate?.id ?? candidate?._id;
  //       if (candidateId) {
  //         const fullCandidate = await getCandidateById(candidateId);
  //         if (fullCandidate && onUpdateCandidate) {
  //           onUpdateCandidate(fullCandidate);  // This was calling onUpdateCandidate(fullCandidate) with 1 arg instead of 2
  //         }
  //       }
  //     } catch (error) {
  //       console.error("Failed to fetch full candidate details:", error);
  //     }
  //   };
  //   if (candidate?.id && !limitedMode) {
  //     loadFullCandidateDetails();
  //   }
  // }, [candidate?.id, limitedMode, onUpdateCandidate]);

  const handleTemplateChange = async (id) => {
    setSelectedTemplate(id);

    try {
      const res = await getChecklistTemplate(id);
      setSelectedTemplateData(res);
    } catch (err) {
      console.error("Failed to fetch template details", err);
    }
  };

  const handleAssignChecklist = async () => {
    if (!selectedTemplate) return;
    try {
      setAssigning(true);
      await assignChecklistToCandidate({
        candidateId: candidate?.id,
        templateId: selectedTemplate,
      });
      showNotice("Checklist assigned successfully");
      setActiveTab("tasks");
      setIsChecklistAssigned(true);
      setShowAssignModal(false);
      setSelectedTemplate("");
      setSelectedTemplateData(null);
    } catch (err) {
      console.error(err);
      showNotice(err?.message || "Failed to assign checklist", "error");
    } finally {
      setAssigning(false);
    }
  };

  const buildTemplateValues = (templateName, type) => {
    const candidateName = candidate?.name || "Candidate";
    const jobTitle = candidate?.jobTitle || "Interview";
    if (templateName === "Face to Face Interview") {
      return getFaceToFaceInterviewEmailTemplate({ candidateName, jobTitle });
    }
    if (templateName === "Online Interview") {
      return getOnlineInterviewEmailTemplate({ candidateName, jobTitle });
    }
    if (type === "faceToFace") {
      return getFaceToFaceInterviewEmailTemplate({ candidateName, jobTitle });
    }
    return getOnlineInterviewEmailTemplate({ candidateName, jobTitle });
  };

  const recomputeEndTime = (dateValue, startTimeValue, durationValue) => {
    if (!dateValue || !startTimeValue || !durationValue) return "";
    const start = new Date(`${dateValue}T${startTimeValue}`);
    if (Number.isNaN(start.getTime())) return "";
    const end = new Date(start.getTime() + Number(durationValue) * 60 * 1000);
    const hours = String(end.getHours()).padStart(2, "0");
    const minutes = String(end.getMinutes()).padStart(2, "0");
    return `${hours}:${minutes}`;
  };

  const recomputeDuration = (dateValue, startTimeValue, endTimeValue) => {
    if (!dateValue || !startTimeValue || !endTimeValue) return "";
    const start = new Date(`${dateValue}T${startTimeValue}`);
    const end = new Date(`${dateValue}T${endTimeValue}`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return "";
    }
    if (end.getTime() <= start.getTime()) {
      end.setDate(end.getDate() + 1);
    }
    const diffMinutes = Math.round(
      (end.getTime() - start.getTime()) / (60 * 1000),
    );
    return String(diffMinutes);
  };

  const openScheduleModal = async (type) => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");
    const defaultDate = `${year}-${month}-${day}`;
    const defaultTemplate =
      type === "online" ? "Online Interview" : "Face to Face Interview";
    const defaults = buildTemplateValues(defaultTemplate, type);
    setShowScheduleMenu(false);
    setScheduleType(type);
    setScheduleErrors({});
    setPanelSearch("");
    setShowPanelMemberDropdown(false);
    setScheduleForm({
      ...initialScheduleForm,
      interviewDate: defaultDate,
      meetingPlatform: type === "online" ? "Microsoft Teams" : "In Person",
      emailTemplate: defaultTemplate,
      emailSubject: defaults.subject,
      emailBody: defaults.body,
    });
    try {
      setLoadingCandidateJobs(true);
      const candidateId =
        candidate?.candidate_id ?? candidate?.id ?? candidate?._id;
      const response = await getCandidateApplications(candidateId);
      const applications = response?.applications ?? [];
      setCandidateJobs(applications);
      setSelectedJobId("");
    } catch (error) {
      console.error("Failed to fetch candidate applications", error);
      setCandidateJobs([]);
      setSelectedJobId("");
    } finally {
      setLoadingCandidateJobs(false);
    }
    setShowScheduleModal(true);
  };

  const closeScheduleModal = () => {
    if (scheduling) return;
    setShowScheduleModal(false);
    setScheduleType("");
    setScheduleErrors({});
    setPanelSearch("");
    setShowPanelMemberDropdown(false);
    setCandidateJobs([]);
    setSelectedJobId("");
    setScheduleForm(initialScheduleForm);
  };

  const handleScheduleInputChange = (field, value) => {
    setScheduleForm((prev) => {
      const updated = {
        ...prev,
        [field]: value,
      };
      if (field === "emailTemplate") {
        const templateValues = buildTemplateValues(value, scheduleType);
        updated.emailSubject = templateValues.subject;
        updated.emailBody = templateValues.body;
      }
      if (
        field === "interviewDate" ||
        field === "startTime" ||
        field === "durationMinutes"
      ) {
        updated.endTime = recomputeEndTime(
          field === "interviewDate" ? value : updated.interviewDate,
          field === "startTime" ? value : updated.startTime,
          field === "durationMinutes" ? value : updated.durationMinutes,
        );
      }
      return updated;
    });

    if (scheduleErrors[field]) {
      setScheduleErrors((prev) => ({
        ...prev,
        [field]: "",
      }));
    }
  };

  const togglePanelMember = (memberId) => {
    const currentIds = Array.isArray(scheduleForm?.interviewerIds)
      ? scheduleForm?.interviewerIds
      : [];
    const isAlreadySelected = currentIds.includes(memberId);

    if (!isAlreadySelected && currentIds.length >= 4) {
      setScheduleErrors((prev) => ({
        ...prev,
        interviewerIds: "Maximum 4 panel members allowed",
      }));
      return;
    }
    const updatedIds = isAlreadySelected
      ? currentIds.filter((id) => id !== memberId)
      : [...currentIds, memberId];

    handleScheduleInputChange("interviewerIds", updatedIds);
  };

  const computedDateTime = useMemo(() => {
    if (
      !scheduleForm.interviewDate ||
      !scheduleForm.startTime ||
      !scheduleForm.endTime
    ) {
      return { startDateTime: "", endDateTime: "" };
    }
    const start = new Date(
      `${scheduleForm.interviewDate}T${scheduleForm.startTime}`,
    );
    const end = new Date(
      `${scheduleForm.interviewDate}T${scheduleForm.endTime}`,
    );
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return { startDateTime: "", endDateTime: "" };
    }
    if (end.getTime() <= start.getTime()) {
      end.setDate(end.getDate() + 1);
    }
    const endDate = [
      end.getFullYear(),
      String(end.getMonth() + 1).padStart(2, "0"),
      String(end.getDate()).padStart(2, "0"),
    ].join("-");

    return {
      startDateTime: `${scheduleForm.interviewDate}T${scheduleForm.startTime}:00`,
      endDateTime: `${endDate}T${scheduleForm.endTime}:00`,
    };
  }, [
    scheduleForm.interviewDate,
    scheduleForm.startTime,
    scheduleForm.endTime,
  ]);

  const validateScheduleForm = () => {
    const errors = {};
    if (!scheduleForm.roundName.trim()) {
      errors.roundName = "Round name is required";
    }
    if (
      !Array.isArray(scheduleForm.interviewerIds) ||
      !scheduleForm.interviewerIds.length
    ) {
      errors.interviewerIds = "Please select at least one panel member";
    }
    const isMoreThanFourMembers =
      Array.isArray(scheduleForm?.interviewerIds) &&
      scheduleForm?.interviewerIds.length > 4;

    if (isMoreThanFourMembers) {
      errors.interviewerIds = "Maximum 4 panel members allowed";
    }
    if (!scheduleForm.interviewDate) {
      errors.interviewDate = "Interview date is required";
    }
    if (!scheduleForm.startTime) {
      errors.startTime = "Start time is required";
    }
    if (!scheduleForm.endTime) {
      errors.endTime = "End time is required";
    }
    if (!scheduleForm.durationMinutes) {
      errors.durationMinutes = "Duration is required";
    }
    if (!scheduleForm.timezone) {
      errors.timezone = "Timezone is required";
    }
    if (!computedDateTime.startDateTime || !computedDateTime.endDateTime) {
      errors.startTime = "Please provide valid interview timing";
    }
    if (scheduleType === "faceToFace" && !scheduleForm.location.trim()) {
      errors.location = "Location is required";
    }
    if (!scheduleForm.emailSubject.trim()) {
      errors.emailSubject = "Email subject is required";
    }
    if (!scheduleForm.emailBody.trim()) {
      errors.emailBody = "Email body is required";
    }
    if (!selectedJobId) {
      errors.selectedJobId = "Please select a job";
    }
    setScheduleErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const buildFaceToFaceEmailBody = (jobDescription = "") => {
    return `${scheduleForm.emailBody}

Location: ${scheduleForm.location}
Date: ${scheduleForm.interviewDate}
Start Time: ${scheduleForm.startTime}
End Time: ${scheduleForm.endTime}
Duration: ${scheduleForm.durationMinutes} minutes
Timezone: ${scheduleForm.timezone}
Meeting Platform: ${scheduleForm?.meetingPlatform}

${
  jobDescription
    ? `

Job Description:
${jobDescription}
`
    : ""
}
`;
  };

  const handleConvertToEmployee = async () => {
    if (!candidate?.id) {
      showNotice("Candidate details are missing", "error");
      return;
    }
    try {
      const response = await apiRequest(`/onboarding/hr/candidate/${candidate.id}/convert-to-employee`, {
        method: "POST",
        body: JSON.stringify({
          candidate_id: candidate.id,
          joining_date: candidate.candidateJoiningDate,
        }),
      });
      showNotice("Candidate converted to employee successfully", "success");
      // Refresh candidate data
      const updatedCandidate = await getCandidateById(candidate.id);
      setCandidate(updatedCandidate);
    } catch (error) {
      showNotice("Failed to convert candidate to employee: " + error.message, "error");
    }
  };

  const handleScheduleInterview = async () => {
    if (!candidate?.id) {
      showNotice("Candidate details are missing", "error");
      return;
    }
    if (!validateScheduleForm()) {
      return;
    }
    if (!candidate?.email) {
      showNotice("Candidate email is missing", "error");
      return;
    }
    try {
      setScheduling(true);
      let selectedApplication = null;
      const candidateId =
        candidate?.candidate_id || candidate?.id || candidate?._id || null;
      const applicationRes = await getCandidateApplications(candidateId);
      const applications = applicationRes?.applications ?? [];
      selectedApplication =
        applications?.find?.(
          (application) =>
            String(application?.job_id) === String(selectedJobId),
        ) ?? null;
      const panelRes = await createInterviewPanel({
        candidateId: candidate.id,
        roundName: scheduleForm.roundName.trim(),
        jobId: selectedApplication?.job_id,
      });
      const panelId = panelRes?.id;
      if (!panelId) {
        throw new Error("Panel created but panel ID was not returned");
      }
      await Promise.all(
        scheduleForm.interviewerIds.map((interviewerId) =>
          assignPanelMember({
            panelId,
            interviewerId,
          }),
        ),
      );

      const interviewRes = await createInterview({
        panelId,
        candidateId: candidate.id,
        startTime: computedDateTime.startDateTime,
        endTime: computedDateTime.endDateTime,
        meetingLink: "",
        outlookEventId: "",
        status: "Scheduled",
      });

      const interviewId = interviewRes?.id;
      if (!interviewId) {
        throw new Error("Interview created but interview ID was not returned");
      }
      await updateCandidateStatus(candidate.id, {
        pipeline_status: "Interview",
      });
      const updatedStatusRes = await getCandidateStatus(candidate.id);
      setStatusData(updatedStatusRes);
      const performedBy =
        localStorage?.getItem?.("hrms_user_name") || "HR User";
      await createCandidateHistoryEvent(candidate?.id, {
        event_type: HISTORY_EVENT_TYPES.INTERVIEW_SCHEDULED,
        note: `${scheduleForm?.roundName?.trim?.() || "Interview"} scheduled for ${scheduleForm?.interviewDate || "-"} from ${scheduleForm?.startTime || "-"} to ${scheduleForm?.endTime || "-"} (${scheduleType || "online"}).`,
        interview_id: interviewId,
        performed_by_name: performedBy,
        event_at: computedDateTime?.startDateTime,
      });
      let jobDescription = "";
      let formattedJD = "<p>Not Available</p>";
      try {
        const candidateId =
          candidate?.candidate_id || candidate?.id || candidate?._id || null;
        const applicationRes = await getCandidateApplications(candidateId);
        const applications = applicationRes?.applications || [];
        selectedApplication =
          applications?.find?.(
            (application) =>
              String(application?.job_id) === String(selectedJobId),
          ) ?? null;
        if (!selectedApplication) {
          showNotice("No application found for candidate", "error");
        }
        if (selectedApplication?.job_id) {
          const activeJobsRes = await getActiveJobs();
          const matchedJob =
            activeJobsRes?.jobs?.find?.(
              (job) =>
                String(job?.job_id) === String(selectedApplication?.job_id),
            ) || null;
          jobDescription =
            matchedJob?.job_description || matchedJob?.description || "";
          if (jobDescription?.trim()) {
            formattedJD = renderToStaticMarkup(
              <ReactMarkdown>{jobDescription}</ReactMarkdown>,
            );
          }
        }
      } catch (error) {
        console.error("Failed to fetch candidate applications", error);
      }
      const resumeLink = await getCandidateResumeLink();
      if (scheduleType === "online") {
        await sendInterviewInvite({
          interviewId,
          extraNotes: `
<p>${scheduleForm?.extraNotes?.trim?.() || ""}</p>
<hr />
<h3 style="margin-bottom: 12px;">
  Job Description
</h3>

${formattedJD}
`,
          timezone: scheduleForm.timezone,
          createTeamsEvent: scheduleForm.meetingPlatform === "Microsoft Teams",
        });
        await sendPanelInterviewBriefEmail({
          resumeLink,
          selectedApplication,
        });
      } else {
        const ccEmails =
          scheduleForm?.ccEmails
            ?.split(",")
            ?.map((email) => email.trim())
            ?.filter(Boolean) ?? [];

        await sendPlainEmail({
          toEmail: candidate.candidate_email,
          subject: scheduleForm.emailSubject.trim(),
          bodyContent: buildFaceToFaceEmailBody(jobDescription),
          isHtml: false,
          ccEmails,
        });
        await sendPanelInterviewBriefEmail({
          resumeLink,
          selectedApplication,
        });
      }

      showNotice(
        scheduleType === "online"
          ? "Online interview scheduled successfully"
          : "Face-to-face interview scheduled successfully",
      );
      await onRefreshCandidates?.();
      setScheduling(false);
      closeScheduleModal();
      setActiveTab("interview");
    } catch (err) {
      console.error("Failed to complete interview scheduling flow", err);
      showNotice(err?.message || "Failed to schedule interview", "error", 5000);
      setScheduling(false);
    }
  };
  const fullName =
    candidate?.name ||
    `${candidate?.first_name || ""} ${candidate?.last_name || ""}`.trim() ||
    "Candidate";
  const getCandidateResumeLink = async () => {
    if (!candidate?.id) return "";

    try {
      const docsRes = await getCandidateDocuments(candidate.id);
      const documents = Array.isArray(docsRes?.documents)
        ? docsRes?.documents
        : [];

      const resumeDoc = documents.find(
        (doc) =>
          String(doc?.document_type ?? "").toLowerCase() === "resume" &&
          !doc?.is_deleted &&
          doc?.sharepoint_url,
      );
      return resumeDoc?.sharepoint_url || "";
    } catch (err) {
      console.error("Failed to fetch candidate resume link", err);
      return "";
    }
  };

  const getSelectedPanelEmails = () => {
    return selectedPanelMembers
      .map((member) => {
        const matchedUser = users?.find(
          (user) => String(user?.user_id) === String(member?.value),
        );
        return matchedUser?.user_email || "";
      })
      .map((email) => email.trim())
      .filter(Boolean);
  };
  const sendPanelInterviewBriefEmail = async ({
    resumeLink,
    selectedApplication,
  }) => {
    const panelEmails = getSelectedPanelEmails();
    if (!panelEmails.length) {
      showNotice(
        "Panel email was skipped because panel member emails are missing.",
        "error",
        5000,
      );
      return;
    }
    const interviewTime = `${scheduleForm?.interviewDate || "-"} ${scheduleForm?.startTime || "-"} - ${scheduleForm?.endTime || "-"}`;
    const resumeSection = resumeLink
      ? `<p><strong>Resume:</strong> <a href="${resumeLink}" target="_blank" rel="noreferrer">View Resume</a></p>`
      : `<p><strong>Resume:</strong> Not uploaded / not available</p>`;

    const bodyContent = `
    <p>Hi Team,</p>
    <p>Please find the candidate details for the upcoming interview.</p>

    <p>
      <strong>Candidate Name:</strong> ${fullName}<br/>
  <strong>Role:</strong> ${
    selectedApplication?.job_title || candidate?.jobTitle || "-"
  }<br/>
      <strong>Round:</strong> ${scheduleForm.roundName || "-"}<br/>
      <strong>Interview Time:</strong> ${interviewTime}<br/>
      <strong>Timezone:</strong> ${scheduleForm.timezone || "-"}
    </p>

    ${
      scheduleForm.extraNotes?.trim()
        ? `<p><strong>Recruiter Notes:</strong><br/>${scheduleForm.extraNotes.trim()}</p>`
        : ""
    }
    ${resumeSection}
    <p>Please review the candidate details before the interview and submit feedback after completion.</p>
    <p>Thanks,<br/>HR Team</p>
  `;
    await sendPlainEmail({
      toEmail: panelEmails[0],
      subject: `Interview Brief - ${fullName} - ${scheduleForm.roundName}`,
      bodyContent,
      isHtml: true,
      ccEmails: panelEmails.slice(1),
    });
  };

  const openOfferModal = () => {
    setPreonboardingModal(true);
  };

  const handleSaveNote = async () => {
    if (!noteText?.trim()) {
      showNotice("Please enter note content", "error");

      return;
    }
    try {
      setSavingNote(true);

      await createCandidateNote(candidate?.id, {
        content: noteText?.trim(),
        category: "General",
      });
      const updatedNotes = await getCandidateNotes(candidate?.id);
      setNotes(updatedNotes?.notes || []);
      setNoteText("");
      setShowNoteModal(false);
      showNotice("Note added successfully", "success");
    } catch (error) {
      console.error("Failed to save candidate note", error);
      showNotice("Failed to save note", "error");
    } finally {
      setSavingNote(false);
    }
  };

  const handleAddNote = async () => {
    if (!noteInput?.trim()) {
      return;
    }
    try {
      setSavingNote(true);
      await createCandidateNote(candidate?.id, {
        content: noteInput?.trim(),
        category: "General",
      });
      const updatedNotes = await getCandidateNotes(candidate?.id);
      setNotes(updatedNotes?.notes || []);
      setNoteInput("");
      toast.success("Note added successfully");
    } catch (error) {
      console.error("Failed to save candidate note", error);
      toast.error("Failed to save note");
    } finally {
      setSavingNote(false);
    }
  };

  const handleArchiveToggle = async () => {
    try {
      const currentStatus = candidate?.accountStatus || statusData?.status;
      const nextStatus = currentStatus === "Inactive" ? "Active" : "Inactive";
      const response = await updateCandidateStatus(candidate?.id, {
        status: nextStatus,
      });
      if (response?.status === "success") {
        setStatusData((prev) => ({
          ...prev,
          status: nextStatus,
        }));
        candidate.accountStatus = nextStatus;
        await onRefreshCandidates?.();
        setUpdatedStatus(Date.now());
        showNotice(
          nextStatus === "Inactive"
            ? "Candidate archived successfully"
            : "Candidate unarchived successfully",
          "success",
        );
      }
    } catch (error) {
      console.error("Failed to update candidate status", error);
      showNotice("Failed to update candidate status", "error");
    }
  };

  const handlePreOnboardingAction = async (record, action) => {
    try {
      const res = await managerReviewApprove(record, action);
      if (res?.status === "success") {
        const updatedCandidate = res?.data;
        if (action === "Approve") {
          const emailSend = await sendPlainEmail({
            toEmail: candidate?.email,
            subject: "Pre-Onboarding Task",
            bodyContent: getEmailBodyHTML(candidate?.name),
            isHtml: false,
          });
          if (emailSend?.status === "success") {
            toast.success(
              `Candidate ${candidate?.name} approved for Pre-Onboarding`,
            );
          }
        } else {
          toast.success(`Candidate ${candidate?.name} has been rejected`);
        }
      }
    } catch (err) {
      toast.error(
        action === "Approve"
          ? "Candidate already moved to Pre-Onboarding"
          : "Failed to reject candidate",
      );
    }
  };

  const handleDocumentsUpdate = (docs) => {
    setCandidateDocCount(docs);
  };

  return (
    <>
      <div className="grid gap-5">
        {notice && (
          <div
            className={`rounded-xl border px-4 py-3 text-sm font-medium ${
              noticeType === "error"
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-green-200 bg-green-50 text-green-700"
            }`}
          >
            {notice}
          </div>
        )}

        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm">
          <div className="px-6 py-5 flex flex-col xl:flex-row xl:items-center xl:justify-between gap-6 overflow-visible">
            <div className="flex items-start gap-4 min-w-0">
              <div className="w-14 h-14 rounded-full bg-orange-500 text-white flex items-center justify-center text-lg font-semibold shrink-0">
                {(fullName || "C")
                  .split(" ")
                  .map((w) => w[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-lg font-semibold text-gray-900 truncate">
                    {fullName}
                  </h2>
                  {candidate?.is_guidewire_candidate && (
                    <span
                      title="Guidewire candidate — our bread and butter, nurture for conversion"
                      className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700 shrink-0"
                    >
                      Guidewire
                    </span>
                  )}
                  {statusData?.status && (
                    <StatusBadge type="account" value={statusData.status} />
                  )}
                  {preonboardingModal && (
                    <PreonboardingModal
                      fullName={fullName}
                      candidate={candidate}
                      onClose={() => setPreonboardingModal(false)}
                      status={radioStatus}
                      offerId={offerId}
                      onSuccess={(data) => {
                        setOfferId(data?.id);
                        setUpdatedStatus(data);
                      }}
                    />
                  )}

                  {previousOfferModalState ? (
                    <PreviousOfferModal
                      onClose={() => setPreviousOfferModalState(false)}
                      previousOffer={previousOffer}
                    />
                  ) : null}
                  {statusData?.pipeline_status && (
                    <StatusDropdown statusData={statusData} />
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-gray-500">
                  {candidate?.email ? (
                    <a
                      href={`mailto:${candidate.candidate_email}`}
                      className="truncate text-blue-600 hover:underline"
                    >
                      {candidate.candidate_email}
                    </a>
                  ) : (
                    <span>-</span>
                  )}
                  {candidate?.phone ? (
                    <a
                      href={`tel:${candidate.candidate_mobile}`}
                      className="hover:underline"
                    >
                      {candidate.candidate_mobile}
                    </a>
                  ) : (
                    <span>-</span>
                  )}
                  <span className="truncate">{candidate?.jobTitle || "-"}</span>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-start xl:justify-end gap-2 overflow-visible">
              <Button variant="ghost" onClick={onBack}>
                Back
              </Button>
              {previousOffer.length > 0 ? (
                <Button
                  variant="secondary"
                  onClick={() => setPreviousOfferModalState(true)}
                  className="h-[46px] border-blue-100 bg-blue-50 text-blue-700 transition-all duration-200 hover:border-blue-200 hover:bg-blue-100"
                >
                  Show Previous Offers
                </Button>
              ) : null}
              {currentRole === "HIRING MANAGER" &&
              candidate?.pipelineStatus == "Pre-onboarding-Approval" ? (
                <AcceptButton
                  disabled={isApproved}
                  onClick={() => handlePreOnboardingAction(apiState, "Approve")}
                >
                  {isApproved ? "Approved" : "Accept"}
                </AcceptButton>
              ) : null}
              {(currentRole === "HR Manager" ||
                currentRole === "HR Operations") &&
                candidateDocCount?.total_documents > 0 &&
                candidateDocCount?.verified_count ===
                  candidateDocCount?.total_documents && (
                  <Button
                    variant="secondary"
                    onClick={openOfferModal}
                    className="h-[46px] border-blue-100 bg-blue-50 text-blue-700 transition-all duration-200 hover:border-blue-200 hover:bg-blue-100"
                  >
                    Create Offer
                  </Button>
                )}

              {(currentRole === "HR Manager" ||
                currentRole === "HR Operations") &&
                candidate?.pipelineStatus === "Offer" &&
                candidate?.candidateJoiningDate &&
                new Date(candidate?.candidateJoiningDate) <= new Date() && (
                  <Button
                    variant="secondary"
                    onClick={() => handleConvertToEmployee()}
                    className="h-[46px] border-green-100 bg-green-50 text-green-700 transition-all duration-200 hover:border-green-200 hover:bg-green-100"
                  >
                    Convert to Employee
                  </Button>
                )}

              {canShowFullActions && (
                <>
                  <Button
                    variant="secondary"
                    onClick={handleArchiveToggle}
                    className={`h-[46px] transition-all duration-200 ${
                      (candidate?.accountStatus || statusData?.status) ===
                      "Inactive"
                        ? "border-green-100 bg-green-50 text-green-700 hover:border-green-200 hover:bg-green-100"
                        : "border-red-100 bg-red-50 text-red-700 hover:border-red-200 hover:bg-red-100"
                    }`}
                  >
                    {(candidate?.accountStatus || statusData?.status) ===
                    "Inactive"
                      ? "Unarchive"
                      : "Archive"}
                  </Button>
                  {candidateJobs?.length > 0 && (
                    <div className="relative" ref={scheduleMenuRef}>
                      <Button
                        onClick={() => setShowScheduleMenu((prev) => !prev)}
                      >
                        Schedule
                      </Button>

                    {showScheduleMenu && (
                      <div className="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden">
                        <button
                          type="button"
                          className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50"
                          onClick={() => openScheduleModal("online")}
                        >
                          Online Interview
                        </button>
                        <button
                          type="button"
                          className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50"
                          onClick={() => openScheduleModal("faceToFace")}
                        >
                          Face to Face Interview
                        </button>
                      </div>
                    )}
                    </div>
                  )}

                  <button
                    type="button"
                    className="p-2 rounded-xl border hover:bg-gray-100 cursor-pointer"
                    title="Send Email"
                    onClick={() => {
                      const email = candidate?.email?.trim();
                      if (!email) {
                        showNotice("Candidate email is not available", "error");
                        return;
                      }
                      const subject = encodeURIComponent(
                        "Regarding your application",
                      );
                      const body = encodeURIComponent(`Hi ${fullName},\n\n`);
                      const to = encodeURIComponent(email);
                      const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${to}&su=${subject}&body=${body}`;
                      const mailtoUrl = `mailto:${to}?subject=${subject}&body=${body}`;
                      const openedWindow = window.open(
                        gmailUrl,
                        "_blank",
                        "noopener,noreferrer",
                      );
                      if (!openedWindow) {
                        window.location.href = mailtoUrl;
                      }
                    }}
                  >
                    <Mail className="w-5 h-5 text-gray-600" />
                  </button>
                  <a
                    href={candidate?.phone ? `tel:${candidate.candidate_mobile}` : undefined}
                    className={`p-2 rounded-xl border border-gray-200 transition ${
                      candidate?.phone
                        ? "hover:bg-gray-100"
                        : "opacity-50 pointer-events-none"
                    }`}
                    title={`Call ${candidate?.name || "candidate"}`}
                    aria-disabled={!candidate?.phone}
                  >
                    <Phone className="w-5 h-5 text-gray-600" />
                  </a>
                  <button
                    type="button"
                    className="p-2 rounded-xl border border-gray-200 hover:bg-gray-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
                    title={`Message ${candidate?.name || "candidate"} on WhatsApp`}
                    disabled={!candidate?.phone}
                    onClick={() => {
                      if (!candidate?.phone) return;
                      const cleanedPhone = candidate.candidate_mobile.replace(/\D/g, "");
                      if (!cleanedPhone) {
                        showNotice("Invalid phone number", "error");
                        return;
                      }
                      window.open(`https://wa.me/${cleanedPhone}`, "_blank");
                    }}
                  >
                    <MessageCircle className="w-5 h-5 text-green-600" />
                  </button>
                  <Button onClick={() => setEditModalOpen(true)}>Edit</Button>
                  <Button
                    disabled={isChecklistAssigned}
                    onClick={() => setShowAssignModal(true)}
                  >
                    Submit Job
                  </Button>
                  <div className="relative" ref={notesMenuRef}>
                    <button
                      type="button"
                      onClick={() => setShowNotesMenu((prev) => !prev)}
                      className="h-[46px] w-[46px] rounded-xl border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition flex items-center justify-center text-xl"
                    >
                      ⋯
                    </button>

                    {showNotesMenu && (
                      <div className="absolute top-full -left-24 mt-2 w-44 rounded-xl border border-gray-200 bg-white shadow-xl  z-50 overflow-hidden">
                        <button
                          type="button"
                          onClick={() => {
                            setShowNotesMenu(false);
                            setShowNoteModal(true);
                          }}
                          className="w-full px-4 py-3 text-sm text-left text-gray-700 hover:bg-gray-50"
                        >
                          Add Note
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {!limitedMode && (
          <CandidateJourney candidateId={candidate?.id} onNavigateTab={setActiveTab} />
        )}

        <div className="border-b">
          <div className="flex flex-wrap gap-2">
            {candidateTabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2.5 text-sm font-medium rounded-t-xl transition ${
                  activeTab === tab
                    ? "bg-white border border-b-0 border-gray-300 text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-800 hover:bg-gray-50"
                }`}
              >
                {tab.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5">
          <div className="p-5 bg-white border rounded-2xl shadow-sm">
            {activeTab === "profile" && !limitedMode && (
              <ProfileTabEditable candidateId={candidate?.id} candidate={candidate} onRefresh={onUpdateCandidate} />
            )}

            {activeTab === "feedback" && limitedMode && (
              <FeedbackTab
                candidateId={candidate?.id}
                limitedMode={limitedMode}
                limitedInterview={candidate?.limitedInterview || null}
              />
            )}

            {activeTab === "documents" && !limitedMode && (
              <DocumentsTab
                candidateId={candidate?.id}
                candidateEmail={candidate?.email || candidate?.candidate_email}
                candidateName={candidate?.name || candidate?.candidate_name}
                onDocumentsUpdate={handleDocumentsUpdate}
              />
            )}

            {activeTab === "tasks" && !limitedMode && (
              <TasksTab candidateId={candidate?.id} />
            )}
            {activeTab === "messages" && !limitedMode && (
              <MessagesTab candidateId={candidate?.id} />
            )}
            {activeTab === "interview" && !limitedMode && (
              <InterviewsTab
                candidateId={candidate?.id}
                onScheduleInterview={() => setShowScheduleModal(true)}
              />
            )}
            {activeTab === "intelligence" && !limitedMode && (
              <IntelligenceTab candidateId={candidate?.id} currentRole={currentRole} />
            )}
            {activeTab === "history" && !limitedMode && (
              <HistoryTab
                candidateId={candidate?.id || candidate?.candidate_id}
              />
            )}
          </div>
          {!limitedMode && (
            <div className="space-y-5">
              {/* Users & BU Details Panel */}
              <UsersBUDetailsPanel
                candidate={candidate}
                onUpdate={async (updates) => {
                  if (onUpdateCandidate) {
                    await onUpdateCandidate({ ...candidate, ...updates });
                  }
                }}
              />

              {/* Notes Panel */}
              <div className="bg-white border rounded-2xl shadow-sm h-fit flex flex-col">
                <div className="border-b px-5 py-4">
                  <h3 className="text-sm font-semibold text-gray-900">Notes</h3>
                </div>

              {/* Note Input */}
              <div className="border-b px-5 py-3">
                <textarea
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Add a note..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs resize-none"
                  rows={2}
                />
                <div className="flex justify-end mt-2">
                  <button
                    onClick={handleAddNote}
                    disabled={!noteInput.trim()}
                    className="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition font-medium"
                  >
                    Add Note
                  </button>
                </div>
              </div>

              <div className="max-h-[500px] overflow-y-auto flex-1">
                {loadingNotes ? (
                  <div className="p-5 text-sm text-gray-500">
                    Loading notes...
                  </div>
                ) : notes?.length ? (
                  <div className="divide-y divide-gray-100">
                    {notes.map((note) => (
                      <div key={note?.id} className="p-5">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-medium text-gray-900">
                            {note?.created_by_name || "HR User"}
                          </p>

                          <span className="text-xs text-gray-400">
                            {note?.created_at
                              ? new Date(note.created_at).toLocaleDateString()
                              : ""}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-gray-600 whitespace-pre-wrap break-words">
                          {note?.content || "-"}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-5 text-sm text-gray-500">
                    No notes available
                  </div>
                )}
              </div>
            </div>
            </div>
          )}
        </div>
        {editModalOpen && (
          <CandidateEditModal
            candidate={candidate}
            onClose={() => setEditModalOpen(false)}
            onUpdateCandidate={onUpdateCandidate}
            onRefreshCandidates={onRefreshCandidates}
          />
        )}
        {showNoteModal && (
          <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
            <div className="bg-white w-full max-w-2xl rounded-3xl shadow-2xl border border-gray-200 overflow-hidden">
              <div className="border-b px-6 py-5 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    Add Note for{" "}
                    {candidate?.name ||
                      candidate?.candidate_name ||
                      "Candidate"}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (savingNote) return;

                    setShowNoteModal(false);
                  }}
                  className="text-2xl text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>
              <div className="px-6 py-5 space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Note
                  </label>
                  <textarea
                    rows={7}
                    value={noteText}
                    onChange={(event) =>
                      setNoteText(event?.target?.value || "")
                    }
                    placeholder="Write a note here..."
                    className="w-full rounded-2xl border border-gray-300 px-4 py-3 text-sm outline-none resize-none focus:border-gray-400"
                  />
                </div>
              </div>
              <div className="border-t px-6 py-4 flex items-center justify-end gap-3">
                <Button
                  variant="ghost"
                  onClick={() => {
                    if (savingNote) return;

                    setShowNoteModal(false);
                  }}
                >
                  Cancel
                </Button>
                <Button onClick={handleSaveNote} disabled={savingNote}>
                  {savingNote ? "Saving..." : "Save Note"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {showAssignModal && (
          <CandidateAssignJobModal
            onClose={() => setShowAssignModal(false)}
            candidateDetails={candidate}
          />
        )}
      </div>

      {showScheduleModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
          <div className="bg-white w-full max-w-6xl rounded-3xl shadow-2xl overflow-hidden border border-gray-200">
            <div className="border-b px-8 py-6 flex items-start justify-between">
              <div>
                <h2 className="text-2xl font-semibold text-gray-900">
                  {scheduleType === "online"
                    ? `Schedule Online Interview with ${
                        candidate?.name || "Candidate"
                      }`
                    : `Schedule Face to Face Interview with ${
                        candidate?.name || "Candidate"
                      }`}
                </h2>
                <p className="text-sm text-gray-500 mt-1">Schedule Interview</p>
              </div>

              <button
                type="button"
                onClick={closeScheduleModal}
                disabled={scheduling}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="px-8 py-6 max-h-[78vh] overflow-y-auto">
              <div className="grid grid-cols-1 gap-8">
                <div className="space-y-8">
                  <CardBlock
                    title="Interview Setup"
                    subtitle="Select panel members and define interview timing."
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <SelectField
                        label="Interview Type"
                        value={scheduleType}
                        onChange={(e) => setScheduleType(e.target.value)}
                      >
                        <option value="inperson">Face to Face Interview</option>
                        <option value="online">Online Interview (Microsoft Teams)</option>
                      </SelectField>
                      <FormField
                        label="Candidate ID"
                        value={candidate?.id || ""}
                        readOnly
                      />
                      <SelectField
                        label="Applied Job"
                        value={selectedJobId}
                        onChange={(e) => setSelectedJobId(e?.target?.value)}
                        error={scheduleErrors?.selectedJobId}
                        disabled={loadingCandidateJobs}
                      >
                        <option value="">
                          {loadingCandidateJobs
                            ? "Loading jobs..."
                            : "Select Job"}
                        </option>
                        {candidateJobs?.map((job) => (
                          <option key={job?.job_id} value={job?.job_id}>
                            {job?.job_title ?? `Job ${job?.job_id}`}
                          </option>
                        ))}
                      </SelectField>
                      <SelectField
                        label="Round Name"
                        value={scheduleForm.roundName || ""}
                        onChange={(e) =>
                          handleScheduleInputChange("roundName", e.target.value)
                        }
                        error={scheduleErrors.roundName}
                      >
                        <option value="">Select Round Name</option>

                        {roundNameOptions?.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </SelectField>

                      <div
                        className="md:col-span-2"
                        ref={panelMemberDropdownRef}
                      >
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          Panel Members
                        </label>
                        <button
                          type="button"
                          onClick={() =>
                            !loadingUsers &&
                            setShowPanelMemberDropdown((prev) => !prev)
                          }
                          className={`w-full min-h-[46px] rounded-xl border px-3 py-2.5 text-sm text-left transition ${
                            scheduleErrors.interviewerIds
                              ? "border-red-300"
                              : "border-gray-300"
                          } ${
                            loadingUsers
                              ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                              : "bg-white text-gray-700"
                          }`}
                          disabled={loadingUsers}
                        >
                          {selectedPanelMembers.length > 0
                            ? `${selectedPanelMembers.length} panel member(s) selected`
                            : loadingUsers
                              ? "Loading panel members..."
                              : "Select panel members"}
                        </button>
                        {showPanelMemberDropdown && !loadingUsers && (
                          <div className="mt-2 rounded-xl border border-gray-200 bg-white shadow-lg max-h-72 overflow-auto p-2">
                            <div className="px-2 pb-2">
                              <input
                                type="text"
                                placeholder="Search panel members..."
                                value={panelSearch}
                                onChange={(e) => setPanelSearch(e.target.value)}
                                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-gray-400"
                              />
                            </div>
                            {filteredPanelMembers.length > 0 ? (
                              filteredPanelMembers.map((option) => {
                                const isChecked =
                                  scheduleForm.interviewerIds.includes(
                                    option.value,
                                  );

                                return (
                                  <label
                                    key={option.value}
                                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isChecked}
                                      onChange={() =>
                                        togglePanelMember(option.value)
                                      }
                                      className="rounded"
                                    />
                                    <span className="text-sm text-gray-700">
                                      {option.label}
                                    </span>
                                  </label>
                                );
                              })
                            ) : (
                              <div className="px-3 py-2 text-sm text-gray-500">
                                No panel members found
                              </div>
                            )}
                          </div>
                        )}

                        {selectedPanelMembers.length > 0 && (
                          <div className="mt-3">
                            <div className="text-sm font-medium text-gray-700 mb-2">
                              Selected Panel Members
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {selectedPanelMembers.map((member) => (
                                <div
                                  key={member.value}
                                  className="inline-flex items-center gap-2 rounded-full bg-blue-50 text-blue-700 border border-blue-100 px-3 py-1.5 text-sm font-medium"
                                >
                                  <span>{member.label}</span>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      togglePanelMember(member.value)
                                    }
                                    className="text-blue-500 hover:text-blue-700"
                                  >
                                    ×
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {scheduleErrors.interviewerIds ? (
                          <p className="text-xs text-red-500 mt-1">
                            {scheduleErrors.interviewerIds}
                          </p>
                        ) : null}
                      </div>
                      <FormField
                        label="Interview Date"
                        type="date"
                        value={scheduleForm.interviewDate}
                        onChange={(e) =>
                          handleScheduleInputChange(
                            "interviewDate",
                            e.target.value,
                          )
                        }
                        error={scheduleErrors.interviewDate}
                      />
                      <SelectField
                        label="Meeting Platform"
                        value={scheduleForm.meetingPlatform}
                        onChange={(e) =>
                          handleScheduleInputChange(
                            "meetingPlatform",
                            e.target.value,
                          )
                        }
                      >
                        {meetingPlatformOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </SelectField>

                      <SelectField
                        label="Timezone"
                        value={scheduleForm.timezone}
                        onChange={(e) =>
                          handleScheduleInputChange("timezone", e.target.value)
                        }
                        error={scheduleErrors.timezone}
                      >
                        {timezoneOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </SelectField>
                      <SelectField
                        label="Duration"
                        value={scheduleForm.durationMinutes}
                        onChange={(e) =>
                          handleScheduleInputChange(
                            "durationMinutes",
                            e.target.value,
                          )
                        }
                        error={scheduleErrors.durationMinutes}
                      >
                        {[30, 45, 60, 90, 120].map((minutes) => (
                          <option key={minutes} value={String(minutes)}>
                            {formatDurationLabel(minutes)}
                          </option>
                        ))}
                      </SelectField>
                      <FormField
                        label="Start Time"
                        type="time"
                        value={scheduleForm.startTime}
                        onChange={(e) =>
                          handleScheduleInputChange("startTime", e.target.value)
                        }
                        error={scheduleErrors.startTime}
                      />
                      <FormField
                        label="End Time"
                        type="time"
                        value={scheduleForm.endTime}
                        readOnly
                        error={scheduleErrors.endTime}
                      />
                    </div>
                    {scheduleType === "faceToFace" && (
                      <div className="mt-5">
                        <FormField
                          label="Interview Location"
                          placeholder="e.g. BlitzenX Office, 3rd Floor, Hyderabad"
                          value={scheduleForm.location}
                          onChange={(e) =>
                            handleScheduleInputChange(
                              "location",
                              e.target.value,
                            )
                          }
                          error={scheduleErrors.location}
                        />
                      </div>
                    )}
                  </CardBlock>
                  <CardBlock
                    title="Notes"
                    subtitle="Optional notes for current phase."
                  >
                    <TextAreaField
                      label="Additional Notes (optional)"
                      placeholder="Add any useful note here"
                      value={scheduleForm.extraNotes}
                      onChange={(e) =>
                        handleScheduleInputChange("extraNotes", e.target.value)
                      }
                    />
                  </CardBlock>
                </div>
              </div>
            </div>

            <div className="border-t bg-white px-8 py-5 flex items-center justify-end gap-3">
              <Button
                variant="ghost"
                onClick={closeScheduleModal}
                disabled={scheduling}
              >
                Cancel
              </Button>

              <Button onClick={handleScheduleInterview} disabled={scheduling}>
                {scheduling ? "Processing..." : "Schedule Interview"}
              </Button>
            </div>
          </div>
          <ToastContainer position="top-right" autoClose={3000} />
        </div>
      )}
    </>
  );
}
function CardBlock({ title, subtitle, children }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-5">
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        {subtitle ? (
          <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
        ) : null}
      </div>
      {children}
    </div>
  );
}
function Info({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
      <span className="text-xs uppercase tracking-wide text-gray-500">
        {label}
      </span>
      <div className="font-medium text-sm text-gray-900 mt-1">
        {value || "-"}
      </div>
    </div>
  );
}
function StatusBadge({ type, value }) {
  let styles = "bg-gray-100 text-gray-600";
  if (type === "account") {
    if (value === "Active") styles = "bg-green-100 text-green-700";
    if (value === "Inactive") styles = "bg-red-100 text-red-700";
  }
  if (type === "pipeline") {
    if (value === "Applied") styles = "bg-blue-100 text-blue-700";
    if (value === "Interview") styles = "bg-purple-100 text-purple-700";
    if (value === "Hired") styles = "bg-green-200 text-green-800";
  }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${styles}`}>
      {value}
    </span>
  );
}

function FormField({
  label,
  error,
  readOnly = false,
  type = "text",
  value,
  onChange,
  placeholder,
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        readOnly={readOnly}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition ${
          readOnly
            ? "bg-gray-50 text-gray-700 border-gray-200 cursor-text"
            : error
              ? "border-red-300 focus:border-red-400"
              : "border-gray-300 focus:border-gray-400"
        }`}
      />
      {error ? <p className="text-xs text-red-500 mt-1">{error}</p> : null}
    </div>
  );
}

function SelectField({
  label,
  error,
  value,
  onChange,
  children,
  disabled = false,
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <select
        value={value}
        onChange={onChange}
        disabled={disabled}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition bg-white ${
          disabled
            ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
            : error
              ? "border-red-300 focus:border-red-400"
              : "border-gray-300 focus:border-gray-400"
        }`}
      >
        {children}
      </select>
      {error ? <p className="text-xs text-red-500 mt-1">{error}</p> : null}
    </div>
  );
}
function TextAreaField({
  label,
  error,
  value,
  onChange,
  placeholder,
  readOnly = false,
  rows = 6,
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <textarea
        rows={rows}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        readOnly={readOnly}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition resize-none ${
          readOnly
            ? "bg-gray-50 text-gray-700 border-gray-200 cursor-text"
            : error
              ? "border-red-300 focus:border-red-400"
              : "border-gray-300 focus:border-gray-400"
        }`}
      />
      {error ? <p className="text-xs text-red-500 mt-1">{error}</p> : null}
    </div>
  );
}
function formatDurationLabel(value) {
  const map = {
    30: "30 min",
    45: "45 min",
    60: "1 hour",
    90: "1.5 hour",
    120: "2 hour",
  };
  return map[value] || `${value} min`;
}
