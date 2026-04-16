import { useState, useEffect } from "react";
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
import CandidateEditModal from "./CandidateEditModal";

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
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="grid gap-4">

     
      {notice && (
        <div className="bg-green-100 text-green-700 p-2 rounded text-sm">
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
            <Button variant="ghost" onClick={onBack}>Back</Button>

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
        {activeTab === "messages" && <div className="text-gray-500">Messages Coming Soon</div>}
        {activeTab === "activity" && <div className="text-gray-500">Activity Coming Soon</div>}
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

    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <span className="text-gray-500">{label}</span>
      <div className="font-medium">{value}</div>
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