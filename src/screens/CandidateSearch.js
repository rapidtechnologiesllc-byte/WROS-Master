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
import { sendPlainEmail } from "../services/api/email";
import { getEmailBodyHTML } from "../utils/preboardingEmailTemplate";

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
  const [openMoveDrawer, setOpenMoveDrawer] = useState(false);
  const [preonboardingModal, setPreonboardingModal] = useState(false);
  const currentRole = localStorage.getItem("hrms_role");
  const [candidateActions, setCandidateActions] = useState({});
  const [preOnboardingCandidates, setPreOnboardingCandidates] = useState([]);
  const isAntTableRole =
    currentRole === "HIRING MANAGER" || currentRole === "HR MANAGER";

  useEffect(() => {
    let currentRole = localStorage.getItem("hrms_role");
    if (currentRole === "HIRING MANAGER") {
      const data = async () => {
        try {
          const canData = await managerReviewList();
          setCandidateList(canData?.candidates);
        } catch (err) {
          console.log(err);
        }
      };
      data();
    }
  }, []);

  useEffect(() => {
    let currentRole = localStorage.getItem("hrms_role");
    if (currentRole === "HR MANAGER") {
      const fetchCandidates = async () => {
        try {
          const canData = await getAllCandidates();

          const filteredCandidates =
            canData?.candidates?.filter(
              (candidate) =>
                candidate.pipline_status?.toLowerCase() ===
                "pre-onboarding".toLowerCase(),
            ) || [];

          setPreOnboardingCandidates(filteredCandidates);
        } catch (err) {
          console.log(err);
        }
      };

      fetchCandidates();
    }
  }, []);

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
      console.log("Approve Response:", res);

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
            isHtml: false,
          });

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
        setCandidateList((prev) =>
          prev.map((candidate) =>
            candidate.candidate_id === result.candidate_id
              ? { ...candidate, ...result }
              : candidate,
          ),
        );

        toast.success(
          `Candidate ${record?.candidate_name} rejected successfully`,
        );
      }
    } catch (err) {
      toast.error(err?.message);
    }
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "candidate_name",
      render: (_, record) => {
        return (
          <button
            className="font-semibold text-gray-900 transition-colors hover:text-black hover:underline"
            onClick={async () => {
              setSelectedCandidateId(record?.candidate_id);
              let finalCandidate = record;
              if (onFetchCandidateById) {
                try {
                  const fresh = await onFetchCandidateById(
                    record?.candidate_id,
                  );
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
            {record?.candidate_name}
          </button>
        );
      },
    },
    {
      title: "Contact",
      dataIndex: "candidate_email",
    },
    {
      title: "Job Title",
      dataIndex: "job_title",
    },
    {
      title: "Pipeline",
      dataIndex: "pipeline_status",
    },
    {
      title: "Status",
      dataIndex: "status",
    },
    ...(currentRole === "HIRING MANAGER"
      ? [
          {
            title: "Action",
            key: "action",
            render: (_, record) => {
              const action = candidateActions[record?.candidate_id];

              return (
                <ButtonDiv>
                  <AcceptButton
                    disabled={action === "Approve"}
                    onClick={() => handlePreOnboardingAction(record, "Approve")}
                  >
                    Accept
                  </AcceptButton>

                  <RejectButton
                    disabled={action === "Reject"}
                    onClick={() => managerRejectCandidate(record)}
                  >
                    Reject
                  </RejectButton>
                </ButtonDiv>
              );
            },
          },
        ]
      : []),
  ];

  const tableData =
    currentRole === "HR MANAGER" ? preOnboardingCandidates : filtered;

  return (
    <>
      <div className="grid gap-6">
        <div className="space-y-6">
          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  Candidates
                </h3>
                <p className="text-sm text-gray-500">
                  Total Candidates: {candidateList.length}
                </p>
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
            />
          </Card>
        ) : (
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
                          window.open(
                            `https://wa.me/${cleanedPhone}`,
                            "_blank",
                          );
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
                          handleActiveStatus("Inactive", c?.id);
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
                      <button
                        className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
                        onClick={() => {
                          setOpenMoveDrawer(true);
                        }}
                      >
                        Move Stage
                      </button>
                      <MoveStageDrawer
                        open={openMoveDrawer}
                        onClose={() => setOpenMoveDrawer(false)}
                        onSubmit={(stage) => {
                          setCandidateList((prev) =>
                            prev.map((c) =>
                              c.id === stage?.candidate_id
                                ? {
                                    ...c,
                                    status: stage?.status,
                                    pipelineStatus: stage?.pipeline_status,
                                  }
                                : c,
                            ),
                          );
                        }}
                        data={c}
                      />
                    </div>
                  )}
                </div>
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
