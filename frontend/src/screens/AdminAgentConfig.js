import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Card, Space, Tag, Empty, Spin, message } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { apiRequest } from '../services/api/client';


const AdminAgentConfig = () => {

  // State
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [form] = Form.useForm();

  // Fetch agents on mount
  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const { data } = await apiRequest('/admin/agents/config', { method: 'GET' });
      setAgents(data);
      setError(null);
    } catch (err) {
      const errorMsg = err.message || 'Failed to load agents';
      setError(errorMsg);
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleShowModal = (agent = null) => {
    if (agent) {
      setEditingAgent(agent);
      form.setFieldsValue(agent);
    } else {
      setEditingAgent(null);
      form.resetFields();
    }
    setIsModalVisible(true);
  };

  const handleCloseModal = () => {
    setIsModalVisible(false);
    setEditingAgent(null);
    form.resetFields();
  };

  const handleSaveAgent = async (values) => {
    try {
      setSyncing(true);
      const path = editingAgent ? `/admin/agents/config/${editingAgent.id}` : '/admin/agents/config';
      await apiRequest(path, { method: editingAgent ? 'PUT' : 'POST', body: JSON.stringify(values) });

      message.success(editingAgent ? 'Agent updated' : 'Agent created');
      handleCloseModal();
      await fetchAgents();
    } catch (err) {
      const errorMsg = err.message || 'Failed to save agent';
      message.error(errorMsg);
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteAgent = (agentId) => {
    Modal.confirm({
      title: 'Delete Agent',
      content: 'Are you sure you want to delete this agent?',
      okText: 'Yes',
      cancelText: 'No',
      onOk: async () => {
        try {
          await apiRequest(`/admin/agents/config/${agentId}`, { method: 'DELETE' });

          message.success('Agent deleted');
          await fetchAgents();
        } catch (err) {
          const errorMsg = err.message || 'Failed to delete agent';
          message.error(errorMsg);
        }
      }
    });
  };

  const columns = [
    {
      title: 'Order',
      dataIndex: 'order',
      key: 'order',
      width: 80,
      render: (text) => text || '-'
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text) => <strong>{text}</strong>
    },
    {
      title: 'Display Name',
      dataIndex: 'display_name',
      key: 'display_name'
    },
    {
      title: 'Queue Name',
      dataIndex: 'queue_name',
      key: 'queue_name',
      render: (text) => <code>{text}</code>
    },
    {
      title: 'Next Queue',
      dataIndex: 'next_queue_name',
      key: 'next_queue_name',
      render: (text) => text ? <code>{text}</code> : '-'
    },
    {
      title: 'Status',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled) => (
        <Tag color={enabled ? 'green' : 'red'}>
          {enabled ? 'Enabled' : 'Disabled'}
        </Tag>
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleShowModal(record)}
          >
            Edit
          </Button>
          <Button
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteAgent(record.id)}
          >
            Delete
          </Button>
        </Space>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="Agent Configuration"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => handleShowModal()}
          >
            Add Agent
          </Button>
        }
      >
        {error && (
          <div style={{ marginBottom: '16px', color: 'red' }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {loading ? (
          <Spin />
        ) : agents.length === 0 ? (
          <Empty description="No agents configured" />
        ) : (
          <Table
            columns={columns}
            dataSource={agents}
            rowKey="id"
            pagination={{ pageSize: 10 }}
          />
        )}
      </Card>

      <Modal
        title={editingAgent ? 'Edit Agent' : 'Create Agent'}
        visible={isModalVisible}
        onOk={() => form.submit()}
        onCancel={handleCloseModal}
        confirmLoading={syncing}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSaveAgent}
        >
          <Form.Item
            label="Name"
            name="name"
            rules={[{ required: true, message: 'Please enter agent name' }]}
          >
            <input type="text" style={{ width: '100%', padding: '8px' }} />
          </Form.Item>

          <Form.Item
            label="Display Name"
            name="display_name"
            rules={[{ required: true, message: 'Please enter display name' }]}
          >
            <input type="text" style={{ width: '100%', padding: '8px' }} />
          </Form.Item>

          <Form.Item
            label="Description"
            name="description"
          >
            <textarea style={{ width: '100%', padding: '8px', minHeight: '80px' }} />
          </Form.Item>

          <Form.Item
            label="Queue Name"
            name="queue_name"
            rules={[{ required: true, message: 'Please enter queue name' }]}
          >
            <input type="text" style={{ width: '100%', padding: '8px' }} />
          </Form.Item>

          <Form.Item
            label="Next Queue Name"
            name="next_queue_name"
          >
            <input type="text" style={{ width: '100%', padding: '8px' }} />
          </Form.Item>

          <Form.Item
            label="Order"
            name="order"
          >
            <input type="number" style={{ width: '100%', padding: '8px' }} />
          </Form.Item>

          <Form.Item
            label="Enabled"
            name="enabled"
            valuePropName="checked"
          >
            <input type="checkbox" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AdminAgentConfig;
