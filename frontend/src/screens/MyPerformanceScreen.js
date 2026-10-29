// My Performance (CEO 2026-10-24): the reviews my reporting chain shared with me, praise and feedback
// about me, the reviews I owe as a reviewer, and praise / feedback for a colleague.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Select } from "../components/ui";
import { FeedbackForm, FeedbackSection, ReviewList } from "../components/PerformancePanel";
import { getColleagues, getMyPerformance } from "../services/api/performance";

function Section({ title, subtitle, children }) {
  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-gray-900">{title}</h2>
      {subtitle ? <p className="mb-4 mt-0.5 text-xs text-gray-500">{subtitle}</p> : <div className="mb-4" />}
      {children}
    </section>
  );
}

function GiveFeedback() {
  const [colleagues, setColleagues] = useState([]);
  const [employeeId, setEmployeeId] = useState("");
  const [sent, setSent] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    getColleagues().then(setColleagues).catch((err) => {
      console.error("[MyPerformance] Failed to load colleagues:", err);
      setError(err.message);
    });
  }, []);
  const name = colleagues.find((c) => c.employee_id === employeeId)?.name;
  return (
    <div className="space-y-3">
      {error ? <div className="text-sm text-rose-700">{error}</div> : null}
      <Select label="Colleague" value={employeeId} onChange={(value) => { setEmployeeId(value); setSent(""); }}
        options={[{ value: "", label: "Choose a colleague" },
          ...colleagues.map((c) => ({ value: c.employee_id, label: c.title ? `${c.name} (${c.title})` : c.name }))]} />
      {employeeId ? <FeedbackForm employeeId={employeeId} onSaved={() => setSent(`Sent to ${name}.`)} /> : null}
      {sent ? <div className="text-sm text-green-700">{sent}</div> : null}
    </div>
  );
}

export default function MyPerformanceScreen() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      setData(await getMyPerformance());
    } catch (err) {
      console.error("[MyPerformance] Failed to load:", err);
      setError(err.message);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  if (error) return <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>;
  if (!data) return <div className="py-10 text-center text-gray-500">Loading your performance...</div>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My Performance</h1>
        <p className="text-sm text-gray-600">Reviews shared with you, praise and feedback about you, and the reviews you owe.</p>
      </div>
      {data.to_review.length ? (
        <Section title={`Reviews I owe (${data.to_review.length})`}>
          <ul className="divide-y text-sm">
            {data.to_review.map((r) => (
              <li key={r.review_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <Link to={`/employees/${r.employee_id}?tab=performance&review=${r.review_id}`} className="font-medium text-blue-700 hover:underline">
                  {r.level_label} review: {r.employee_name}
                </Link>
                <span className={r.status === "MISSED" ? "text-rose-700" : "text-gray-500"}>
                  {r.status === "MISSED" ? "Missed, " : ""}due {r.due_date}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
      {data.employee_id ? (
        <>
          <Section title="My reviews" subtitle="A review shows here once your reviewer completes it and shares it with you.">
            <ReviewList data={data} onSaved={load} />
          </Section>
          <Section title="Praise and feedback about me">
            <FeedbackSection data={data} employeeId={data.employee_id} onSaved={load} allowGive={false} />
          </Section>
        </>
      ) : !data.to_review.length ? (
        <Section title="Nothing to show">
          <div className="text-sm text-gray-500">Your login has no employee record and no reviews are waiting on you.</div>
        </Section>
      ) : null}
      <Section title="Give praise or feedback" subtitle="Praise is visible to everyone. Feedback goes to the person, their reporting chain and HR.">
        <GiveFeedback />
      </Section>
    </div>
  );
}
