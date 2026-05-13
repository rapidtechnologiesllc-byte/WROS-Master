import React from "react";
import { Button, Card } from "../components/ui";
import { Divider, Table, Typography } from "antd";

const SalaryModal = ({ onClose }) => {
  const { Text } = Typography;

  const salaryData = [
    {
      key: "1",
      label: "Basic Salary",
      monthly: "INR 1,25,000",
      annually: "INR 15,00,000",
    },
    {
      key: "2",
      label: "House Rent Allowance/Company Leased Accommodation",
      monthly: "INR 50,000",
      annually: "INR 6,00,000",
    },
    {
      key: "3",
      label: "Medical Allowance",
      monthly: "INR 1,250",
      annually: "INR 15,000",
    },
    {
      key: "4",
      label: "Fixed Allowance",
      monthly: "INR 67,150",
      annually: "INR 8,05,800",
    },
    {
      key: "5",
      label: "Transport Allowance",
      monthly: "INR 1,600",
      annually: "INR 19,200",
    },
    {
      key: "6",
      label: "Deployment Allowance/ Performance Incentive",
      monthly: "INR 5,000",
      annually: "INR 60,000",
    },
    {
      key: "7",
      label: "TOTAL",
      monthly: "INR 2,50,000",
      annually: "INR 30,00,000",
      isTotal: true,
    },
  ];

  const deductionData = [
    {
      key: "1",
      label: "PF Employee",
      monthly: "INR 1,800",
      annually: "INR 21,600",
    },
    {
      key: "2",
      label: "PF - Employer",
      monthly: "INR 1,800",
      annually: "INR 21,600",
    },
  ];

  const columns = [
    {
      title: "DETAILS",
      dataIndex: "label",
      key: "label",
      width: "50%",
      render: (text, record) => <Text strong={record.isTotal}>{text}</Text>,
    },
    {
      title: "MONTHLY",
      dataIndex: "monthly",
      key: "monthly",
      align: "left",
      render: (text, record) => <Text strong={record.isTotal}>{text}</Text>,
    },
    {
      title: "ANNUALLY",
      dataIndex: "annually",
      key: "annually",
      align: "left",
      render: (text, record) => <Text strong={record.isTotal}>{text}</Text>,
    },
  ];

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex justify-center bg-black/40 p-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <div className="w-full max-w-4xl max-h-[75vh] flex flex-col">
          <Card
            title="Salary Structure"
            bodyClassName="px-2 py-4 flex flex-col overflow-hidden max-h-[75vh]"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div>
              <Table
                columns={columns}
                dataSource={salaryData}
                pagination={false}
                bordered
                size="middle"
                rowClassName={(record) => (record.isTotal ? "total-row" : "")}
              />
              <Divider />
              <Table
                columns={[
                  {
                    ...columns[0],
                    title: "DEDUCTIONS",
                  },
                  columns[1],
                  columns[2],
                ]}
                dataSource={deductionData}
                pagination={false}
                bordered
                size="middle"
              />
            </div>
          </Card>
        </div>
      </div>
    </>
  );
};

export default SalaryModal;
