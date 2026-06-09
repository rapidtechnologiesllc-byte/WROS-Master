import React from "react";
import {
  ButtonContainer,
  CancelButton,
  ModalContainer,
  Overlay,
  SubmitButton,
  TextArea,
  Title,
} from "../../styles/RejectModalStyles";

const RejectModal = ({ isOpen, onClose, onSubmit, value, setValue }) => {
  if (!isOpen) return null;

  return (
    <Overlay>
      <ModalContainer>
        <Title>Add reason</Title>
        <TextArea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter your remarks here..."
        />
        <ButtonContainer>
          <CancelButton onClick={onClose}>Cancel</CancelButton>
          <SubmitButton onClick={onSubmit}>Submit</SubmitButton>
        </ButtonContainer>
      </ModalContainer>
    </Overlay>
  );
};

export default RejectModal;
