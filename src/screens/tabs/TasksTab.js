import { useEffect, useState } from "react";
import { apiRequest } from "../../services/api/client";
import { hrCompleteChecklistItem } from "../../services/api/checklists";
import { getCandidateDocuments } from "../../services/api/documents"; 

export default function TasksTab({ candidateId }) {
  const [data, setData] = useState(null);
  const [documents, setDocuments] = useState([]); 
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [completingId, setCompletingId] = useState(null);


  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 3000);
    return () => clearTimeout(timer);
  }, [notice]);

 
  const fetchTasks = async () => {
    try {
      setLoading(true);
      setError("");

      const { data } = await apiRequest(
        `/checklist/hr/candidate/${candidateId}`,
        { method: "GET" }
      );

      setData(data || null);
    } catch (err) {
      setError(err.message || "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  };

 
  const fetchDocuments = async () => {
    try {
      const docs = await getCandidateDocuments(candidateId);
        console.log("DOCUMENTS API:", docs);
      setDocuments(docs?.documents || []);
    } catch (err) {
      console.error("Failed to fetch documents", err);
    }
  };

  useEffect(() => {
    if (!candidateId) return;
    fetchTasks();
    fetchDocuments(); 
  }, [candidateId]);

  
  const isDocumentUploaded = (taskTitle) => {
    return documents.some((doc) => {
      const title = taskTitle.toLowerCase();

      if (title.includes("pan")) return doc.type === "PAN";
      if (title.includes("aadhaar")) return doc.type === "AADHAAR";
      if (title.includes("salary")) return doc.type === "SALARY_SLIP";

      return false;
    });
  };

  const handleCompleteItem = async (itemId) => {
    try {
      setCompletingId(itemId);

      const res = await hrCompleteChecklistItem(itemId);

      await fetchTasks();

      setNotice(res?.message || "Item marked complete");
    } catch (err) {
      setError(err.message || "Failed to complete item");
    } finally {
      setCompletingId(null);
    }
  };

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading tasks...</div>;
  }

  if (error) {
    return <div className="p-6 text-center text-red-500">{error}</div>;
  }

  if (!data || data.checklists?.length === 0) {
    return (
      <div className="p-6 text-center text-gray-400">
        No tasks available
      </div>
    );
  }

  return (
    <div className="grid gap-6">

     
      {notice && (
        <div className="bg-green-100 text-green-700 p-2 rounded text-sm">
          {notice}
        </div>
      )}

      {data.checklists.map((checklist) => {
        const progress =
          (checklist.completed_items / checklist.total_items) * 100;

        return (
          <div
            key={checklist.id}
            className="bg-white border rounded-2xl p-5 shadow-sm"
          >
           
            <div className="flex justify-between items-center mb-3">
              <div>
                <div className="font-semibold text-gray-900">
                  {checklist.template_name}
                </div>
                <div className="text-xs text-gray-400">
                  {checklist.total_items} tasks
                </div>
              </div>

              <div className="text-sm font-medium text-gray-600">
                {checklist.completed_items}/{checklist.total_items}
              </div>
            </div>

           
            <div className="w-full h-2 bg-gray-200 rounded-full mb-4">
              <div
                className="h-2 bg-green-500 rounded-full"
                style={{ width: `${progress}%` }}
              />
            </div>

           
            <div className="grid gap-3">
              {checklist.items.map((item) => {
                const uploaded = isDocumentUploaded(item.title); 

                return (
                  <div
                    key={item.id}
                    className="flex justify-between items-center border rounded-xl px-4 py-3"
                  >
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {item.title}
                      </div>

                      <div className="text-xs text-gray-400">
                        {item.description}
                      </div>

                      <div className="text-xs text-gray-400 mt-1">
                        Due: {formatDate(item.due_date)}
                      </div>

                     
                      {uploaded && (
                        <div className="text-xs text-green-600 mt-1">
                          Document Uploaded 
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <StatusBadge status={item.status} />

                      
                      {item.status !== "completed" && (
                        <button
                          onClick={() => handleCompleteItem(item.id)}
                          disabled={!uploaded || completingId === item.id}
                          className={`text-xs px-3 py-1 rounded text-white ${
                            uploaded
                              ? "bg-blue-500"
                              : "bg-gray-400 cursor-not-allowed"
                          }`}
                        >
                          {completingId === item.id ? "..." : "Complete"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }) {
  let styles = "bg-gray-100 text-gray-600";

  if (status === "completed") styles = "bg-green-100 text-green-600";
  else if (status === "pending") styles = "bg-yellow-100 text-yellow-700";
  else if (status === "active") styles = "bg-blue-100 text-blue-600";

  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${styles}`}>
      {status}
    </span>
  );
}

function formatDate(date) {
  if (!date) return "-";
  return new Date(date).toLocaleDateString();
}