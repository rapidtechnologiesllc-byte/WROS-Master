import React, { useEffect, useState } from "react";
import { SectionTitle } from "../styles/Pre-onboardingModal";
import { getAllJobs } from "../services/api/jobs";
import { mapJobFromApi } from "../App";
import { Select } from "antd";
import { Card } from "../components/ui";
import { Table as AntTable } from "antd";
import { Users } from "lucide-react";
import { toast } from "react-toastify";
import {
  approveOfferLetter,
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
import { sendMailAttachments } from "../services/api/email";
import OfferConfirmationEmail from "../utils/offerLetterTemplate";
import { EyeOutlined, DownloadOutlined } from "@ant-design/icons";
import {
  DownloadButton,
  OfferLetterButtonContainer,
  ViewButton,
} from "../styles/OfferListingStyles";

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
  const currentRole = localStorage.getItem("hrms_role");

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
      if (!selectedJob?.id) return;

      try {
        setLoading(true);
        const list = await offerLetterByJobId(selectedJob?.id || "");
        setOfferDetails(list?.offers);
        console.log(list);
      } catch (err) {
        toast.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchList();
  }, [selectedJob]);

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

  const downloadFile = async (url, fileName = "OfferLetter.pdf") => {
    try {
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("hrms_token")}`,
        },
      });

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
      console.error("Download failed", error);
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

            <DownloadButton onClick={() => downloadFile(record?.download_url)}>
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
    ...(currentRole === "HR MANAGER"
      ? [
          {
            title: "Action",
            key: "action",
            render: (_, record) => {
              return (
                <ButtonDiv>
                  <AcceptButton onClick={() => sigatureModalHandler(record)}>
                    Accept
                  </AcceptButton>
                  <RejectButton
                  //   onClick={() => managerRejectCandidate(record)}
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
        // const emailResult = sendMailAttachments({
        //   toEmail: candidateData?.candidate_email,
        //   subject: `BlitzenX-Employment Offer ${candidateData?.candidate_name} | ${candidateData?.position} `,
        //   bodyContent: OfferConfirmationEmail(
        //     candidateData?.candidate_name,
        //     candidateData?.position,
        //     "BlitzenX",
        //     candidateData?.job_id,
        //   ),
        //   files: candidateData?.download_url,
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
        <div className="space-y-6">
          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              Candidate List
            </div>
            <span>
              Lisintg of candidates who's offer letters are pending for approval
            </span>
          </div>
        </div>
      </div>
      <div className="grid gap-6">
        <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <SectionTitle title="Candidate Overview" />
          <Select
            label="Job Title"
            value={selectedJob?.id || ""}
            onChange={(value) => {
              const job = jobs.find((j) => j.id === value);
              setSelectedJob(job);
            }}
            options={jobOptions}
          />
        </section>
      </div>
      <Card
        // title={`Candidates (${tableData.length})`}
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
    </>
  );
};

export default OfferListing;
