// Candidate search/listing and selection screen.
import { useMemo, useState } from "react";
import { Plus, Search, Users } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge, Table } from "../components/ui";
import CandidateEditModal from "./CandidateEditModal";

export default function CandidateSearch({
  candidates,
  jobs,
  selectedCandidateId,
  setSelectedCandidateId,
  selectedJobId,
  setSelectedJobId,
  onCreateCandidate,
  onMatchingJobs,
  onInterviewSchedule,
  onUpdateCandidate,
  onDeleteCandidate,
  onFetchCandidateById
}) {
  const [query, setQuery] = useState("");
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editCandidateId, setEditCandidateId] = useState("");
  const [overrideEditingCandidate, setOverrideEditingCandidate] = useState(null);

  const editingCandidate = useMemo(() => {
    if (
      overrideEditingCandidate &&
      String(overrideEditingCandidate.id || "") === String(editCandidateId || "")
    ) {
      return overrideEditingCandidate;
    }
    return candidates.find((c) => c.id === editCandidateId) || null;
  }, [candidates, editCandidateId, overrideEditingCandidate]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        c.phone.toLowerCase().includes(q)
    );
  }, [candidates, query]);

  return (
    <div className="grid gap-4">
      <Card
        title="Search Existing Candidate"
        icon={<Search className="h-4 w-4" />}
        right={
          <Button onClick={onCreateCandidate}>
            <Plus className="h-4 w-4" /> Add New
          </Button>
        }
      >
        <div className="grid gap-3 md:grid-cols-3">
          <Input
            label="Search (phone / email / name)"
            value={query}
            onChange={setQuery}
            placeholder="+1 555... or name@..."
          />
          <label className="block">
            <div className="mb-1 text-xs font-semibold text-gray-700">
              Selected Candidate
            </div>
            <select
              value={selectedCandidateId}
              onChange={(e) => setSelectedCandidateId(e.target.value)}
              className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <Select
            label="Selected Job"
            value={selectedJobId}
            onChange={setSelectedJobId}
            options={jobs.map((j) => j.id)}
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={onMatchingJobs}>
            Show matching jobs
          </Button>
          <Button variant="secondary" onClick={onInterviewSchedule}>
            Interview request / scheduling
          </Button>
        </div>
      </Card>

      <Card title="Candidates" icon={<Users className="h-4 w-4" />}>
        <Table
          columns={[
            { key: "name", header: "Name" },
            { key: "contact", header: "Contact" },
            { key: "jobTitle", header: "Job Title" },
            { key: "status", header: "Status" },
          ]}
          rows={filtered.map((c) => ({
            name: (
              <button
                className="font-semibold hover:underline"
                onClick={async () => {
                  setSelectedCandidateId(c.id);
                  setEditCandidateId(c.id);
                  setOverrideEditingCandidate(null);
                  if (onFetchCandidateById) {
                    try {
                      const fresh = await onFetchCandidateById(c.id);
                      if (fresh) {
                        setOverrideEditingCandidate(fresh);
                      }
                    } catch (err) {
                      // Fall back to list data if detail fetch fails.
                    }
                  }
                  setEditModalOpen(true);
                }}
              >
                {c.name}
              </button>
            ),
            contact: (
              <div className="text-xs text-gray-700">
                <div>{c.email}</div>
                <div>{c.phone}</div>
              </div>
            ),
            jobTitle: c.jobTitle || "-",
            status: <StatusBadge status={c.status} />,
          }))}
        />

        <div className="mt-3 text-xs text-gray-600">
          Duplicate check (phone/email) + merge popup can be added here.
        </div>
      </Card>

      {editModalOpen && editingCandidate ? (
        <CandidateEditModal
          candidate={editingCandidate}
          onClose={() => {
            setEditModalOpen(false);
            setEditCandidateId("");
            setOverrideEditingCandidate(null);
          }}
          onUpdateCandidate={onUpdateCandidate}
        />
      ) : null}
    </div>
  );
}
