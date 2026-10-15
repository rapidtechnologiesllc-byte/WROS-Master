import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Label } from "../styles/Pre-onboardingModal";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { getAllJobs } from "../services/api/jobs";
import { Select } from "antd";
import { Card } from "../components/ui";
import { Table as AntTable } from "antd";
import { Users, AlertCircle, CheckCircle, X } from "lucide-react";
import {
  approveOfferLetter,
  cancelOfferLetter,
  getAllOffers,
  offerLetterById,
  offerLetterByJobId,
  releaseOfferApi,
} from "../services/api/offerLetters";
import {
  AcceptButton,
  ButtonDiv,
  RejectButton,
} from "../styles/CandidateSearchStyles";
import SignatureModal from "../components/ui/SignatureModal";
import { sendPlainEmail } from "../services/api/email";
import { EyeOutlined, DownloadOutlined } from "@ant-design/icons";
import {
  DownloadButton,
  DropdownContainer,
  OfferLetterButtonContainer,
  ViewButton,
} from "../styles/OfferListingStyles";
import RejectModal from "../components/ui/RejectModal";
import { updateCandidateStatus } from "../services/api/candidates";
import { getRejectionEmailHTML } from "../utils/rejectionEmailTemplate";
import { mapJobFromApi } from "../utils/jobMappers";

const OfferListing = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [loading, setLoading] = useState(false);
  const [offerDetails, setOfferDetails] = useState([]);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedOfferCandidate, setSelectedOfferCandidate] = useState(null);
  const [signatureLoading, setSignatureLoading] = useState(false);
  const [rejectModalShow, setRejectModalShow] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [statusSelected, setStatusSelected] = useState("");
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const canManageOffers = hasPermission("offer-letters", "edit");
  const offerStatusOptions = [
    { label: "Released", value: "Released" },
    { label: "AwaitingApproval", value: "AwaitingApproval" },
    { label: "Cancelled", value: "Cancelled" },
    { label: "Accepted", value: "Accepted" },
  ];

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        const refreshed = await getAllJobs();
        if (!isMounted) return;
        // No user directory is loaded on this screen; mapJobFromApi only
        // uses it to resolve owner names, which this list does not show.
        const mappedJobs = (refreshed?.jobs || []).map((j) =>
          mapJobFromApi(j, []),
        );
        setJobs(mappedJobs);
      } catch (err) {
        // Throwing here only produced an unhandled promise rejection; surface it.
        console.error("[OfferListing] Failed to load jobs:", err);
        if (isMounted) {
          setActionError(`Failed to load jobs: ${err?.message || "Unknown error"}`);
        }
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const fetchList = async () => {
      if (!selectedJob?.id) {
        setOfferDetails([]);
        return;
      }

      try {
        setLoading(true);
        const list = await offerLetterByJobId(selectedJob?.id || "");
        setOfferDetails(list?.offers);
      } catch (err) {
        console.error("[OfferListing] Failed to load offer letters:", err);
        setActionError(
          `Failed to load offer letters: ${err?.message || "Unknown error"}`,
        );
      } finally {
        setLoading(false);
      }
    };
    fetchList();
  }, [selectedJob]);

  useEffect(() => {
    const fetchOfferList = async () => {
      if (!statusSelected) {
        setOfferDetails([]);
        return;
      }
      try {
        setLoading(true);
        const list = await getAllOffers({ status: statusSelected });
        setOfferDetails(list?.offers);
      } catch (err) {
        console.error("[OfferListing] Failed to fetch offers:", err);
        setActionError(`Failed to fetch offers: ${err?.message || "Unknown error"}`);
      } finally {
        setLoading(false);
      }
    };
    fetchOfferList();
  }, [statusSelected]);

  const jobOptions = [
    { label: "Please select job", value: "", disabled: true },
    ...(jobs?.map((job) => ({
      label: job?.title,
      value: job?.id,
    })) || []),
  ];

  const sigatureModalHandler = (record) => {
    setSelectedOfferCandidate(record);
    setShowSignatureModal(true);
  };

  const downloadFile = async (id, fileName = "OfferLetter.docx") => {
    if (!id) {
      setActionError("Offer letter download url is not available");
      return;
    }
    try {
      const createOfferId = await offerLetterById(id);
      const response = await fetch(createOfferId?.download_url, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("hrms_token")}`,
        },
      });
      if (!response.ok) {
        setActionError("Failed to download offer letter.");
        return;
      }

      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
      setActionSuccess("Offer letter downloaded successfully");
    } catch (error) {
      console.error("[OfferListing] Offer letter download failed:", error);
      setActionError(`Download failed: ${error?.message || "Unknown error"}`);
    }
  };

  const cancelOfferHandler = (record) => {
    setSelectedOfferCandidate(record);
    setRejectModalShow(true);
  };

  const handleRejectOffer = async () => {
    try {
      const payload = { reason: rejectReason };
      const cancelOfferApi = await cancelOfferLetter(
        selectedOfferCandidate?.id,
        payload,
      );
      if (cancelOfferApi?.status !== "Success") {
        setActionError("Failed to cancel the offer letter");
        return;
      }
      const matchid = selectedOfferCandidate?.id;
      setOfferDetails((prev) =>
        prev.map((item) =>
          String(item?.id) === String(matchid)
            ? { ...item, offer_status: "Cancelled" }
            : item,
        ),
      );
      setRejectModalShow(false);
      setRejectReason("");

      const result = await updateCandidateStatus(
        selectedOfferCandidate?.candidate_id,
        {
          status: "Active",
          pipeline_status: "Applied",
        },
      );
      if (result?.status !== "success") {
        setActionError(
          "Offer cancelled, but the candidate status could not be reset",
        );
        return;
      }
      await sendPlainEmail({
        toEmail: selectedOfferCandidate?.candidate_email,
        subject: `Update on Your Application - ${selectedOfferCandidate?.position}`,
        bodyContent: getRejectionEmailHTML(
          selectedOfferCandidate?.candidate_name,
        ),
        isHtml: true,
      });
      setActionSuccess("Offer rejected successfully");
    } catch (err) {
      console.error("[OfferListing] Failed to reject offer:", err);
      setActionError(err?.message || "Failed to reject offer");
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
            onClick={() => {
              if (!record?.candidate_id) {
                setActionError("This offer has no linked candidate");
                return;
              }
              navigate(`/candidates/${record.candidate_id}`);
            }}
          >
            {record?.candidate_name}
          </button>
        );
      },
    },
    {
      title: "Offer Letter",
      key: "offer_letter",
      render: (_, record) => {
        return (
          <OfferLetterButtonContainer>
            <ViewButton
              onClick={() => window.open(record?.sharepoint_url, "_blank")}
            >
              <EyeOutlined style={{ marginRight: "6px" }} />
              View
            </ViewButton>

            <DownloadButton onClick={() => downloadFile(record?.id)}>
              <DownloadOutlined style={{ marginRight: "6px" }} />
              Download
            </DownloadButton>
          </OfferLetterButtonContainer>
        );
      },
    },
    {
      title: "Contact",
      dataIndex: "candidate_email",
    },
    {
      title: "Job Title",
      dataIndex: "position",
    },
    {
      title: "Offer Status",
      dataIndex: "offer_status",
    },
    ...(canManageOffers
      ? [
          {
            title: "Action",
            key: "action",
            render: (_, record) => {
              return (
                <ButtonDiv>
                  <AcceptButton
                    onClick={() => sigatureModalHandler(record)}
                    disabled={record?.offer_status === "Accepted"}
                  >
                    Accept
                  </AcceptButton>
                  <RejectButton
                    onClick={() => cancelOfferHandler(record)}
                    disabled={record?.offer_status === "Cancelled"}
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

  const sendEmailOffer = async (signaturePng, candidateData) => {
    try {
      const formData = new FormData();
      formData.append("offer_id", candidateData?.id);
      formData.append("signature", signaturePng);
      const offerApproveApi = await approveOfferLetter(
        candidateData?.id,
        formData,
      );
      if (offerApproveApi?.status === "success") {
        const releasOffer = await releaseOfferApi(candidateData?.id);
        if (releasOffer?.status === "success") {
          setActionSuccess("Offer Approved and released successfully");
        } else {
          setActionError("Offer approved, but releasing it failed");
        }
      } else {
        setActionError("Failed to approve the offer letter");
      }
    } catch (error) {
      console.error("[OfferListing] Failed to approve/release offer:", error);
      setActionError(error?.message || "Failed to approve the offer letter");
    }
  };

  const handleSignatureSave = async (pngData) => {
    try {
      setSignatureLoading(true);
      if (selectedOfferCandidate) {
        await sendEmailOffer(pngData, selectedOfferCandidate);
      }
      setShowSignatureModal(false);
    } catch (err) {
      console.error("[OfferListing] Failed to save signature:", err);
      setActionError(err?.message || "Failed to save signature");
    } finally {
      setSignatureLoading(false);
    }
  };

  return (
    <>
      {/* Action Error Banner */}
      {actionError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
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
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
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

      <div className="grid gap-6">
        <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <DropdownContainer>
            <Label>Select Job</Label>
            <Select
              label="Job Title"
              value={selectedJob?.id || ""}
              onChange={(value) => {
                const job = jobs.find((j) => j.id === value);
                setSelectedJob(job);
              }}
              options={jobOptions}
              style={{ width: "20%" }}
              allowClear
            />
            <Label>Select Offer Status</Label>
            <Select
              placeholder="Please select offer type"
              label="Select Offer Status"
              value={statusSelected}
              onChange={(value) => setStatusSelected(value)}
              options={offerStatusOptions}
              style={{ width: "20%" }}
              allowClear
            />
          </DropdownContainer>
        </section>
      </div>
      <Card
        title={`Offer Listing`}
        icon={<Users className="h-4 w-4 text-gray-700" />}
        className="shadow-sm"
      >
        <AntTable
          columns={columns}
          dataSource={offerDetails}
          pagination={false}
          bordered
          loading={loading}
        />
      </Card>

      <SignatureModal
        isOpen={showSignatureModal}
        onClose={() => setShowSignatureModal(false)}
        onSave={handleSignatureSave}
        loading={signatureLoading}
      />
      <RejectModal
        isOpen={rejectModalShow}
        onClose={() => {
          setRejectModalShow(false);
          setRejectReason("");
        }}
        onSubmit={handleRejectOffer}
        value={rejectReason}
        setValue={setRejectReason}
      />
    </>
  );
};

export default OfferListing;
