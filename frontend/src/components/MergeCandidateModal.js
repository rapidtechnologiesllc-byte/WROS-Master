// Merge candidate (CEO 2026-11-04: "THE SAME CANDIDATE GOT created twice"): pick the other record and which one to
// keep. Everything moves to the record kept and the other is removed: one person, one record (CEO 2026-11-09).
// Its old link, email and phone keep leading here.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input } from "./ui";
import { getPossibleDuplicates, mergeCandidate } from "../services/api/candidates";

export default function MergeCandidateModal({ candidate, onClose }) {
  const navigate = useNavigate();
  const [term, setTerm] = useState("");
  const [matches, setMatches] = useState([]);
  const [picked, setPicked] = useState(null);
  const [keep, setKeep] = useState("older");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const id = candidate?.id || candidate?.candidate_id;

  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      getPossibleDuplicates(id, term)
        .then((rows) => { if (live) setMatches(rows || []); })
        .catch((err) => { if (live) setError(err.message || "Could not look for duplicates."); });
    }, 250);
    return () => { live = false; clearTimeout(timer); };
  }, [id, term]);

  const merge = async () => {
    setBusy(true);
    setError("");
    try {
      const [kept, removed] = keep === "this" ? [id, picked.id] : [picked.id, id];
      const result = await mergeCandidate(removed, kept);
      onClose();
      navigate(`/candidates/${result.kept_candidate_id}`);
    } catch (err) {
      setError(err.message || "Could not merge.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div role="dialog" aria-label="Merge candidate" className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl">
        <div className="text-lg font-semibold text-gray-900">Merge candidate</div>
        <p className="mt-1 text-sm text-gray-600">
          History, interviews, documents, tasks and Thunder activity move to the record you keep, and the other record is removed:
          one person, one record. Its old link, email and phone keep leading to the record you keep.
        </p>
        {error ? <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}
        <div className="mt-4"><Input label="Find the other record (name or email)" value={term} onChange={setTerm} /></div>
        <div className="mt-3 max-h-56 space-y-2 overflow-y-auto">
          {matches.length ? matches.map((m) => (
            <label key={m.id} className="flex cursor-pointer items-start gap-2 rounded-xl border p-3 text-sm">
              <input type="radio" name="other-record" checked={picked?.id === m.id} onChange={() => setPicked(m)} className="mt-1" />
              <span>
                <span className="font-semibold text-gray-900">{m.name || m.email}</span>
                <span className="ml-2 rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">{m.reason}</span>
                <span className="block text-xs text-gray-600">{m.email} · {m.phone || "no phone"} · {m.source || "no source"} · added {m.created_at?.slice(0, 10) || "unknown"}</span>
              </span>
            </label>
          )) : <div className="py-4 text-center text-sm text-gray-500">No likely duplicates found. Search above.</div>}
        </div>
        {picked ? (
          <div className="mt-3 grid gap-1 text-sm">
            <div className="font-semibold text-gray-900">Which record do you keep?</div>
            <label className="flex items-center gap-2"><input type="radio" name="keep" checked={keep === "older"} onChange={() => setKeep("older")} />{picked.name || picked.email} ({picked.email})</label>
            <label className="flex items-center gap-2"><input type="radio" name="keep" checked={keep === "this"} onChange={() => setKeep("this")} />This record ({candidate?.email || candidate?.candidate_email})</label>
          </div>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!picked || busy} onClick={merge}>{busy ? "Merging…" : "Merge"}</Button>
        </div>
      </div>
    </div>
  );
}
