import React from 'react';
import { Table, Tag, Dropdown } from 'antd';
import { MoreOutlined } from '@ant-design/icons';

const TableView = ({ data }) => {
  const columns = [
    {
      title: '',
      render: () => <input type="checkbox" />
    },
    { title: 'ID', dataIndex: 'id' },
    { title: 'Title', dataIndex: 'title' },

    {
      title: 'Type',
      dataIndex: 'type',
      render: (val) => <Tag color="blue">{val}</Tag>
    },

    { title: 'Client / Dept', dataIndex: 'clientDept' },
    { title: 'BU', dataIndex: 'bu' },
    { title: 'Location', dataIndex: 'location' },

    {
      title: 'Hiring Manager',
      dataIndex: 'hiringManager',
      render: (val) => <Tag>{val}</Tag>
    },

    { title: 'Recruiter', dataIndex: 'recruiter' },
    { title: 'Open', dataIndex: 'openPositions' },

    {
      title: 'Status',
      dataIndex: 'status',
      render: (val) => (
        <Tag color={val === 'Open' ? 'green' : 'default'}>
          {val}
        </Tag>
      )
    },

    {
      title: '',
      render: () => (
        <Dropdown
          menu={{
            items: [
              { key: '1', label: 'Edit' },
              { key: '2', label: 'Delete' }
            ]
          }}
        >
          <MoreOutlined style={{ cursor: 'pointer' }} />
        </Dropdown>
      )
    }
  ];

  return (
    <div style={wrapper}>
      <Table columns={columns} dataSource={data} pagination={false} rowKey="id" />
    </div>
  );
};

const wrapper = {
  background: '#fff',
  padding: 12,
  borderRadius: 8,
  border: '1px solid #f0f0f0'
};

export default TableView;