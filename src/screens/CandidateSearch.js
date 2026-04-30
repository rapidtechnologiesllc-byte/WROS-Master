// Candidate search/listing and selection screen.
import { useEffect, useMemo, useState } from "react";
import { Plus, Search, Users } from "lucide-react";
import {
  Button,
  Card,
  Input,
  Select,
  StatusBadge,
  Table,
} from "../components/ui";
import CandidateEditModal from "./CandidateEditModal";
import {
  getCandidateStatus,
  updateCandidateStatus,
} from "../services/api/candidates";
import { toast } from "react-toastify";

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
  onFetchCandidateById,
  setScreen,
  setSelectedCandidate,
  onRefreshCandidates,
}) {
  const [query, setQuery] = useState("");
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editCandidateId, setEditCandidateId] = useState("");
  const [overrideEditingCandidate, setOverrideEditingCandidate] =
    useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [candidateList, setCandidateList] = useState(candidates);

  useEffect(() => {
    setCandidateList(candidates);
  }, [candidates]);

  const editingCandidate = useMemo(() => {
    if (
      overrideEditingCandidate &&
      String(overrideEditingCandidate.id || "") ===
        String(editCandidateId || "")
    ) {
      return overrideEditingCandidate;
    }
    return candidateList.find((c) => c.id === editCandidateId) || null;
  }, [candidateList, editCandidateId, overrideEditingCandidate]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return candidateList;
    return candidateList.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        c.phone.toLowerCase().includes(q),
    );
  }, [candidateList, query]);

  const handleCandidateStatus = async (candidateId) => {
    try {
      const result = await updateCandidateStatus(candidateId, {
        status: "Active",
        pipeline_status: "Pre-Onboarding",
      });
      if (result?.status === "success") {
        toast.success(
          `Candidate ${result?.data?.candidate_name} moved to Pre-Onboarding`,
        );
        const candidateStatus = await getCandidateStatus(candidateId);
        setCandidateList((prev) =>
          prev.map((c) =>
            c.id === candidateId
              ? {
                  ...c,
                  status: candidateStatus?.status,
                  pipelineStatus: candidateStatus?.pipeline_status,
                }
              : c,
          ),
        );
      }
    } catch (err) {
      toast.error(err);
      console.log(err);
    }
  };

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
            { key: "pipeline", header: "Pipeline" },
            { key: "account", header: "Account" },
            { key: "status", header: "Verified" },
            { key: "actions", header: "" },
          ]}
          rows={filtered.map((c) => ({
            name: (
              <button
                className="font-semibold hover:underline"
                onClick={async () => {
                  setSelectedCandidateId(c.id);

                  let finalCandidate = c;

                  if (onFetchCandidateById) {
                    try {
                      const fresh = await onFetchCandidateById(c.id);
                      if (fresh) {
                        finalCandidate = fresh;
                      }
                    } catch (err) {}
                  }

                  setSelectedCandidate(finalCandidate);
                  setScreen("candidateDetails");
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
            pipeline: c.pipelineStatus ? (
              <StatusBadge status={c.pipelineStatus} />
            ) : (
              <span className="text-xs text-gray-400">—</span>
            ),
            account: c.accountStatus ? (
              <StatusBadge status={c.accountStatus} />
            ) : (
              <span className="text-xs text-gray-400">—</span>
            ),
            status: <StatusBadge status={c.status} />,
            actions: (
              <div className="relative">
                <button
                  className="px-2 py-1 text-gray-600 hover:text-black"
                  onClick={() =>
                    setOpenMenuId(openMenuId === c.id ? null : c.id)
                  }
                >
                  ⋮
                </button>
                {openMenuId === c.id && (
                  <div className="absolute right-0 mt-2 w-40 bg-white border rounded shadow-md z-10">
                    <button
                      className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
                      onClick={() => {
                        handleCandidateStatus(c?.id);
                        setOpenMenuId(null);
                      }}
                    >
                      Pre Onboarding
                    </button>
                  </div>
                )}
              </div>
            ),
          }))}
        />

        <div className="mt-3 text-xs text-gray-600">
          Duplicate check (phone/email) + merge popup can be added here.
        </div>
      </Card>

      {false && editingCandidate ? (
        <CandidateEditModal
          candidate={editingCandidate}
          onClose={() => {
            setEditModalOpen(false);
            setEditCandidateId("");
            setOverrideEditingCandidate(null);
          }}
          onUpdateCandidate={onUpdateCandidate}
          onRefreshCandidates={onRefreshCandidates}
        />
      ) : null}
    </div>
  );
}
