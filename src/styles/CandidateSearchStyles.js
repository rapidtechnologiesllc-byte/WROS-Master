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

  &:hover {
    background: #15803d;
  }
`;

const RejectButton = styled.div`
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  background: #FEE2E2;
  color: #B91C1C;
  cursor: pointer;
  font-size: 13px;

  &:hover {
    background: #b91c1c;
    color: white;
  }
`;

export {AcceptButton,ButtonDiv,RejectButton}
