import { useState , useEffect } from "react";
import { Card, Button } from "../components/ui";
import ProfileTab from "./tabs/ProfileTab";
import FeedbackTab from "./tabs/FeedbackTab";
import DocumentsTab from "./tabs/DocumentsTab";
import TasksTab from "./tabs/TasksTab";
import { getCandidateStatus } from "../services/api/candidateStatus";
import CandidateEditModal from "./CandidateEditModal";


export default function CandidateDetailsScreen({ candidate, onBack }) {
    
  const [activeTab, setActiveTab] = useState("profile");
  const [statusData, setStatusData] = useState(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
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

  return (
    <div className="grid gap-4">

   
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
    <div className="flex flex-col items-end gap-2">
      <Button variant="ghost" onClick={onBack}>
        Back
      </Button>
      

      <Button onClick={() => setEditModalOpen(true)}>
        Edit
      </Button>
    </div>
  }
>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Name</span>
            <div className="font-medium">{candidate?.name}</div>
          </div>
          <div>
            <span className="text-gray-500">Email</span>
            <div className="font-medium">{candidate?.email}</div>
          </div>
          <div>
            <span className="text-gray-500">Phone</span>
            <div className="font-medium">{candidate?.phone}</div>
          </div>
          <div>
            <span className="text-gray-500">Job Title</span>
            <div className="font-medium">{candidate?.jobTitle}</div>
          </div>
        </div>
      
      </Card>

    
      <div className="flex gap-2 border-b pb-2">
        {["profile", "messages", "feedback", "documents", "tasks", "activity"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-all ${
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

       
       {activeTab === "profile" && (
  <ProfileTab candidateId={candidate?.id} />
)}

       
        {activeTab === "feedback" && (
  <FeedbackTab candidateId={candidate?.id} />
)}

        {activeTab === "messages" && (
          <div className="text-gray-500">Messages Coming Soon</div>
        )}

        {activeTab === "documents" && (
  <DocumentsTab candidateId={candidate?.id} />
)}

        {activeTab === "tasks" && (
  <TasksTab candidateId={candidate?.id} />
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