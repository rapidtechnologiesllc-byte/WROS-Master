// Candidate search/listing and selection screen.
import { useEffect, useMemo, useState } from "react";
import { Plus, Users, AlertCircle, CheckCircle, X, Linkedin } from "lucide-react";
import {
  Button,
  Card,
  StatusBadge,
  Table,
} from "../components/ui";
import CandidateEditModal from "./CandidateEditModal";
import LinkedInAddCandidateModal from "../components/LinkedInAddCandidateModal";
import {
  getAllCandidates,
  getCandidateStatus,
  updateCandidateStatus,
} from "../services/api/candidates";
import ScreenErrorDisplay from "../components/ScreenErrorDisplay";
import { Table as AntTable } from "antd";
import { useNavigate } from "react-router-dom";
import CandidateActionMenu from "../components/ui/CandidateActionMenu";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { updateCandidateThunderEnabled } from "../services/api/candidates";

// Account status of an archived candidate (backend: candidate_contact_policy.ARCHIVED_STATUS)
const ARCHIVED_STATUS = "Inactive";
// Rows come from two shapes: the mapped list (id, accountStatus) and /candidates/all
// (candidate_id, status = account status)
const rowId = (c) => c.id || c.candidate_id || c.candidateID;
const accountStatusOf = (c) => c.accountStatus || (["Active", "Inactive"].includes(c.status) ? c.status : "");
const isArchived = (c) => accountStatusOf(c) === ARCHIVED_STATUS;

export default function CandidateSearch({
  candidates,
  jobs,
  selectedCandidateId,
  setSelectedCandidateId,
  setCandidateRecord,
  selectedJobId,
  setSelectedJobId,
  onCreateCandidate,
  onMatchingJobs,
  onInterviewSchedule,
  onUpdateCandidate,
  onDeleteCandidate,
  onFetchCandidateById,
  setSelectedCandidate,
  setCandidateDetailsDefaultTab,
  setAutoOpenSchedule,
  onRefreshCandidates,
}) {
  const [query] = useState("");
  const [editCandidateId, setEditCandidateId] = useState("");
  const [overrideEditingCandidate, setOverrideEditingCandidate] =
    useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [candidateList, setCandidateList] = useState(candidates || []);
  const [loading, setLoading] = useState(false);
  const [screenError, setScreenError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [linkedInOpen, setLinkedInOpen] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const navigate = useNavigate();
  const isAntTableRole =
    hasPermission("candidates", "view") ||
    hasPermission("candidates", "edit");

  const handleThunderToggle = async (candidateId, currentValue) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await updateCandidateThunderEnabled(candidateId, !currentValue).catch(e => { throw e; });
      setCandidateList((prev) =>
        prev.map((c) =>
          c.candidate_id === candidateId
            ? { ...c, thunder_enabled: !currentValue }
            : c
        )
      );
      setActionSuccess(!currentValue ? "Thunder processing enabled" : "Thunder processing disabled");
    } catch (err) {
      const errorMsg = err?.message || "Unknown error updating Thunder configuration";
      setActionError(`Failed to update Thunder configuration: ${errorMsg}`);
      console.error("[CandidateSearch] Thunder toggle failed:", err);
    }
  };

  useEffect(() => {
    // Refresh the candidate list on mount
    if (hasPermission("candidates", "edit")) {
      fetchApprovalCandidates();
    }
  }, []);

  const fetchApprovalCandidates = async () => {
    try {
      setLoading(true);
      // Refresh all candidates to show newly created ones
      if (hasPermission("candidates", "view")) {
        const allData = await getAllCandidates().catch(e => { throw e; });
        setCandidateList(allData?.candidates || []);
      }
    } catch (err) {
      setScreenError(err?.message || "Failed to fetch candidates");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const refreshAllCandidates = async () => {
    try {
      setLoading(true);
      // Fetch all candidate lists to ensure UI is in sync
      const allData = await getAllCandidates().catch(e => { throw e; });
      setCandidateList(allData?.candidates || []);
    } catch (err) {
      setScreenError(err?.message || "Failed to refresh candidates");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Normalize candidates from prop - ensure consistent field names
    const normalizedCandidates = candidates?.map(c => ({
      ...c,
      candidate_name: c.candidate_name || c.name,
      candidate_email: c.candidate_email || c.email,
      candidate_mobile: c.candidate_mobile || c.phone,
      candidate_id: c.candidate_id || c.id,
    })) || [];
    setCandidateList([...normalizedCandidates]);
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

  const archivedCount = useMemo(() => candidateList.filter(isArchived).length, [candidateList]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    // Archived candidates stay out of the list unless "Show archived" is on
    const visible = showArchived ? candidateList : candidateList.filter((c) => !isArchived(c));

    if (!q) return visible;
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
    return visible.filter((candidate) => {
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
  }, [candidateList, query, showArchived]);

  const handleCandidateStatus = async (candidateId) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      const result = await updateCandidateStatus(candidateId, { status: "Active", pipeline_status: "Pre-Onboarding" }).catch(e => { throw e; });
      if (result?.status === "success") {
        setActionSuccess(
          `Candidate ${result?.data?.candidate_name} moved to Pre-Onboarding`,
        );
        const candidateStatus = await getCandidateStatus(candidateId).catch(e => { throw e; });
        setCandidateList((prev) =>
          prev.map((c) =>
            rowId(c) === candidateId
              ? {
                  ...c,
                  accountStatus: candidateStatus?.status,
                  pipelineStatus: candidateStatus?.pipeline_status,
                }
              : c,
          ),
        );
      }
    } catch (err) {
      setScreenError(err?.message || "Failed to update candidate status");
      throw err;
    }
  };

  // Archive (status Inactive) / Unarchive (Active) from the row menu
  const handleActiveStatus = async (status, candidateId) => {
    setActionError(null);
    setActionSuccess(null);
    setOpenMenuId(null);
    try {
      const result = await updateCandidateStatus(candidateId, { status });
      if (result?.status !== "success") {
        throw new Error(result?.message || "The server did not confirm the change");
      }
      const name = result?.data?.candidate_name || "Candidate";
      setActionSuccess(status === ARCHIVED_STATUS ? `${name} archived` : `${name} unarchived`);
      setCandidateList((prev) =>
        prev.map((c) =>
          rowId(c) === candidateId ? { ...c, accountStatus: status } : c,
        ),
      );
    } catch (err) {
      setActionError(`Could not ${status === ARCHIVED_STATUS ? "archive" : "unarchive"} the candidate: ${err?.message || "unknown error"}`);
    }
  };

  const mapCandidate = (data, source) => {
    if (source === "common") {
      return {
        id: rowId(data),
        name: data.name || data.candidate_name,
        email: data.email || data.candidate_email,
        phone: data.phone || data.candidate_mobile,
        status: data.pipelineStatus || data.pipline_status,
        archived: isArchived(data),
      };
    }

    if (source === "ant") {
      return {
        id: rowId(data),
        name: data.candidate_name,
        email: data.candidate_email,
        phone: data.candidate_mobile,
        status: data.pipline_status,
        archived: isArchived(data),
      };
    }

    return {};
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "candidate_name",
      width: 300,
      render: (value, record) => {
        // Handle both transformed (name) and original (candidate_name) field names
        const name = value || record?.name || record?.candidate_name || 'N/A';
        const candidateId = record?.candidate_id || record?.id;

        return (
          <span className="inline-flex items-center gap-1.5">
            <button
              className="font-semibold text-gray-900 transition-colors hover:text-black hover:underline"
              onClick={() => {
                navigate(`/candidates/${candidateId}`);
              }}
            >
              {name}
            </button>
            {record?.is_guidewire_candidate ? (
              <span
                title="Guidewire candidate — nurture for conversion"
                className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700"
              >
                Guidewire
              </span>
            ) : null}
            {isArchived(record) ? (
              <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold text-gray-700">
                Archived
              </span>
            ) : null}
          </span>
        );
      },
    },
    {
      title: "Contact",
      dataIndex: "candidate_email",
      width: 200,
      render: (value, record) => {
        // Handle both transformed (email, phone) and original (candidate_email, candidate_mobile) field names
        const email = value || record?.email || record?.candidate_email || "-";
        const phone = record?.candidate_mobile || record?.phone || record?.mobile || "-";

        return (
          <div className="space-y-1">
            <div className="text-sm text-gray-900">
              {phone && phone !== "-" ? `${phone}` : "-"}
            </div>
            <div className="text-sm text-gray-600">{email}</div>
          </div>
        );
      },
    },
    {
      title: "Thunder",
      dataIndex: "thunder_enabled",
      width: 120,
      render: (_, record) => {
        const isEnabled = record?.thunder_enabled !== false;
        return (
          <button
            onClick={() => handleThunderToggle(record?.candidate_id, record?.thunder_enabled ?? true)}
            title={isEnabled ? "Click to unsubscribe from Thunder" : "Thunder is disabled"}
            className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${
              isEnabled
                ? "bg-green-500 hover:bg-green-600"
                : "bg-gray-300 hover:bg-gray-400 cursor-not-allowed"
            }`}
          >
            <span
              className={`inline-block h-6 w-6 transform rounded-full bg-white shadow-md transition-transform ${
                isEnabled ? "translate-x-7" : "translate-x-1"
              }`}
            />
            <span className="absolute left-2 text-[10px] font-bold text-white opacity-0">
              ON
            </span>
            <span className={`absolute right-2 text-[10px] font-bold transition-opacity ${
              isEnabled ? "opacity-0" : "opacity-100 text-gray-600"
            }`}>
              OFF
            </span>
          </button>
        );
      },
    },
    {
      title: "Job Title",
      dataIndex: "candidateJobTitle",
      width: 120,
      render: (_, record) => (
        <div className="text-sm text-gray-700">
          {record?.candidateJobTitle || record?.job_title || "-"}
        </div>
      ),
    },
    {
      title: "Location",
      dataIndex: "candidateCurrentLocation",
      width: 120,
      render: (_, record) => (
        <div className="text-sm text-gray-700">
          {record?.candidateCurrentLocation || record?.candidate_current_location || "-"}
        </div>
      ),
    },
    {
      title: "Status",
      dataIndex: "pipline_status",
      width: 100,
    },
    {
      title: "More Options",
      key: "more_options",
      width: 60,
      render: (_, record) => {
        return (
          <CandidateActionMenu
            candidate={mapCandidate(record, "ant")}
            openMenuId={openMenuId}
            setOpenMenuId={setOpenMenuId}
            handleActiveStatus={handleActiveStatus}
            handleCandidateStatus={handleCandidateStatus}
            setCandidateList={setCandidateList}
          />
        );
      },
    },
  ];

  // Determine which candidate data to show based on permissions
  let tableData = [];
  if (hasPermission("candidates", "view")) {
    // The unified list (newly created candidates show at once), minus archived ones
    // unless "Show archived" is on
    tableData = filtered;
  }

  return (
    <>
      <div className="grid gap-6">
        <ScreenErrorDisplay
          error={screenError}
          onDismiss={() => setScreenError(null)}
        />

        {/* Action Error Banner */}
        {actionError && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-700 text-sm font-medium">{actionError}</p>
              </div>
              <button
                onClick={() => setActionError(null)}
                className="text-red-600 hover:text-red-800 flex-shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Action Success Banner */}
        {actionSuccess && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-green-700 text-sm font-medium">{actionSuccess}</p>
              </div>
              <button
                onClick={() => setActionSuccess(null)}
                className="text-green-600 hover:text-green-800 flex-shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        <LinkedInAddCandidateModal
          open={linkedInOpen}
          onClose={() => setLinkedInOpen(false)}
          onQueued={() => refreshAllCandidates().catch(() => {})}
        />

        <div className="space-y-6">
          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm text-gray-500">
                  Total Candidates: {candidateList.length - archivedCount}
                  {archivedCount > 0 ? ` (+${archivedCount} archived)` : ""}
                </p>
                {archivedCount > 0 && (
                  <label className="mt-2 inline-flex cursor-pointer items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={showArchived}
                      onChange={(e) => setShowArchived(e.target.checked)}
                    />
                    Show archived
                  </label>
                )}
              </div>

              <div className="flex items-center gap-2">
                {hasPermission("candidates", "create") && (
                  <>
                    <Button
                      variant="secondary"
                      onClick={() => setLinkedInOpen(true)}
                      className="h-[46px] shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
                    >
                      <Linkedin className="h-4 w-4" /> Add from LinkedIn
                    </Button>
                    <Button
                      onClick={onCreateCandidate}
                      className="h-[46px] shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
                    >
                      <Plus className="h-4 w-4" /> Add Candidate
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {isAntTableRole ? (
          <Card
            title={`Candidates (${tableData.length})`}
            icon={<Users className="h-4 w-4 text-gray-700" />}
            className="shadow-sm"
          >
            <AntTable
              columns={columns}
              dataSource={tableData}
              pagination={false}
              bordered
              loading={loading}
            />
          </Card>
        ) : (
          <Table
            columns={[
              { key: "name", header: "Name" },
              { key: "contact", header: "Contact" },
              { key: "jobTitle", header: "Job Title" },
              { key: "pipeline", header: "Pipeline" },
              { key: "businessUnit", header: "Business Unit" },
              { key: "actions", header: "" },
            ]}
            rows={filtered.map((c) => ({
              name: (
                <button
                  className="font-semibold text-gray-900 transition-colors hover:text-black hover:underline"
                  onClick={() => {
                    navigate(`/candidates/${c.candidate_id}`);
                  }}
                >
                  {c.candidate_name}
                </button>
              ),
              contact: (
                <div className="space-y-1 text-xs text-gray-700">
                  <div>{c.candidate_email || c.email}</div>
                  <div>{c.candidate_mobile || c.phone || "-"}</div>
                </div>
              ),
              jobTitle: c.job_title || c.candidateJobTitle || "-",
              pipeline: c.pipline_status || c.pipelineStatus ? (
                <StatusBadge status={c.pipline_status || c.pipelineStatus} />
              ) : (
                <span className="text-xs text-gray-400">—</span>
              ),
              businessUnit: c.business_unit_name ? (
                <span className="text-xs font-medium text-gray-900">{c.business_unit_name}</span>
              ) : (
                <span className="text-xs text-gray-400">Unassigned</span>
              ),
              status: <StatusBadge status={c.status} />,
              actions: (
                <CandidateActionMenu
                  candidate={mapCandidate(c, "common")}
                  openMenuId={openMenuId}
                  setOpenMenuId={setOpenMenuId}
                  handleActiveStatus={handleActiveStatus}
                  handleCandidateStatus={handleCandidateStatus}
                  setCandidateList={setCandidateList}
                />
              ),
            }))}
          />
        )}

        {editingCandidate ? (
          <CandidateEditModal
            candidate={editingCandidate}
            onClose={() => {
              setEditCandidateId("");
              setOverrideEditingCandidate(null);
            }}
            onUpdateCandidate={onUpdateCandidate}
            onRefreshCandidates={onRefreshCandidates}
          />
        ) : null}
      </div>
    </>
  );
}
