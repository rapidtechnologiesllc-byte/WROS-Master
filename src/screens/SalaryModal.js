import React from "react";
import { Button, Card } from "../components/ui";
import { Divider, Table, Typography, Spin } from "antd";

const SalaryModal = ({ onClose, salaryDataProp, loading }) => {
  const { Text } = Typography;

  const formatINR = (value) => {
    if (value === null || value === undefined) return "-";
    return `INR ${Number(value).toLocaleString("en-IN")}`;
  };

  const mapSalaryData = (data) => {
    if (!data) return [];

    return [
      {
        key: "basic",
        label: "Basic Salary",
        monthly: formatINR(data.basic_pm),
        annually: formatINR(data.basic_pa),
      },
      {
        key: "hra",
        label: "House Rent Allowance",
        monthly: formatINR(data.hra_pm),
        annually: formatINR(data.hra_pa),
      },
      {
        key: "medical",
        label: "Medical Allowance",
        monthly: formatINR(data.medical_pm),
        annually: formatINR(data.medical_pa),
      },
      {
        key: "transport",
        label: "Transport Allowance",
        monthly: formatINR(data.transport_pm),
        annually: formatINR(data.transport_pa),
      },
      {
        key: "deployment",
        label: "Deployment Allowance",
        monthly: formatINR(data.deployment_pm),
        annually: formatINR(data.deployment_pa),
      },
      {
        key: "fixed",
        label: "Fixed Allowance",
        monthly: formatINR(data.fixed_allowance_pm),
        annually: formatINR(data.fixed_allowance_pa),
      },
      {
        key: "gross",
        label: "GROSS",
        monthly: formatINR(data.gross_pm),
        annually: formatINR(data.gross_pa),
        isTotal: true,
      },
    ];
  };

  const mapDeductionData = (data) => {
    if (!data) return [];

    return [
      {
        key: "epf_emp",
        label: "PF Employee",
        monthly: formatINR(data.epf_employee_pm),
        annually: formatINR(data.epf_employee_pa),
      },
      {
        key: "epf_employer",
        label: "PF Employer",
        monthly: formatINR(data.epf_employer_pm),
        annually: formatINR(data.epf_employer_pa),
      },
      {
        key: "esic_emp",
        label: "ESIC Employee",
        monthly: formatINR(data.esic_employee_pm),
        annually: formatINR(data.esic_employee_pa),
      },
      {
        key: "total_deductions",
        label: "Total Deductions",
        monthly: formatINR(data.total_deductions_pm),
        annually: formatINR(data.total_deductions_pa),
        isTotal: true,
      },
      {
        key: "net",
        label: "Net Salary",
        monthly: formatINR(data.net_pm),
        annually: formatINR(data.net_pa),
        isTotal: true,
      },
    ];
  };

  const salaryData = React.useMemo(() => {
    return mapSalaryData(salaryDataProp);
  }, [salaryDataProp]);

  const deductionData = React.useMemo(() => {
    return mapDeductionData(salaryDataProp);
  }, [salaryDataProp]);

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
        className="fixed inset-0 z-50 flex justify-center bg-black/40 p-4"
        role="dialog"
        aria-modal="true"
      >
        <div className="w-full max-w-4xl max-h-[90vh] flex flex-col bg-white rounded-lg overflow-hidden">
          <Card
            title="Salary Structure"
            bodyClassName="px-2 py-4 flex flex-col overflow-y-auto"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div className="overflow-y-auto max-h-[70vh] pr-2">
              {loading ? (
                <div className="flex justify-center items-center h-64">
                  <Spin size="large" />
                </div>
              ) : (
                <>
                  <Table
                    columns={columns}
                    dataSource={salaryData}
                    pagination={false}
                    bordered
                    size="middle"
                    rowClassName={(record) =>
                      record.isTotal ? "total-row" : ""
                    }
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
                </>
              )}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
};

export default SalaryModal;
