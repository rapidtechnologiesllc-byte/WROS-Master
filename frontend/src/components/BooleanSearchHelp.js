// How to write a boolean search, and what a search's words found (shared by Candidates and a job's Search tab)
export function BooleanSearchHelp() {
  return (
    <div className="text-xs text-gray-500">
      Words side by side must all be there (AND). Use OR for either, NOT to leave out, brackets to group and
      &quot;quotes&quot; for an exact phrase. A skill also finds the other names it goes by. Example:{" "}
      <code className="rounded bg-gray-100 px-1">guidewire AND (policycenter OR &quot;claim center&quot;) NOT tester</code>
    </div>
  );
}

// Each word, how many candidates it finds on its own and the other names searched; then the suggestions
export function SearchExplain({ result }) {
  if (!result) return null;
  const words = Object.entries(result.term_counts || {});
  return (
    <div className="space-y-2">
      {words.length ? (
        <div className="flex flex-wrap gap-2">
          {words.map(([word, count]) => {
            const others = (result.expanded?.[word] || []).filter((n) => n.toLowerCase() !== word.toLowerCase());
            return (
              <span key={word} title={others.length ? `Also searched: ${others.join(", ")}` : undefined}
                className={`rounded-full px-2 py-0.5 text-xs ${count ? "bg-slate-100 text-slate-700" : "bg-rose-100 text-rose-800"}`}>
                {word}: {count} candidate{count === 1 ? "" : "s"}
                {others.length ? ` (+${others.length} other name${others.length === 1 ? "" : "s"})` : ""}
              </span>
            );
          })}
        </div>
      ) : null}
      {(result.suggestions || []).map((tip) => (
        <div key={tip} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">{tip}</div>
      ))}
    </div>
  );
}

// Where a candidate's match was found: a recorded skill, their title, or only their resume
export function FoundWhere({ found }) {
  const entries = Object.entries(found || {});
  if (!entries.length) return <span className="text-xs text-gray-400">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {entries.map(([word, places]) => (
        <span key={word} className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-800">
          {word}: {places.join(", ")}
        </span>
      ))}
    </div>
  );
}
