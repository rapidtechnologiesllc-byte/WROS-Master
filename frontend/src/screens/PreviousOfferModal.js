import React, { useState } from "react";
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
import { EyeIcon, FileText, X, AlertTriangle } from "lucide-react";
import { offerLetterById } from "../services/api/offerLetters";

const PreviousOfferModal = ({ onClose, previousOffer }) => {
  const { Panel } = Collapse;
  const [actionError, setActionError] = useState(null);

  const downloadHandler = async (id, fileName = "OfferLetter.docx") => {
    setActionError(null);
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
      setActionError(err?.message);
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
          {actionError && (
            <div className="mt-4 flex items-start gap-3 rounded-lg bg-red-50 px-4 py-3 border border-red-200">
              <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-800">{actionError}</p>
              </div>
              <button
                type="button"
                onClick={() => setActionError(null)}
                className="flex-shrink-0 text-red-400 hover:text-red-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          )}
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
