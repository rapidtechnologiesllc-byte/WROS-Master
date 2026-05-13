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
  setCandidateDetailsDefaultTab,
  setAutoOpenSchedule,
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

    const getSearchableText = (candidate) =>
      [candidate?.name, candidate?.email, candidate?.phone, candidate?.jobTitle]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

    const matchesKeyword = (candidate, keyword) => {
      const cleanKeyword = keyword.trim().toLowerCase();
      if (!cleanKeyword) return true;

      return getSearchableText(candidate).includes(cleanKeyword);
    };

    return candidateList.filter((candidate) => {
      if (q.includes(" and ")) {
        return q
          .split(" and ")
          .every((keyword) => matchesKeyword(candidate, keyword));
      }

      if (q.includes(" or ")) {
        return q
          .split(" or ")
          .some((keyword) => matchesKeyword(candidate, keyword));
      }

      if (q.includes(" not ")) {
        const [includeKeyword, excludeKeyword] = q.split(" not ");

        return (
          matchesKeyword(candidate, includeKeyword) &&
          !matchesKeyword(candidate, excludeKeyword)
        );
      }

      return matchesKeyword(candidate, q);
    });
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
    <div className="grid gap-6">
      <div className="space-y-6">
        <div className="rounded-2xl border border-gray-200 bg-white p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="w-full lg:w-[30%]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search by candidate name, email, job title or phone number"
                  className="w-full rounded-xl border border-gray-200 bg-white py-3 pl-10 pr-4 text-sm outline-none transition-all focus:border-gray-400"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                onClick={onMatchingJobs}
                className="h-[46px] border-blue-100 bg-blue-50 text-blue-700 transition-all duration-200 hover:border-blue-200 hover:bg-blue-100"
              >
                Show Matching Jobs
              </Button>

              <Button
                onClick={onCreateCandidate}
                className="h-[46px] shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
              >
                <Plus className="h-4 w-4" /> Add Candidate
              </Button>
            </div>
          </div>
        </div>
      </div>

      <Card
        title={`Candidates (${filtered.length})`}
        icon={<Users className="h-4 w-4 text-gray-700" />}
        className="shadow-sm"
      >
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">
              Candidate Directory
            </h3>
            <p className="text-xs text-gray-500">
              View and manage recruitment candidates
            </p>
          </div>
        </div>
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
                className="font-semibold text-gray-900 transition-colors hover:text-black hover:underline"
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
                  setCandidateDetailsDefaultTab?.("profile");
                  setAutoOpenSchedule?.(false);
                  setScreen("candidateDetails");
                }}
              >
                {c.name}
              </button>
            ),
            contact: (
              <div className="space-y-1 text-xs text-gray-700">
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
                  <div className="absolute right-0 z-10 mt-2 w-56 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg">
                    <button
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                      onClick={() => {
                        setSelectedCandidateId(c?.id);
                        setSelectedCandidate(c);
                        setCandidateDetailsDefaultTab?.("profile");
                        setAutoOpenSchedule?.(true);
                        setScreen("candidateDetails");
                        setOpenMenuId(null);
                      }}
                    >
                      Schedule Interview
                    </button>
                    <button
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                      onClick={() => {
                        const email = c?.email?.trim();

                        if (!email) {
                          return;
                        }

                        const subject = encodeURIComponent(
                          "Regarding your application",
                        );

                        const body = encodeURIComponent(
                          `Hi ${c?.name || "Candidate"},\n\n`,
                        );

                        const to = encodeURIComponent(email);

                        const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${to}&su=${subject}&body=${body}`;

                        const mailtoUrl = `mailto:${to}?subject=${subject}&body=${body}`;

                        const openedWindow = window.open(
                          gmailUrl,
                          "_blank",
                          "noopener,noreferrer",
                        );

                        if (!openedWindow) {
                          window.location.href = mailtoUrl;
                        }

                        setOpenMenuId(null);
                      }}
                    >
                      Send Email
                    </button>
                    <button
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!c?.phone}
                      onClick={() => {
                        if (!c?.phone) return;

                        const cleanedPhone = c.phone.replace(/\D/g, "");

                        if (!cleanedPhone) {
                          return;
                        }

                        window.open(`https://wa.me/${cleanedPhone}`, "_blank");
                        setOpenMenuId(null);
                      }}
                    >
                      Message on WhatsApp
                    </button>
                    <button
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
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
                        setCandidateDetailsDefaultTab?.("feedback");
                        setScreen("candidateDetails");
                        setOpenMenuId(null);
                      }}
                    >
                      Add Feedback
                    </button>
                    <button
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                      onClick={() => {
                        console.log("Archive candidate:", c?.id);

                        setOpenMenuId(null);
                      }}
                    >
                      Archive
                    </button>
                    <button
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
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
      </Card>

      {editingCandidate ? (
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
