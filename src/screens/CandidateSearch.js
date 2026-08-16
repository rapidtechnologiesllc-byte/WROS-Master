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
import { Table as AntTable } from "antd";
import {
  AcceptButton,
  ButtonDiv,
  RejectButton,
} from "../styles/CandidateSearchStyles";
import {
  managerReviewApprove,
  managerReviewList,
} from "../services/api/preOnboarding";
import { sendPlainEmail, sendLoginCredentials } from "../services/api/email";
import { getEmailBodyHTML } from "../utils/preboardingEmailTemplate";
import { getRejectionEmailHTML } from "../utils/rejectionEmailTemplate";
import { useNavigate } from "react-router-dom";
import CandidateActionMenu from "../components/ui/CandidateActionMenu";

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
  const [candidateList, setCandidateList] = useState(candidates);
  const [openMoveDrawer, setOpenMoveDrawer] = useState(false);
  const [preonboardingModal, setPreonboardingModal] = useState(false);
  const currentRole = localStorage.getItem("permission_role");
  const [candidateActions, setCandidateActions] = useState({});
  const [preOnboardingCandidates, setPreOnboardingCandidates] = useState([]);
  const [managerCandidatesList, setManagerCandidatesList] = useState([]);
  const [approvalCandidates, setApprovalCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const isAntTableRole = [
    "Hiring Manager",
    "HR Operations",
    "HR Manager",
  ].includes(currentRole);

  useEffect(() => {
    const role = localStorage.getItem("permission_role");
    if (role === 'HR Manager') {
      fetchCandidates();
    }
  }, []);

  useEffect(() => {
    const role = localStorage.getItem("permission_role");
    if (role === 'HR Manager') {
      offerApprovalCandidates();
    }
  }, []);

  useEffect(() => {
    let currentRole = localStorage.getItem("permission_role");
    if (currentRole === "Hiring Manager") {
      fetchApprovalCandidates();
    }
  }, []);

  const fetchApprovalCandidates = async () => {
    try {
      setLoading(true);
      const canData = await managerReviewList();
      setManagerCandidatesList(canData?.candidates);
    } catch (err) {
      toast.error(err?.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchCandidates = async () => {
    try {
      setLoading(true);
      const canData = await getAllCandidates();
      const filteredCandidates = canData?.candidates;
      setPreOnboardingCandidates(filteredCandidates);
    } catch (err) {
      console.log(err);
    } finally {
      setLoading(false);
    }
  };

  const offerApprovalCandidates = async () => {
    try {
      setLoading(true);
      const canData = await getAllCandidates();

      const filteredCandidates =
        canData?.candidates?.filter(
          (candidate) =>
            candidate.pipline_status?.toLowerCase() ===
            "OfferApproval".toLowerCase(),
        ) || [];
      setApprovalCandidates(filteredCandidates);
    } catch (err) {
      console.log(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setCandidateList([...candidates]);
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
                  accountStatus: candidateStatus?.status,
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

  const handleActiveStatus = async (status, candidateId) => {
    try {
      const result = await updateCandidateStatus(candidateId, {
        status: status,
      });
      if (result?.status === "success") {
        toast.success(`Candidate ${result?.data?.candidate_name} is Archvied`);
        const candidateStatus = await getCandidateStatus(candidateId);
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
    } catch (err) {}
  };

  const handlePreOnboardingAction = async (record, action) => {
    try {
      const res = await managerReviewApprove(record, action);
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
          const emailSend = await sendPlainEmail({
            toEmail: record?.candidate_email,
            subject: "Pre-Onboarding Task",
            bodyContent: getEmailBodyHTML(record?.candidate_name),
            isHtml: true,
          });
          await sendLoginCredentials(record?.candidate_id);
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
      toast.error(
        action === "Approve"
          ? "Candidate already moved to Pre-Onboarding"
          : "Failed to reject candidate",
      );
    }
  };

  const managerRejectCandidate = async (record) => {
    try {
      const result = await updateCandidateStatus(record?.candidate_id, {
        status: "Active",
        pipeline_status: "Pre-onboarding-Approval",
      });
      if (result?.status === "success") {
        await fetchCandidates();
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
          await sendPlainEmail({
            toEmail: record?.candidate_email,
            subject: "Update on Your Application",
            bodyContent: getRejectionEmailHTML(record?.candidate_name),
            isHtml: true,
          });

          toast.success("Rejection email sent successfully");
        } catch (emailError) {
          console.error("Failed to send rejection email", emailError);

          toast.warning("Candidate rejected, but email could not be sent");
        }
      }
    } catch (err) {
      toast.error(err?.message);
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
      render: (_, record) => {
        return (
          <span className="inline-flex items-center gap-1.5">
            <button
              className="font-semibold text-gray-900 transition-colors hover:text-black hover:underline"
              onClick={() => {
                navigate(`/candidates/${record.candidate_id}`);
              }}
            >
              {record?.candidate_name}
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
      width: 80,
    },
    {
      title: "Job Title",
      dataIndex: "job_title",
      width: 80,
    },
    {
      title: "Pipeline",
      dataIndex: "pipline_status",
      width: 80,
    },
    {
      title: "Status",
      dataIndex: "status",
      width: 80,
    },
    ...(currentRole === "Hiring Manager"
      ? [
          {
            title: "Action",
            key: "action",
            render: (_, record) => {
              const isApproved = record?.pipeline_status === "Pre-Onboarding";
              return (
                <ButtonDiv>
                  <AcceptButton
                    disabled={isApproved}
                    onClick={() => handlePreOnboardingAction(record, "Approve")}
                  >
                    {isApproved ? "Approved" : "Accept"}
                  </AcceptButton>
                  <RejectButton onClick={() => managerRejectCandidate(record)}>
                    Reject
                  </RejectButton>
                </ButtonDiv>
              );
            },
          },
        ]
      : []),
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

  const tableDataMap = {
    "Hiring Manager": managerCandidatesList,
    "HR Manager": approvalCandidates,
    "HR Operations": preOnboardingCandidates,
  };
  const tableData = tableDataMap[currentRole] || [];

  return (
    <>
      <div className="grid gap-6">
        <div className="space-y-6">
          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm text-gray-500">
                  Total Candidates: {candidateList.length}
                </p>
              </div>

              <div className="flex items-center gap-2">
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
                    navigate(`/candidates/${c.id}`);
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
