import styled from "styled-components";

const ContentDiv = styled.div`
  display: flex;
  gap: 15px;
  justify-content: flex-start;
  align-items: flex-end;
  margin-bottom: 10px;
`;

const AssignButton = styled.button`
  padding: 8px;
  background-color: gray;
  cursor: pointer;
  color: black;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  border-radius: 8px;
`;

export { AssignButton, ContentDiv };
