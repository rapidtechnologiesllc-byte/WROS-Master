// Candidate search/listing and selection screen.
import { useMemo, useState } from "react";
import { Plus, Search, Users } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge, Table } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export default function CandidateSearch({
  candidates,
  jobs,
  selectedCandidateId,
  setSelectedCandidateId,
  selectedJobId,
  setSelectedJobId,
  onCreateCandidate,
  onMatchingJobs,
  onInterviewSchedule
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        c.phone.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q)
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
          <Select
            label="Selected Candidate"
            value={selectedCandidateId}
            onChange={setSelectedCandidateId}
            options={candidates.map((c) => c.id)}
          />
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
            { key: "id", header: "ID" },
            { key: "name", header: "Name" },
            { key: "contact", header: "Contact" },
            { key: "skills", header: "Skills" },
            { key: "status", header: "Status" }
          ]}
          rows={filtered.map((c) => ({
            id: (
              <button
                className="font-semibold hover:underline"
                onClick={() => setSelectedCandidateId(c.id)}
              >
                {c.id}
              </button>
            ),
            name: c.name,
            contact: (
              <div className="text-xs text-gray-700">
                <div>{c.email}</div>
                <div>{c.phone}</div>
              </div>
            ),
            skills: (
              <div className="flex flex-wrap gap-1">
                {c.skills.map((s) => (
                  <span key={s} className={cx(pill, "border-gray-200 bg-gray-50")}>
                    {s}
                  </span>
                ))}
              </div>
            ),
            status: <StatusBadge status={c.status} />
          }))}
        />

        <div className="mt-3 text-xs text-gray-600">
          Duplicate check (phone/email) + merge popup can be added here.
        </div>
      </Card>
    </div>
  );
}
