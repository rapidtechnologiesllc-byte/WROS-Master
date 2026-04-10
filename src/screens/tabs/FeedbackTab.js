import { useEffect, useState } from "react";
import { getCandidateInterviewHistory } from "../../services/api/interviews";

export default function FeedbackTab({ candidateId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!candidateId) return;

    let isMounted = true;

    const fetchFeedback = async () => {
      try {
        setLoading(true);
        setError("");

        const result = await getCandidateInterviewHistory(candidateId);
       

        if (isMounted) {
          setData(result || null);
        }
      } catch (err) {
        if (isMounted) {
          setError(err?.message || "Failed to load feedback");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchFeedback();

    return () => {
      isMounted = false;
    };
  }, [candidateId]);

 
  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">
        Loading feedback...
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

 
  if (!data) {
    return (
      <div className="p-6 text-center text-gray-400">
        No feedback data available
      </div>
    );
  }

  return (
    <div className="grid gap-6">

   
      <section className="bg-white border rounded-2xl p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-500 mb-3 uppercase tracking-wide">
          Interview Summary
        </h3>

        <div className="grid grid-cols-4 gap-4 text-sm">
          <Stat label="Total" value={data.total_interviews} />
          <Stat label="Scheduled" value={data.scheduled_interviews} />
          <Stat label="Completed" value={data.completed_interviews} />
          <Stat label="Cancelled" value={data.cancelled_interviews} />
        </div>
      </section>

      
      <section className="bg-white border rounded-2xl p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-500 mb-3 uppercase tracking-wide">
          Interview History
        </h3>

        {data.interviews?.length === 0 ? (
          <div className="text-gray-400">No interviews found</div>
        ) : (
          <div className="grid gap-3">
            {data.interviews?.map((i) => (
              <div
                key={i.id}
                className="border rounded-xl p-4 flex justify-between items-center"
              >
                <div>
                  <div className="font-medium text-gray-900">
                    {i.panel_round_name}
                  </div>
                  <div className="text-sm text-gray-500">
                    {new Date(i.start_time).toLocaleString()}
                  </div>
                </div>

                <div className="text-sm font-medium">
                  <StatusBadge status={i.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

    </div>
  );
}


function Stat({ label, value }) {
  return (
    <div className="text-center">
      <div className="text-lg font-semibold text-gray-900">
        {value ?? 0}
      </div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const color =
    status === "Completed"
      ? "text-green-600"
      : status === "Cancelled"
      ? "text-red-600"
      : "text-yellow-600";

  return <span className={color}>{status}</span>;
}