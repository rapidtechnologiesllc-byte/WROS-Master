import { Table } from "antd";

const PreonboardingTable = ({columns,data}) => {
  return (
    <>
      <div style={wrapper}>
        <Table
        columns={columns}
        dataSource={data}
        pagination={false}
        rowKey="id"
      />
      </div>
    </>
  );
};

export default PreonboardingTable;

const wrapper = {
  background: "#fff",
  padding: 12,
  borderRadius: 8,
  border: "1px solid #f0f0f0",
};
