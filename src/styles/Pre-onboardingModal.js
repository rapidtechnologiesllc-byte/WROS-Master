import styled from "styled-components";

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

const Container = styled.div`
  padding: 20px;
  background: #f5f6f8;
  min-height: 60vh;
`;

const Section = styled.div`
  background: #fff;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 20px;
`;

const ScrollContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding-right: 6px;
  max-height: 60vh;
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

const PreviewBox = styled.div`
  height: 600px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fafafa;
  overflow-y: auto;
  padding: 20px;
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

export {
  StepperDiv,
  Span,
  CheckBoxesDiv,
  BonusButtonDiv,
  Container,
  CandidateWrapper,
  Name,
  PreviewBox,
  Role,
  Section,
  Title,
  ScrollContainer,
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
};
