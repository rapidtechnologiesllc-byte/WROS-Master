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
  getAllCandidates,
  getCandidateStatus,
  updateCandidateStatus,
} from "../services/api/candidates";
import { toast } from "react-toastify";
import MoveStageDrawer from "../components/ui/MoveStageDrawer";
import ScreenErrorDisplay from "../components/ScreenErrorDisplay";
import { Table as AntTable } from "antd";
import {
  managerReviewApprove,
  managerReviewList,
} from "../services/api/preOnboarding";
import { sendPlainEmail, sendLoginCredentials } from "../services/api/email";
import { getEmailBodyHTML } from "../utils/preboardingEmailTemplate";
import { getRejectionEmailHTML } from "../utils/rejectionEmailTemplate";
import { useNavigate } from "react-router-dom";
import CandidateActionMenu from "../components/ui/CandidateActionMenu";
import { hasPermission } from "../utils/permissionsRbac";
import { updateCandidateThunderEnabled } from "../services/api/candidates";

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
  const [query, setQuery] = useState("");
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editCandidateId, setEditCandidateId] = useState("");
  const [overrideEditingCandidate, setOverrideEditingCandidate] =
    useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [candidateList, setCandidateList] = useState(candidates || []);
  const [openMoveDrawer, setOpenMoveDrawer] = useState(false);
  const [preonboardingModal, setPreonboardingModal] = useState(false);
  const [candidateActions, setCandidateActions] = useState({});
  const [preOnboardingCandidates, setPreOnboardingCandidates] = useState([]);
  const [managerCandidatesList, setManagerCandidatesList] = useState([]);
  const [approvalCandidates, setApprovalCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [screenError, setScreenError] = useState(null);
  const navigate = useNavigate();
  const isAntTableRole =
    hasPermission("candidates", "view") ||
    hasPermission("candidates", "edit");

  const handleThunderToggle = async (candidateId, currentValue) => {
    try {
      await updateCandidateThunderEnabled(candidateId, !currentValue).catch(e => { throw e; });
      setCandidateList((prev) =>
        prev.map((c) =>
          c.candidate_id === candidateId
            ? { ...c, thunder_enabled: !currentValue }
            : c
        )
      );
      toast.success(!currentValue ? "Thunder processing enabled" : "Thunder processing disabled");
    } catch (err) {
      const errorMsg = err?.message || "Unknown error updating Thunder configuration";
      toast.error(`Failed to update Thunder configuration: ${errorMsg}`);
      console.error("[CandidateSearch] Thunder toggle failed:", err);
    }
  };

  useEffect(() => {
    // Refresh all candidate lists on mount
    if (hasPermission("candidates", "view")) {
      fetchCandidates();
    }
    if (hasPermission("candidates", "edit")) {
      fetchApprovalCandidates();
    }
    if (hasPermission("offers", "view")) {
      offerApprovalCandidates();
    }
  }, []);

  const fetchApprovalCandidates = async () => {
    try {
      setLoading(true);
      const canData = await managerReviewList().catch(e => { throw e; });
      setManagerCandidatesList(canData?.candidates);
      // Also refresh all candidates to show newly created ones
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
      setPreOnboardingCandidates(allData?.candidates || []);

      const approvalData = await managerReviewList().catch(e => { throw e; });
      setManagerCandidatesList(approvalData?.candidates || []);

      const offerData = await getAllCandidates().catch(e => { throw e; });
      const filteredOffers = offerData?.candidates?.filter(
        (c) => c.pipline_status?.toLowerCase() === "OfferApproval".toLowerCase()
      ) || [];
      setApprovalCandidates(filteredOffers);
    } catch (err) {
      setScreenError(err?.message || "Failed to refresh candidates");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const fetchCandidates = async () => {
    try {
      setLoading(true);
      const canData = await getAllCandidates().catch(e => { throw e; });
      const filteredCandidates = canData?.candidates;
      setPreOnboardingCandidates(filteredCandidates);
    } catch (err) {
      console.log(err);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const offerApprovalCandidates = async () => {
    try {
      setLoading(true);
      const canData = await getAllCandidates().catch(e => { throw e; });

      const filteredCandidates =
        canData?.candidates?.filter(
          (candidate) =>
            candidate.pipline_status?.toLowerCase() ===
            "OfferApproval".toLowerCase(),
        ) || [];
      setApprovalCandidates(filteredCandidates);
    } catch (err) {
      console.log(err);
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
      const result = await updateCandidateStatus(candidateId, { status: "Active", pipeline_status: "Pre-Onboarding" }).catch(e => { throw e; });
      if (result?.status === "success") {
        toast.success(
          `Candidate ${result?.data?.candidate_name} moved to Pre-Onboarding`,
        );
        const candidateStatus = await getCandidateStatus(candidateId).catch(e => { throw e; });
        setCandidateList((prev) =>
          prev.map((c) =>
            c.id === candidateId
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
      console.log(err);
      throw err;
    }
  };

  const handleActiveStatus = async (status, candidateId) => {
    try {
      const result = await updateCandidateStatus(candidateId, {
        status: status,
      }).catch(e => { throw e; });
      if (result?.status === "success") {
        toast.success(`Candidate ${result?.data?.candidate_name} is Archvied`);
        const candidateStatus = await getCandidateStatus(candidateId).catch(e => { throw e; });
        setCandidateList((prev) =>
          prev.map((c) =>
            c.id === candidateId
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
      throw err;
    }
  };

  const handlePreOnboardingAction = async (record, action) => {
    try {
      const res = await managerReviewApprove(record, action).catch(e => { throw e; });
      if (res?.status === "success") {
        const updatedCandidate = res?.data;
        setCandidateList((prev) =>
          prev.map((candidate) =>
            candidate.candidate_id === updatedCandidate.candidate_id
              ? {
                  ...candidate,
                  pipeline_status: updatedCandidate.pipeline_status,
                  status: updatedCandidate.status,
                  updated_at: updatedCandidate.updated_at,
                }
              : candidate,
          ),
        );
        if (action === "Approve") {
          const emailSend = await sendPlainEmail({ toEmail: record?.candidate_email, subject: "Pre-Onboarding Task", bodyContent: getEmailBodyHTML(record?.candidate_name), isHtml: true }).catch(e => { throw e; });
          await sendLoginCredentials(record?.candidate_id).catch(e => { throw e; });
          if (emailSend?.status === "success") {
            toast.success(
              `Candidate ${record?.candidate_name} approved for Pre-Onboarding`,
            );
          }
        } else {
          toast.success(
            `Candidate ${record?.candidate_name} has been rejected`,
          );
        }
      }
    } catch (err) {
      setScreenError(
        action === "Approve"
          ? "Candidate already moved to Pre-Onboarding"
          : "Failed to reject candidate",
      );
      throw err;
    }
  };

  const managerRejectCandidate = async (record) => {
    try {
      const result = await updateCandidateStatus(record?.candidate_id, { status: "Active", pipeline_status: "Pre-onboarding-Approval" }).catch(e => { throw e; });
      if (result?.status === "success") {
        await fetchCandidates().catch(e => { throw e; });
        const updatedCandidate = result.data;
        setCandidateList((prev) =>
          prev.map((candidate) =>
            candidate.candidate_id === result?.candidate_id
              ? { ...candidate, ...result }
              : candidate,
          ),
        );

        toast.success(
          `Candidate ${record?.candidate_name} rejected successfully`,
        );

        try {
          await sendPlainEmail({ toEmail: record?.candidate_email, subject: "Update on Your Application", bodyContent: getRejectionEmailHTML(record?.candidate_name), isHtml: true }).catch(emailError => { console.error("Failed to send rejection email", emailError); toast.warning("Candidate rejected, but email could not be sent"); throw emailError; });
          toast.success("Rejection email sent successfully");
        } catch (emailError) {
          throw emailError;
        }
      }
    } catch (err) {
      setScreenError(err?.message || "Failed to process candidate");
    }
  };

  const mapCandidate = (data, source) => {
    if (source === "common") {
      return {
        id: data.id,
        name: data.name,
        email: data.email,
        phone: data.phone,
        status: data.pipelineStatus,
      };
    }

    if (source === "ant") {
      return {
        id: data.candidate_id,
        name: data.candidate_name,
        email: data.candidate_email,
        phone: data.candidate_mobile,
        status: data.pipline_status,
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
      width: 100,
      render: (_, record) => (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={record?.thunder_enabled ?? true}
            onChange={() => handleThunderToggle(record?.candidate_id, record?.thunder_enabled ?? true)}
            className="w-4 h-4"
          />
          <span className="text-xs text-gray-600">
            {record?.thunder_enabled !== false ? "Enabled" : "Disabled"}
          </span>
        </label>
      ),
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
    // Show all candidates from the unified list (includes all statuses)
    // This ensures newly created candidates are visible immediately
    tableData = candidateList || [];
  }

  return (
    <>
      <div className="grid gap-6">
        <ScreenErrorDisplay
          error={screenError}
          onDismiss={() => setScreenError(null)}
        />
        <div className="space-y-6">
          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm text-gray-500">
                  Total Candidates: {candidateList.length}
                </p>
              </div>

              <div className="flex items-center gap-2">
                {hasPermission("candidate.create") && (
                  <Button
                    onClick={onCreateCandidate}
                    className="h-[46px] shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
                  >
                    <Plus className="h-4 w-4" /> Add Candidate
                  </Button>
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
              setEditModalOpen(false);
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
