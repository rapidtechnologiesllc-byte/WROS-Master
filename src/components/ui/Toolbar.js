import React from 'react';
import { Switch, Button, Space, Divider, Segmented, Input, Flex } from 'antd';
import {
  AppstoreOutlined,
  TableOutlined,
  FilterOutlined,
  ReloadOutlined
} from '@ant-design/icons';

const Toolbar = ({
  view,
  setView,
  setDrawerOpen,
  onSearch,
  onReset
}) => {
  return (
    <Flex justify="space-between" align="center" style={styles.container}>
      
      {/* LEFT */}
      <Space>
        <Space>
          <Switch defaultChecked />
          <span>Show only my assigned jobs</span>
        </Space>

        <Divider type="vertical" />

        <Segmented
          value={view}
          onChange={setView}
          options={[
            {
              label: <Space><TableOutlined /> Table View</Space>,
              value: 'table'
            },
            {
              label: <Space><AppstoreOutlined /> Card View</Space>,
              value: 'card'
            }
          ]}
        />

        <Button icon={<FilterOutlined />} onClick={() => setDrawerOpen(true)}>
          Set Filters
        </Button>
      </Space>

      {/* RIGHT */}
      <Space>
        <Input.Search
          placeholder="Search by Title or ID"
          onSearch={onSearch}
          allowClear
          style={{ width: 250 }}
        />

        <Button icon={<ReloadOutlined />} onClick={onReset}>
          Reset Filters
        </Button>
      </Space>

    </Flex>
  );
};

const styles = {
  container: {
    padding: '12px 16px',
    background: '#fff',
    borderRadius: 8,
    border: '1px solid #f0f0f0',
    marginBottom: 12
  }
};

export default Toolbar;