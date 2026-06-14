import React from "react";
import { Button } from "../components/ui";
import {
  Content,
  DateText,
  DetailItem,
  DetailsGrid,
  HeaderRow,
  Label,
  StyledCollapse,
  Title,
  Value,
  Wrapper,
} from "../styles/Pre-onboardingModal";
import { DownOutlined } from "@ant-design/icons";
import { Collapse } from "antd";
import { EyeIcon, FileText } from "lucide-react";
import { toast } from "react-toastify";
import { offerLetterById } from "../services/api/offerLetters";

const PreviousOfferModal = ({ onClose, previousOffer }) => {
  const { Panel } = Collapse;

  const downloadHandler = async (id, fileName = "OfferLetter.docx") => {
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
        throw new Error("Failed to download offer letter.");
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
    } catch (err) {
      toast.error(err?.message);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex justify-center items-center p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-6xl h-[95vh] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        <div className="shrink-0 border-b bg-white px-6 py-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold">Previous Offer Letters</h2>
            </div>
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto px-6 py-4">
            <Wrapper>
              <StyledCollapse
                accordion
                bordered={false}
                expandIcon={({ isActive }) => (
                  <DownOutlined rotate={isActive ? 180 : 0} />
                )}
              >
                {previousOffer?.map((offer) => (
                  <Panel
                    key={offer?.id}
                    header={
                      <HeaderRow>
                        <FileText title={offer?.file}>
                          {offer?.download_url}
                        </FileText>
                        <Value>{offer?.candidate_name}</Value>
                      </HeaderRow>
                    }
                  >
                    <Wrapper>
                      <DetailsGrid>
                        <DetailItem>
                          <Label>Email ID</Label>
                          <Value title={offer?.candidate_email}>
                            {offer?.candidate_email}
                          </Value>
                        </DetailItem>
                        <DetailItem>
                          <Label>Salary</Label>
                          <Value>{offer?.salary}</Value>
                        </DetailItem>
                        <DetailItem>
                          <Label>Recruiter</Label>
                          <Value>Onboarding Team</Value>
                        </DetailItem>
                        <DetailItem>
                          <Label>Offer template</Label>
                          <Value>Default Offer Letter</Value>
                        </DetailItem>
                        <DetailItem>
                          <Label>Joining date</Label>
                          <Value>{offer?.joining_date}</Value>
                        </DetailItem>
                        <DetailItem>
                          <Label>Valid upto</Label>
                          <Value>{offer?.offer_expire_date}</Value>
                        </DetailItem>
                        <Button
                          variant="secondary"
                          onClick={() => downloadHandler(offer?.id)}
                        >
                          Download Offer Letter
                        </Button>
                      </DetailsGrid>{" "}
                    </Wrapper>
                  </Panel>
                ))}
              </StyledCollapse>
            </Wrapper>
          </div>
        </div>
      </div>
    </div>
  );
};
export default PreviousOfferModal;
