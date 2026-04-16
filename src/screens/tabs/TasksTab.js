import { useEffect, useState } from "react";
import { apiRequest } from "../../services/api/client";
import { hrCompleteChecklistItem } from "../../services/api/checklists";

export default function TasksTab({ candidateId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [completingId, setCompletingId] = useState(null);

 
  useEffect(() => {
    if (!notice) return;

    const timer = setTimeout(() => {
      setNotice("");
    }, 3000);

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

  useEffect(() => {
    if (!candidateId) return;
    fetchTasks();
  }, [candidateId]);

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
                className="h-2 bg-green-500 rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>

           
            <div className="grid gap-3">
              {checklist.items.map((item) => (
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
                  </div>

                  <div className="flex items-center gap-2">
                    <StatusBadge status={item.status} />

               
                    {item.status !== "completed" && (
                      <button
                        onClick={() => handleCompleteItem(item.id)}
                        disabled={completingId === item.id}
                        className="text-xs bg-blue-500 text-white px-3 py-1 rounded"
                      >
                        {completingId === item.id ? "..." : "Complete"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }) {
  let styles = "bg-gray-100 text-gray-600";

  if (status === "completed") {
    styles = "bg-green-100 text-green-600";
  } else if (status === "pending") {
    styles = "bg-yellow-100 text-yellow-700";
  } else if (status === "active") {
    styles = "bg-blue-100 text-blue-600";
  }

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