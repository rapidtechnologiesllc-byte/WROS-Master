import { useEffect, useState } from "react";
import { apiRequest } from "../../services/api/client";

export default function DocumentsTab({ candidateId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!candidateId) return;

    let isMounted = true;

    const fetchDocuments = async () => {
      try {
        setLoading(true);
        setError("");

        const { data } = await apiRequest(
          `/documents/candidate/${candidateId}`,
          { method: "GET" }
        );

        if (isMounted) {
          setData(data || null);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || "Failed to load documents");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchDocuments();

    return () => {
      isMounted = false;
    };
  }, [candidateId]);

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">
        Loading documents...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center text-red-500">
        {error}
      </div>
    );
  }

  if (!data || !data.documents || data.documents.length === 0) {
    return (
      <div className="p-6 text-center text-gray-400">
        No documents available
      </div>
    );
  }

  return (
    <div className="grid gap-4">

      {data.documents.map((doc) => (
        <div
          key={doc.id}
          className="flex justify-between items-center bg-white border rounded-2xl p-4 shadow-sm hover:shadow-md transition"
        >
          
          <div>
            <div className="font-medium text-gray-900">
              {doc.document_name || "Document"}
            </div>

            <div className="text-xs text-gray-400 mt-1">
              {doc.document_type || "File"} • Uploaded:{" "}
              {formatDate(doc.created_at)}
            </div>
          </div>

        
          <div className="flex items-center gap-3">

            <StatusBadge status={doc.status} />

           
            {doc.document_url && (
              <a
                href={doc.document_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-medium text-blue-600 hover:underline"
              >
                View
              </a>
            )}
          </div>
        </div>
      ))}

    </div>
  );
}


function StatusBadge({ status }) {
  let styles = "bg-gray-100 text-gray-600";

  if (status === "verified") {
    styles = "bg-green-100 text-green-600";
  } else if (status === "pending") {
    styles = "bg-yellow-100 text-yellow-700";
  } else if (status === "rejected") {
    styles = "bg-red-100 text-red-600";
  }

  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${styles}`}>
      {status || "unknown"}
    </span>
  );
}


function formatDate(date) {
  if (!date) return "-";
  return new Date(date).toLocaleDateString();
}