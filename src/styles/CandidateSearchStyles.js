import styled from "styled-components";

const ButtonDiv = styled.div`
  display: flex;
  gap: 8px;
`;

const AcceptButton = styled.button`
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  background: #71e09a;
  color: white;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    background: #15803d;
  }

  &:disabled {
    background: #16a34a;
    color: white;
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const RejectButton = styled.button`
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  background: #fee2e2;
  color: #b91c1c;
  cursor: pointer;
  font-size: 13px;

  &:hover {
    background: #b91c1c;
    color: white;
  }

  &:disabled {
    background: #df3b3b;
    color: white;
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

export { AcceptButton, ButtonDiv, RejectButton };
