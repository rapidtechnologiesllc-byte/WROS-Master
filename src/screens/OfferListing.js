import React, { useEffect, useState } from "react";
import { Label, SectionTitle } from "../styles/Pre-onboardingModal";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { getAllJobs } from "../services/api/jobs";
import { Select } from "antd";
import { Card } from "../components/ui";
import { Table as AntTable } from "antd";
import { Users } from "lucide-react";
import { toast } from "react-toastify";
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
import PreonboardingModal from "./PreonboardingModal";
import SignatureModal from "../components/ui/SignatureModal";
import { sendMailAttachments, sendPlainEmail } from "../services/api/email";
import OfferConfirmationEmail from "../utils/offerLetterTemplate";
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
import { mapJobFromApi } from "../routes/Approutes";

const OfferListing = () => {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [offerDetails, setOfferDetails] = useState([]);
  const [preonboardingModal, setPreonboardingModal] = useState(false);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedOfferCandidate, setSelectedOfferCandidate] = useState(null);
  const [signaturePng, setSignaturePng] = useState(null);
  const [signatureLoading, setSignatureLoading] = useState(false);
  const [rejectModalShow, setRejectModalShow] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [statusSelected, setStatusSelected] = useState("");
  const canManageOffers = hasPermission("offers", "edit");
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
        const mappedJobs = (refreshed?.jobs || []).map((j) =>
          mapJobFromApi(j, users),
        );
        setJobs(mappedJobs);
      } catch (err) {
        console.error(err);
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
        toast.error(err);
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
        toast.error("Failed to fetch offers");
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
      toast.error("Offer letter download url is not available");
    }
    try {
      const createOfferId = await offerLetterById(id);
      const response = await fetch(createOfferId?.download_url, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("hrms_token")}`,
        },
      });
      if (!response.ok) {
        toast.error("Failed to download offer letter.");
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
    } catch (error) {
      toast.error("Download failed", error);
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
      if (cancelOfferApi?.status === "Success") {
        const result = await updateCandidateStatus(
          selectedOfferCandidate?.candidate_id,
          {
            status: "Active",
            pipeline_status: "Applied",
          },
        );
        if (result?.status === "success") {
          await sendPlainEmail({
            toEmail: selectedOfferCandidate?.candidate_email,
            subject: `Update on Your Application - ${selectedOfferCandidate?.position}`,
            bodyContent: getRejectionEmailHTML(
              selectedOfferCandidate?.candidate_name,
            ),
            isHtml: true,
          });
          const matchid = selectedOfferCandidate?.id;
          setOfferDetails((prev) =>
            prev.map((item) =>
              item?.id == matchid
                ? { ...item, offer_status: "Cancelled" }
                : item,
            ),
          );
          toast.success("Offer rejected successfully");
        }
      }
      setRejectModalShow(false);
      setRejectReason("");
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
              setCandidateRecord(record);
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
          toast.success("Offer Approved, and release");
        }

        // const emailResult = await sendMailAttachments({
        //   toEmail: candidateData?.candidate_email,
        //   subject: `BlitzenX-Employment Offer ${candidateData?.candidate_name} | ${candidateData?.position} `,
        //   bodyContent: OfferConfirmationEmail(
        //     candidateData?.candidate_name,
        //     candidateData?.position,
        //     "BlitzenX",
        //     candidateData?.job_id,
        //   ),
        //   files: [candidateData?.download_url],
        //   is_html: false,
        // });
      }
    } catch (error) {
      toast.error("Offer Already Approved");
    }
  };

  const handleSignatureSave = async (pngData) => {
    try {
      setSignatureLoading(true);
      setSignaturePng(pngData);
      if (selectedOfferCandidate) {
        await sendEmailOffer(pngData, selectedOfferCandidate);
      }
      setShowSignatureModal(false);
    } catch (err) {
      toast.error(err?.message);
    } finally {
      setSignatureLoading(false);
    }
  };

  return (
    <>
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
