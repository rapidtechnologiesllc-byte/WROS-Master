import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../../services/api/client";
import { hrCompleteChecklistItem } from "../../services/api/checklists";
import { getCandidateDocuments } from "../../services/api/documents";

const DOCUMENT_TASK_MAPPINGS = [
  { type: "pan", keywords: ["pan"] },
  { type: "aadhar", keywords: ["aadhar", "aadhaar"] },
  {
    type: "salary_slip",
    keywords: ["salary slip", "salary slips", "pay slip", "pay slips", "payslip"]
  },
  { type: "bank_statement", keywords: ["bank statement", "bank"] },
  {
    type: "education",
    keywords: ["education certificate", "degree certificate"]
  },
  {
    type: "experience",
    keywords: ["experience letter", "relieving letter"]
  },
  { type: "resume", keywords: ["resume", "cv"] }
];

export default function TasksTab({ candidateId }) {
  const [data, setData] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("success");
  const [completingId, setCompletingId] = useState(null);

  const noticeTimerRef = useRef(null);

  const showNotice = useCallback((message, type = "success") => {
    setNotice(message);
    setNoticeType(type);

    if (noticeTimerRef.current) {
      clearTimeout(noticeTimerRef.current);
    }

    noticeTimerRef.current = setTimeout(() => {
      setNotice("");
    }, 4000);
  }, []);

  const fetchTasks = useCallback(async () => {
    const { data } = await apiRequest(
      `/checklist/hr/candidate/${candidateId}`,
      { method: "GET" }
    );
    setData(data || null);
  }, [candidateId]);

  const fetchDocuments = useCallback(async () => {
    const docs = await getCandidateDocuments(candidateId);
    setDocuments(Array.isArray(docs?.documents) ? docs.documents : []);
  }, [candidateId]);

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true);
      await fetchTasks();
      await fetchDocuments();
    } catch (err) {
      showNotice(err.message || "Failed to load tasks.", "error");
    } finally {
      setLoading(false);
    }
  }, [fetchTasks, fetchDocuments, showNotice]);

  useEffect(() => {
    if (!candidateId) return;
    fetchAll();

    return () => {
      if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    };
  }, [candidateId, fetchAll]);

  const getDocumentTypeFromTask = useCallback((title = "") => {
    const lower = title.toLowerCase();

    const match = DOCUMENT_TASK_MAPPINGS.find(({ keywords }) =>
      keywords.some((k) => lower.includes(k))
    );

    return match?.type || null;
  }, []);

  const isDocumentVerified = (title) => {
    const docType = getDocumentTypeFromTask(title);

    if (!docType) return false;

    return documents.some(
      (doc) =>
        doc.document_type === docType &&
        doc.is_verified === true
    );
  };

  const handleCompleteItem = async (itemId) => {
    try {
      setCompletingId(itemId);

      const res = await hrCompleteChecklistItem(itemId);

      await fetchAll();

      showNotice(res?.message || "Task marked complete");
    } catch (err) {
      showNotice(err.message || "Failed to complete task", "error");
    } finally {
      setCompletingId(null);
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">
        Loading tasks...
      </div>
    );
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
        <div
          className={`rounded-xl border px-4 py-3 text-sm font-medium ${
            noticeType === "success"
              ? "border-green-200 bg-green-50 text-green-700"
              : "border-red-200 bg-red-50 text-red-700"
          }`}
        >
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
                const verified = isDocumentVerified(item.title);
                const isCompleted = item.status === "completed";

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

                      {verified && !isCompleted && (
                        <div className="text-xs text-green-600 mt-2">
                          Document verified. You can complete this task.
                        </div>
                      )}

                      {!verified && !isCompleted && (
                        <div className="text-xs text-yellow-600 mt-2">
                          Waiting for document verification.
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <StatusBadge status={item.status} />

                      {!isCompleted ? (
                        <button
                          onClick={() => handleCompleteItem(item.id)}
                          disabled={!verified || completingId === item.id}
                          className={`text-xs px-3 py-1 rounded text-white ${
                            verified
                              ? "bg-blue-600"
                              : "bg-gray-400 cursor-not-allowed"
                          }`}
                        >
                          {completingId === item.id
                            ? "Completing..."
                            : "Complete"}
                        </button>
                      ) : (
                        <span className="text-xs text-green-600 font-semibold">
                          ✔ Completed
                        </span>
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