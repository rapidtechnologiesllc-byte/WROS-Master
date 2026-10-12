import { useState } from "react";
import { Loader, Plus, X } from "lucide-react";
import { queueLinkedInCandidate } from "../services/api/linkedinPipeline";

// Add a candidate from a LinkedIn profile URL. Shared by the Candidates page and
// the LinkedIn Pipeline screen so both go through the same backend queue.
export default function LinkedInAddCandidateModal({ open, onClose, onQueued }) {
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  if (!open) return null;

  const reset = () => {
    setLinkedinUrl("");
    setFirstName("");
    setLastName("");
    setEmail("");
  };

  const close = () => {
    setError(null);
    setNotice(null);
    onClose();
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (!linkedinUrl.trim()) {
      setError("Enter the candidate's LinkedIn profile URL.");
      return;
    }
    setSaving(true);
    try {
      const result = await queueLinkedInCandidate({
        linkedinUrl: linkedinUrl.trim(),
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim(),
      });
      if (result?.status === "QUEUED") {
        reset();
        setNotice("Added. The candidate record is being created and a follow-up task is on My Tasks.");
        if (onQueued) onQueued(result);
      } else if (result?.status === "ALREADY_EXISTS") {
        setError(`Candidate already in the system: ${result.candidate?.name || "existing record"}`);
      } else if (result?.status === "ALREADY_QUEUED") {
        const stage = (result.pipeline_item?.status || "").replace(/_/g, " ");
        setError(`${result.message || "Already in the LinkedIn pipeline"}${stage ? ` (status: ${stage})` : ""}`);
      } else {
        setError(`Unexpected response from the server: ${result?.status || "no status"}`);
      }
    } catch (err) {
      setError(err?.message || "Failed to add the candidate from LinkedIn");
    } finally {
      setSaving(false);
    }
  };

  const field = "w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-bx-orange";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" role="dialog" aria-modal="true">
      <form onSubmit={submit} className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Add candidate from LinkedIn</h2>
          <button type="button" onClick={close} className="text-gray-500 hover:text-gray-800" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-3">
          <input
            type="url"
            placeholder="https://www.linkedin.com/in/..."
            value={linkedinUrl}
            onChange={(e) => setLinkedinUrl(e.target.value)}
            className={field}
            autoFocus
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input type="text" placeholder="First name (optional)" value={firstName}
              onChange={(e) => setFirstName(e.target.value)} className={field} />
            <input type="text" placeholder="Last name (optional)" value={lastName}
              onChange={(e) => setLastName(e.target.value)} className={field} />
          </div>
          <input type="email" placeholder="Email (optional, if known)" value={email}
            onChange={(e) => setEmail(e.target.value)} className={field} />
        </div>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {notice && <p className="mt-3 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={close}
            className="rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50">
            Close
          </button>
          <button type="submit" disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-bx-orange px-4 py-2 text-white hover:bg-bx-orange-hover disabled:bg-gray-400">
            {saving ? <Loader className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {saving ? "Adding..." : "Add from LinkedIn"}
          </button>
        </div>
      </form>
    </div>
  );
}
