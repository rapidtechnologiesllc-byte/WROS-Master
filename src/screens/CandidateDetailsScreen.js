import { useEffect, useMemo, useRef, useState } from "react";
import { Card, Button } from "../components/ui";
import ProfileTab from "./tabs/ProfileTab";
import FeedbackTab from "./tabs/FeedbackTab";
import DocumentsTab from "./tabs/DocumentsTab";
import TasksTab from "./tabs/TasksTab";
import ActivityTab from "./tabs/ActivityTab";
import CandidateEditModal from "./CandidateEditModal";

import { getCandidateStatus } from "../services/api/candidateStatus";
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
import { getAllUsers } from "../services/api/users";
import {
  getOnlineInterviewEmailTemplate,
  getFaceToFaceInterviewEmailTemplate,
} from "../utils/interviewEmailTemplates";
import CandidateAssignJobModal from "./CandidateAssignJobModal";

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

const meetingPlatformOptions = [
  "Microsoft Teams",
  "Google Meet",
  "Zoom",
  "Phone Call",
  "In Person",
  "Other",
];

const emailTemplateOptions = [
  "Online Interview",
  "Face to Face Interview",
  "Custom",
];

export default function CandidateDetailsScreen({ candidate, onBack }) {
  const [activeTab, setActiveTab] = useState("profile");
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

  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleType, setScheduleType] = useState("");
  const [scheduleForm, setScheduleForm] = useState(initialScheduleForm);
  const [scheduleErrors, setScheduleErrors] = useState({});
  const [scheduling, setScheduling] = useState(false);

  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  const [showPanelMemberDropdown, setShowPanelMemberDropdown] = useState(false);
  const [panelSearch, setPanelSearch] = useState("");
  const panelMemberDropdownRef = useRef(null);

  useEffect(() => {
    if (!candidate?.id) return;

    const fetchStatus = async () => {
      try {
        const res = await getCandidateStatus(candidate.id);
        setStatusData(res);
      } catch (err) {
        console.error("Failed to fetch candidate status", err);
      }
    };

    fetchStatus();
  }, [candidate?.id]);

  useEffect(() => {
    if (!candidate?.id) return;

    const checkChecklist = async () => {
      try {
        const res = await getCandidateChecklists(candidate.id);
        setIsChecklistAssigned(Boolean(res && res.length > 0));
      } catch (err) {
        console.error("Failed to check checklist", err);
      }
    };

    checkChecklist();
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

        const userList = Array.isArray(res)
          ? res
          : Array.isArray(res?.users)
            ? res.users
            : Array.isArray(res?.items)
              ? res.items
              : Array.isArray(res?.data)
                ? res.data
                : [];

        setUsers(userList);
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

  const showNotice = (message, type = "success", duration = 4000) => {
    setNotice(message);
    setNoticeType(type);

    window.clearTimeout(window.__candidateDetailsNoticeTimeout);
    window.__candidateDetailsNoticeTimeout = window.setTimeout(() => {
      setNotice("");
    }, duration);
  };

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
        candidateId: candidate.id,
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

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "";
    if (end <= start) return "";

    const diffMinutes = Math.round(
      (end.getTime() - start.getTime()) / (60 * 1000),
    );
    return String(diffMinutes);
  };

  const openScheduleModal = (type) => {
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
    setShowScheduleModal(true);
  };

  const closeScheduleModal = () => {
    if (scheduling) return;
    setShowScheduleModal(false);
    setScheduleType("");
    setScheduleErrors({});
    setPanelSearch("");
    setShowPanelMemberDropdown(false);
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

      if (field === "durationMinutes") {
        updated.endTime = recomputeEndTime(
          updated.interviewDate,
          updated.startTime,
          value,
        );
      }

      if (
        field === "startTime" ||
        field === "endTime" ||
        field === "interviewDate"
      ) {
        const calculatedDuration = recomputeDuration(
          field === "interviewDate" ? value : updated.interviewDate,
          field === "startTime" ? value : updated.startTime,
          field === "endTime" ? value : updated.endTime,
        );

        if (calculatedDuration) {
          updated.durationMinutes = calculatedDuration;
        }
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
    const currentIds = Array.isArray(scheduleForm.interviewerIds)
      ? scheduleForm.interviewerIds
      : [];

    const updatedIds = currentIds.includes(memberId)
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

    return {
      startDateTime: `${scheduleForm.interviewDate}T${scheduleForm.startTime}`,
      endDateTime: `${scheduleForm.interviewDate}T${scheduleForm.endTime}`,
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
    } else if (
      new Date(computedDateTime.endDateTime) <=
      new Date(computedDateTime.startDateTime)
    ) {
      errors.endTime = "End time must be after start time";
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

    setScheduleErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const buildFaceToFaceEmailBody = () => {
    return `${scheduleForm.emailBody}

Location: ${scheduleForm.location}
Date: ${scheduleForm.interviewDate}
Start Time: ${scheduleForm.startTime}
End Time: ${scheduleForm.endTime}
Duration: ${scheduleForm.durationMinutes} minutes
Timezone: ${scheduleForm.timezone}
Meeting Platform: ${scheduleForm.meetingPlatform}`;
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

      const panelRes = await createInterviewPanel({
        candidateId: candidate.id,
        roundName: scheduleForm.roundName.trim(),
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

      if (scheduleType === "online") {
        await sendInterviewInvite({
          interviewId,
          extraNotes: scheduleForm.extraNotes,
          timezone: scheduleForm.timezone,
          createTeamsEvent: scheduleForm.meetingPlatform === "Microsoft Teams",
        });
      } else {
        const ccEmails = scheduleForm.ccEmails
          .split(",")
          .map((email) => email.trim())
          .filter(Boolean);

        await sendPlainEmail({
          toEmail: candidate.email,
          subject: scheduleForm.emailSubject.trim(),
          bodyContent: buildFaceToFaceEmailBody(),
          isHtml: false,
          ccEmails,
        });
      }

      showNotice(
        scheduleType === "online"
          ? "Online interview scheduled successfully"
          : "Face-to-face interview scheduled successfully",
      );

      closeScheduleModal();
      setActiveTab("activity");
    } catch (err) {
      console.error("Failed to complete interview scheduling flow", err);
      showNotice(err?.message || "Failed to schedule interview", "error", 5000);
    } finally {
      setScheduling(false);
    }
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

        <Card
          title={
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-semibold text-base">Candidate Details</span>

              {statusData?.status && (
                <StatusBadge type="account" value={statusData.status} />
              )}

              {statusData?.pipeline_status && (
                <StatusBadge
                  type="pipeline"
                  value={statusData.pipeline_status}
                />
              )}
            </div>
          }
          right={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Button variant="ghost" onClick={onBack}>
                Back
              </Button>

              <div className="relative" ref={scheduleMenuRef}>
                <Button onClick={() => setShowScheduleMenu((prev) => !prev)}>
                  Schedule
                </Button>

                {showScheduleMenu && (
                  <div className="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-xl shadow-lg z-20 overflow-hidden">
                    <button
                      className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50 transition"
                      onClick={() => openScheduleModal("online")}
                    >
                      Online Interview
                    </button>

                    <button
                      className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50 transition"
                      onClick={() => openScheduleModal("faceToFace")}
                    >
                      Face to Face Interview
                    </button>
                  </div>
                )}
              </div>

              <Button onClick={() => setEditModalOpen(true)}>Edit</Button>

              <Button
                disabled={isChecklistAssigned}
                onClick={() => setShowAssignModal(true)}
              >
                Submit Job
              </Button>
            </div>
          }
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <Info label="Name" value={candidate?.name} />
            <Info label="Email" value={candidate?.email} />
            <Info label="Phone" value={candidate?.phone} />
            <Info label="Job Title" value={candidate?.jobTitle} />
          </div>
        </Card>

        <div className="border-b">
          <div className="flex flex-wrap gap-2">
            {[
              "profile",
              "messages",
              "feedback",
              "documents",
              "tasks",
              "activity",
            ].map((tab) => (
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

        <div className="p-5 bg-white border rounded-2xl shadow-sm">
          {activeTab === "profile" && (
            <ProfileTab candidateId={candidate?.id} />
          )}
          {activeTab === "feedback" && (
            <FeedbackTab candidateId={candidate?.id} />
          )}
          {activeTab === "documents" && (
            <DocumentsTab candidateId={candidate?.id} />
          )}
          {activeTab === "tasks" && <TasksTab candidateId={candidate?.id} />}
          {activeTab === "messages" && (
            <div className="text-gray-500">Messages Coming Soon</div>
          )}
          {activeTab === "activity" && (
            <ActivityTab candidateId={candidate?.id} />
          )}
        </div>

        {editModalOpen && (
          <CandidateEditModal
            candidate={candidate}
            onClose={() => setEditModalOpen(false)}
          />
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
                    ? `Schedule Online Interview with ${candidate?.name || "Candidate"}`
                    : `Schedule Face to Face Interview with ${candidate?.name || "Candidate"}`}
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Phase 1 setup: panel, panel members, interview timing, and
                  email preparation.
                </p>
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
              <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1fr] gap-8">
                <div className="space-y-8">
                  <CardBlock
                    title="Interview Setup"
                    subtitle="Select panel members and define interview timing."
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <FormField
                        label="Interview Type"
                        value={
                          scheduleType === "online"
                            ? "Online Interview"
                            : "Face to Face Interview"
                        }
                        readOnly
                      />

                      <FormField
                        label="Candidate ID"
                        value={candidate?.id || ""}
                        readOnly
                      />

                      <FormField
                        label="Round Name"
                        placeholder="e.g. Technical Round 1"
                        value={scheduleForm.roundName}
                        onChange={(e) =>
                          handleScheduleInputChange("roundName", e.target.value)
                        }
                        error={scheduleErrors.roundName}
                      />

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
                        {durationOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
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
                        onChange={(e) =>
                          handleScheduleInputChange("endTime", e.target.value)
                        }
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

                <div className="space-y-8">
                  <CardBlock
                    title="Email to Candidate"
                    subtitle="Template is editable and can evolve in later phases."
                  >
                    <div className="space-y-5">
                      <SelectField
                        label="Email Template"
                        value={scheduleForm.emailTemplate}
                        onChange={(e) =>
                          handleScheduleInputChange(
                            "emailTemplate",
                            e.target.value,
                          )
                        }
                      >
                        {emailTemplateOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </SelectField>

                      <FormField
                        label="Subject"
                        value={scheduleForm.emailSubject}
                        onChange={(e) =>
                          handleScheduleInputChange(
                            "emailSubject",
                            e.target.value,
                          )
                        }
                        error={scheduleErrors.emailSubject}
                      />

                      <TextAreaField
                        label="Body"
                        value={scheduleForm.emailBody}
                        onChange={(e) =>
                          handleScheduleInputChange("emailBody", e.target.value)
                        }
                        error={scheduleErrors.emailBody}
                        rows={10}
                      />

                      <FormField
                        label="CC Emails (optional)"
                        placeholder="Enter comma-separated emails"
                        value={scheduleForm.ccEmails}
                        onChange={(e) =>
                          handleScheduleInputChange("ccEmails", e.target.value)
                        }
                      />

                      {scheduleType === "online" && (
                        <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-4 text-sm text-blue-700">
                          Backend will generate the final Teams invite and event
                          details using the created interview record.
                        </div>
                      )}
                    </div>
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
