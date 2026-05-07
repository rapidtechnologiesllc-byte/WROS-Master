import React, { useState } from "react";
import { Button, Card, Select, TextArea } from "../components/ui";
import { DatePicker, Form } from "antd";

const BonusModal = ({ onClose }) => {
  const BonusType = [
    "Project Bonus",
    "Annual Performance Bonus",
    "Other Bonus",
  ];
  const [type, setType] = useState();
  const [description, setDescription] = useState("");
  const onDateChange = (date, dateString) => {
    console.log(date, dateString);
  };

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex justify-center bg-black/40 p-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <div className="w-full max-w-4xl max-h-[80vh] flex flex-col">
          <Card
            title="Assign Bonus"
            bodyClassName="px-2 py-4"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Bonus Type"
                value={type}
                onChange={setType}
                options={BonusType}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Form.Item label="Bonus Payout Date" name="date">
                <DatePicker onChange={onDateChange} />
              </Form.Item>
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <TextArea
                label={"Description"}
                value={description}
                onChange={setDescription}
                placeholder={"Input Text"}
              />
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={() => {}}>Add</Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
};

export default BonusModal;
