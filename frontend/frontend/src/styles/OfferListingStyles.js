import styled from "styled-components";

export const ViewButton = styled.button`
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 18px rgba(79, 70, 229, 0.35);
  }

  &:active {
    transform: translateY(0);
  }
`;

export const DownloadButton = styled.button`
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #10b981, #34d399);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 18px rgba(16, 185, 129, 0.35);
  }

  &:active {
    transform: translateY(0);
  }
`;

export const OfferLetterButtonContainer = styled.div`
  display: flex;
  gap: 10px;
  align-items: center;
`;

export const DropdownContainer = styled.div`
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 12px;
`;
