import { useState, useEffect, useRef } from "react";
import { Card, Button } from "../components/ui";
import ProfileTab from "./tabs/ProfileTab";
import FeedbackTab from "./tabs/FeedbackTab";
import DocumentsTab from "./tabs/DocumentsTab";
import TasksTab from "./tabs/TasksTab";
import { getCandidateStatus } from "../services/api/candidateStatus";
import {
  listChecklistTemplates,
  assignChecklistToCandidate,
  getChecklistTemplate,
  getCandidateChecklists
} from "../services/api/checklists";
import {
  createInterviewPanel,
  assignPanelMember,
  createInterview
} from "../services/api/interviews";
import CandidateEditModal from "./CandidateEditModal";

const initialScheduleForm = {
  roundName: "",
  interviewerId: "",
  startTime: "",
  endTime: "",
  meetingLink: "",
  location: ""
};

export default function CandidateDetailsScreen({ candidate, onBack }) {
  const [activeTab, setActiveTab] = useState("profile");
  const [statusData, setStatusData] = useState(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [notice, setNotice] = useState("");

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

  useEffect(() => {
    if (!candidate?.id) return;

    const fetchStatus = async () => {
      try {
        const res = await getCandidateStatus(candidate.id);
        setStatusData(res);
      } catch (err) {
        console.error(err);
      }
    };

    fetchStatus();
  }, [candidate?.id]);

  useEffect(() => {
    if (!candidate?.id) return;

    const checkChecklist = async () => {
      try {
        const res = await getCandidateChecklists(candidate.id);

        if (res && res.length > 0) {
          setIsChecklistAssigned(true);
        } else {
          setIsChecklistAssigned(false);
        }
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
        templateId: selectedTemplate
      });

      setNotice("Checklist assigned successfully");

      setTimeout(() => {
        setNotice("");
      }, 3000);

      setActiveTab("tasks");
      setIsChecklistAssigned(true);
      setShowAssignModal(false);
      setSelectedTemplate("");
      setSelectedTemplateData(null);
    } catch (err) {
      console.error(err);
      setNotice("Failed to assign checklist");
      setTimeout(() => {
        setNotice("");
      }, 3000);
    } finally {
      setAssigning(false);
    }
  };

  const handleScheduleOptionClick = (type) => {
    setShowScheduleMenu(false);
    setScheduleType(type);
    setScheduleErrors({});
    setScheduleForm(initialScheduleForm);
    setShowScheduleModal(true);
  };

  const closeScheduleModal = () => {
    if (scheduling) return;
    setShowScheduleModal(false);
    setScheduleType("");
    setScheduleErrors({});
    setScheduleForm(initialScheduleForm);
  };

  const handleScheduleInputChange = (field, value) => {
    setScheduleForm((prev) => ({
      ...prev,
      [field]: value
    }));

    if (scheduleErrors[field]) {
      setScheduleErrors((prev) => ({
        ...prev,
        [field]: ""
      }));
    }
  };

  const validateScheduleForm = () => {
    const errors = {};

    if (!scheduleForm.roundName.trim()) {
      errors.roundName = "Round name is required";
    }

    if (!scheduleForm.interviewerId.trim()) {
      errors.interviewerId = "Interviewer ID is required";
    }

    if (!scheduleForm.startTime) {
      errors.startTime = "Start time is required";
    }

    if (!scheduleForm.endTime) {
      errors.endTime = "End time is required";
    }

    if (
      scheduleForm.startTime &&
      scheduleForm.endTime &&
      new Date(scheduleForm.endTime) <= new Date(scheduleForm.startTime)
    ) {
      errors.endTime = "End time must be after start time";
    }

    if (scheduleType === "online" && !scheduleForm.meetingLink.trim()) {
      errors.meetingLink = "Meeting link is required for online interview";
    }

    if (scheduleType === "faceToFace" && !scheduleForm.location.trim()) {
      errors.location = "Location is required for face to face interview";
    }

    setScheduleErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleScheduleInterview = async () => {
    if (!candidate?.id) {
      setNotice("Candidate details are missing");
      setTimeout(() => setNotice(""), 3000);
      return;
    }

    if (!validateScheduleForm()) {
      return;
    }

    try {
      setScheduling(true);

      const panelRes = await createInterviewPanel({
        candidateId: candidate.id,
        roundName: scheduleForm.roundName.trim()
      });

      const panelId = panelRes?.id;

      if (!panelId) {
        throw new Error("Panel created but panel ID was not returned");
      }

      await assignPanelMember({
        panelId,
        interviewerId: scheduleForm.interviewerId.trim()
      });

      await createInterview({
        panelId,
        candidateId: candidate.id,
        startTime: scheduleForm.startTime,
        endTime: scheduleForm.endTime,
        meetingLink:
          scheduleType === "online"
            ? scheduleForm.meetingLink.trim()
            : null,
        outlookEventId: null,
        status: "Scheduled"
      });

      setNotice(
        scheduleType === "online"
          ? "Online interview scheduled successfully"
          : "Face to face interview scheduled successfully"
      );

      setTimeout(() => {
        setNotice("");
      }, 3000);

      closeScheduleModal();
      setActiveTab("activity");
    } catch (err) {
      console.error("Failed to schedule interview", err);
      setNotice(err?.message || "Failed to schedule interview");
      setTimeout(() => {
        setNotice("");
      }, 4000);
    } finally {
      setScheduling(false);
    }
  };

  return (
    <div className="grid gap-4">
      {notice && (
        <div className="bg-green-100 text-green-700 p-3 rounded-lg text-sm font-medium">
          {notice}
        </div>
      )}

      <Card
        title={
          <div className="flex items-center gap-3">
            <span className="font-semibold">Candidate Details</span>

            {statusData?.status && (
              <StatusBadge type="account" value={statusData.status} />
            )}

            {statusData?.pipeline_status && (
              <StatusBadge type="pipeline" value={statusData.pipeline_status} />
            )}
          </div>
        }
        right={
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={onBack}>
              Back
            </Button>

            <div className="relative" ref={scheduleMenuRef}>
              <Button onClick={() => setShowScheduleMenu((prev) => !prev)}>
                Schedule
              </Button>

              {showScheduleMenu && (
                <div className="absolute right-0 mt-2 w-52 bg-white border border-gray-200 rounded-xl shadow-lg z-20 overflow-hidden">
                  <button
                    className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50 transition"
                    onClick={() => handleScheduleOptionClick("online")}
                  >
                    Online Interview
                  </button>

                  <button
                    className="w-full text-left px-4 py-3 text-sm hover:bg-gray-50 transition"
                    onClick={() => handleScheduleOptionClick("faceToFace")}
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
              {isChecklistAssigned ? "Checklist Assigned" : "Assign Checklist"}
            </Button>
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-4 text-sm">
          <Info label="Name" value={candidate?.name} />
          <Info label="Email" value={candidate?.email} />
          <Info label="Phone" value={candidate?.phone} />
          <Info label="Job Title" value={candidate?.jobTitle} />
        </div>
      </Card>

      <div className="flex gap-2 border-b pb-2">
        {["profile", "messages", "feedback", "documents", "tasks", "activity"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg ${
              activeTab === tab
                ? "bg-white border border-b-0 border-gray-300 text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {tab.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="mt-4 p-4 bg-white border rounded-xl shadow-sm">
        {activeTab === "profile" && <ProfileTab candidateId={candidate?.id} />}
        {activeTab === "feedback" && <FeedbackTab candidateId={candidate?.id} />}
        {activeTab === "documents" && <DocumentsTab candidateId={candidate?.id} />}
        {activeTab === "tasks" && <TasksTab candidateId={candidate?.id} />}
        {activeTab === "messages" && (
          <div className="text-gray-500">Messages Coming Soon</div>
        )}
        {activeTab === "activity" && (
          <div className="text-gray-500">Activity Coming Soon</div>
        )}
      </div>

      {editModalOpen && (
        <CandidateEditModal
          candidate={candidate}
          onClose={() => setEditModalOpen(false)}
        />
      )}

      {showAssignModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white w-[420px] rounded-2xl shadow-xl p-6">
            <h2 className="text-lg font-semibold mb-2">Assign Checklist</h2>
            <p className="text-xs text-gray-500 mb-4">
              Select template and preview before assigning
            </p>

            {loadingTemplates ? (
              <div className="text-sm text-gray-500">Loading templates...</div>
            ) : (
              <select
                className="w-full border rounded-lg p-2 mb-4"
                value={selectedTemplate}
                onChange={(e) => handleTemplateChange(e.target.value)}
              >
                <option value="">Select Template</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            )}

            {selectedTemplateData && (
              <div className="border rounded-lg p-3 bg-gray-50 mb-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-semibold">Preview</span>
                  <span className="text-xs text-gray-500">
                    {selectedTemplateData.items?.length || 0} items
                  </span>
                </div>

                <ul className="text-sm text-gray-700 space-y-1 max-h-40 overflow-auto">
                  {selectedTemplateData.items?.map((item) => (
                    <li key={item.id}>• {item.title}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowAssignModal(false)}>
                Cancel
              </Button>

              <Button
                onClick={handleAssignChecklist}
                disabled={!selectedTemplate || assigning}
              >
                {assigning ? "Assigning..." : "Assign"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {showScheduleModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden">
            <div className="border-b px-6 py-4 flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {scheduleType === "online"
                    ? "Schedule Online Interview"
                    : "Schedule Face to Face Interview"}
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Create panel, assign interviewer, and schedule interview for{" "}
                  <span className="font-medium text-gray-700">
                    {candidate?.name || "candidate"}
                  </span>
                </p>
              </div>

              <button
                type="button"
                onClick={closeScheduleModal}
                disabled={scheduling}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-6">
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
                  placeholder="Enter round name"
                  value={scheduleForm.roundName}
                  onChange={(e) =>
                    handleScheduleInputChange("roundName", e.target.value)
                  }
                  error={scheduleErrors.roundName}
                />

                <FormField
                  label="Interviewer ID"
                  placeholder="Enter interviewer ID"
                  value={scheduleForm.interviewerId}
                  onChange={(e) =>
                    handleScheduleInputChange("interviewerId", e.target.value)
                  }
                  error={scheduleErrors.interviewerId}
                />

                <FormField
                  label="Start Time"
                  type="datetime-local"
                  value={scheduleForm.startTime}
                  onChange={(e) =>
                    handleScheduleInputChange("startTime", e.target.value)
                  }
                  error={scheduleErrors.startTime}
                />

                <FormField
                  label="End Time"
                  type="datetime-local"
                  value={scheduleForm.endTime}
                  onChange={(e) =>
                    handleScheduleInputChange("endTime", e.target.value)
                  }
                  error={scheduleErrors.endTime}
                />

                {scheduleType === "online" && (
                  <div className="md:col-span-2">
                    <FormField
                      label="Meeting Link"
                      placeholder="Paste meeting link"
                      value={scheduleForm.meetingLink}
                      onChange={(e) =>
                        handleScheduleInputChange("meetingLink", e.target.value)
                      }
                      error={scheduleErrors.meetingLink}
                    />
                  </div>
                )}

                {scheduleType === "faceToFace" && (
                  <div className="md:col-span-2">
                    <FormField
                      label="Location"
                      placeholder="Enter office / venue location"
                      value={scheduleForm.location}
                      onChange={(e) =>
                        handleScheduleInputChange("location", e.target.value)
                      }
                      error={scheduleErrors.location}
                    />
                  </div>
                )}
              </div>

              {scheduleType === "faceToFace" && (
                <div className="mt-4 rounded-lg bg-blue-50 border border-blue-100 px-4 py-3">
                  <p className="text-sm text-blue-700">
                    Location is currently collected for UI completeness. Your
                    existing interview create API appears to use meeting link but
                    does not yet show a dedicated location field.
                  </p>
                </div>
              )}
            </div>

            <div className="border-t px-6 py-4 flex justify-end gap-3 bg-gray-50">
              <Button variant="ghost" onClick={closeScheduleModal} disabled={scheduling}>
                Cancel
              </Button>

              <Button onClick={handleScheduleInterview} disabled={scheduling}>
                {scheduling ? "Scheduling..." : "Schedule Interview"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <span className="text-gray-500">{label}</span>
      <div className="font-medium">{value || "-"}</div>
    </div>
  );
}

function StatusBadge({ type, value }) {
  let styles = "bg-gray-100 text-gray-600";

  if (type === "account") {
    if (value === "Active") styles = "bg-green-100 text-green-600";
    if (value === "Inactive") styles = "bg-red-100 text-red-600";
  }

  if (type === "pipeline") {
    if (value === "Applied") styles = "bg-blue-100 text-blue-600";
    if (value === "Interview") styles = "bg-purple-100 text-purple-600";
    if (value === "Hired") styles = "bg-green-200 text-green-700";
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
  placeholder
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
            ? "bg-gray-100 text-gray-500 border-gray-200 cursor-not-allowed"
            : error
              ? "border-red-300 focus:border-red-400"
              : "border-gray-300 focus:border-gray-400"
        }`}
      />
      {error ? (
        <p className="text-xs text-red-500 mt-1">{error}</p>
      ) : null}
    </div>
  );
}