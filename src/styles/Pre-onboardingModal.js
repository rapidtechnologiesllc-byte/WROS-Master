import styled from "styled-components";
import { Collapse } from "antd";

const StepperDiv = styled.div`
  margin-top: 10px;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
`;

const Span = styled.span`
  font-weight: 600;
`;

const CheckBoxesDiv = styled.div`
  margin-top: 10px;
  display: flex;
  gap: 10px;
`;

const BonusButtonDiv = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  color: #0b68cb;
  cursor: pointer;
  width: fit-content;
  margin-top: 10px;
`;

const Title = styled.h3`
  margin-bottom: 16px;
  font-weight: 600;
  color: #333;
`;

const CandidateWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Name = styled.div`
  font-weight: 500;
`;

const Role = styled.div`
  font-size: 12px;
  color: #888;
`;

const IconDiv = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  color: #0b68cb;
  width: fit-content;
  cursor: pointer;
`;

const Wrapper = styled.div`
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 24px;
  width: 100%;
  margin-top: 24px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const AvatarWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
`;

const UserInfo = styled.div`
  display: flex;
  flex-direction: column;
`;

const CandidateName = styled.div`
  font-size: 16px;
  font-weight: 600;
  color: #111827;
`;

const CandidateRole = styled.div`
  font-size: 13px;
  color: #6b7280;
  margin-top: 2px;
`;

const SectionTitle = styled.div`
  font-size: 15px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 20px;
`;

const DetailsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 28px;

  @media (max-width: 1200px) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  @media (max-width: 768px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 480px) {
    grid-template-columns: 1fr;
  }
`;

const DetailItem = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const Label = styled.div`
  font-size: 12px;
  color: #9ca3af;
`;

const Value = styled.div`
  font-size: 14px;
  color: #111827;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
`;

const StyledCollapse = styled(Collapse)`
  background: transparent;
  .ant-collapse-item {
    border: 1px solid #e5e7eb;
    border-radius: 6px !important;
    margin-bottom: 12px;
    overflow: hidden;
    background: #fff;
  }
  .ant-collapse-header {
    padding: 18px 20px !important;
    align-items: center !important;
  }
  .ant-collapse-expand-icon {
    color: #6b7280;
    font-size: 12px;
  }
  .ant-collapse-content-box {
    padding: 16px 20px !important;
    border-top: 1px solid #f1f5f9;
    max-height: 300px;
    overflow-y: auto;
  }
`;

const HeaderRow = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
`;

const FileText = styled.span`
  font-size: 14px;
  font-weight: 500;
  color: #111827;

  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const DateText = styled.span`
  font-size: 14px;
  color: #374151;
  white-space: nowrap;
`;

const Content = styled.div`
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 8px;
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 999px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
`;

const PreviewLayout = styled.div`
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: #f3f4f6;
`;

const PreviewTopBar = styled.div`
  padding: 20px 24px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
`;

const DocumentViewer = styled.div`
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: auto;
  padding: 32px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background: #e5e7eb;
`;

const EmptyState = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 15px;
`;

const DocumentPaper = styled.div`
  width: 850px;
  min-height: 1100px;
  background: #ffffff;
  border-radius: 10px;
  padding: 56px;
  box-shadow:
    0 10px 25px rgba(0, 0, 0, 0.08),
    0 4px 10px rgba(0, 0, 0, 0.04);
  margin-bottom: 40px;
  @media (max-width: 900px) {
    width: 100%;
    padding: 24px;
  }
`;

const FormStepContainer = styled.div`
  padding: 24px;
  min-height: 100%;
  background: #fff;
`;

export {
  StepperDiv,
  Span,
  CheckBoxesDiv,
  BonusButtonDiv,
  CandidateWrapper,
  Name,
  Role,
  Title,
  IconDiv,
  AvatarWrapper,
  CandidateName,
  DetailItem,
  DetailsGrid,
  Header,
  Label,
  SectionTitle,
  UserInfo,
  Value,
  Wrapper,
  CandidateRole,
  StyledCollapse,
  Collapse,
  Content,
  DateText,
  FileText,
  HeaderRow,
  DocumentViewer,
  EmptyState,
  PreviewLayout,
  PreviewTopBar,
  DocumentPaper,
  FormStepContainer,
};
