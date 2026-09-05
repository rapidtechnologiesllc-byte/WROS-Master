import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Spin,
  Empty,
  message,
  Drawer,
} from 'antd';
import {
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import styled from 'styled-components';
import * as queuesApi from '../services/api/queues';

const PageContainer = styled.div`
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
`;

function MessageQueueDashboard() {
  const [queues, setQueues] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedQueue, setSelectedQueue] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);

  const QUEUE_TYPES = [
    'THUNDER_QUEUE',
    'EMAIL_QUEUE',
    'WHATSAPP_QUEUE',
    'SMS_QUEUE',
    'SLACK_QUEUE',
    'APPROVAL_QUEUE',
    'COMMISSION_QUEUE',
    'CRM_QUEUE',
    'DASHBOARD_QUEUE',
    'CALENDAR_QUEUE',
    'SIGNATURE_QUEUE',
    'CANDIDATE_QUEUE',
  ];

  useEffect(() => {
    fetchQueueStats();
    const interval = setInterval(fetchQueueStats, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchQueueStats = async () => {
    try {
      setLoading(true);
      setError(null);

      const statsData = await queuesApi.getQueueStats();

      // Transform stats to queue list format
      const queueList = QUEUE_TYPES.map(queueType => {
        const queueData = statsData.queues?.[queueType] || {};
        const messageCount = queueData.total || 0;

        return {
          id: queueType,
          name: queueType,
          total_messages: messageCount,
          status: messageCount > 0 ? 'Running' : 'Idle',
          pending: queueData.pending || 0,
          completed: queueData.completed || 0,
          failed: queueData.failed || 0,
        };
      });

      setQueues(queueList);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const fetchQueueMessages = async (queueType) => {
    try {
      const messagesData = await queuesApi.getQueueMessages(queueType, null, 100, 0);
      setMessages(messagesData.data || []);
      setSelectedQueue(queueType);
      setDrawerVisible(true);
    } catch (err) {
      message.error(err.message);
    }
  };

  const handleQueueAction = async (queueType, action) => {
    try {
      let result;
      if (action === 'start') {
        result = await queuesApi.startQueue(queueType);
      } else if (action === 'stop') {
        result = await queuesApi.stopQueue(queueType);
      } else if (action === 'retry') {
        result = await queuesApi.retryQueue(queueType);
      }

      message.success(result.message || `Queue ${action} successful`);

      // Refresh stats
      await fetchQueueStats();
    } catch (err) {
      message.error(err.message);
    }
  };

  const queueColumns = [
    {
      title: 'Queue Type',
      dataIndex: 'name',
      key: 'name',
      width: '30%',
      render: (text, record) => (
        <Button
          type="link"
          onClick={() => fetchQueueMessages(record.name)}
          style={{ padding: 0, textAlign: 'left' }}
        >
          {text}
        </Button>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: '15%',
      render: (status) => (
        <Tag icon={status === 'Running' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
             color={status === 'Running' ? 'green' : 'gray'}>
          {status}
        </Tag>
      ),
    },
    {
      title: 'Total Messages',
      dataIndex: 'total_messages',
      key: 'total_messages',
      width: '15%',
    },
    {
      title: 'Completed',
      dataIndex: 'completed',
      key: 'completed',
      width: '13%',
      render: (count) => <Tag color="green">{count}</Tag>,
    },
    {
      title: 'Failed',
      dataIndex: 'failed',
      key: 'failed',
      width: '13%',
      render: (count) => <Tag color="red">{count}</Tag>,
    },
    {
      title: 'Pending',
      dataIndex: 'pending',
      key: 'pending',
      width: '14%',
      render: (count) => <Tag color="blue">{count}</Tag>,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: '15%',
      render: (text, record) => (
        <Space size="small">
          <Button
            size="small"
            type="primary"
            onClick={() => handleQueueAction(record.name, 'start')}
            loading={loading}
          >
            Start
          </Button>
          <Button
            size="small"
            danger
            onClick={() => handleQueueAction(record.name, 'stop')}
            loading={loading}
          >
            Stop
          </Button>
          <Button
            size="small"
            onClick={() => handleQueueAction(record.name, 'retry')}
            loading={loading}
          >
            Retry
          </Button>
        </Space>
      ),
    },
  ];

  const messageColumns = [
    {
      title: 'Message ID',
      dataIndex: 'id',
      key: 'id',
      width: '20%',
      ellipsis: true,
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: '15%',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: '15%',
      render: (status) => (
        <Tag color={status === 'COMPLETED' ? 'green' : status === 'FAILED' ? 'red' : 'blue'}>
          {status}
        </Tag>
      ),
    },
    {
      title: 'Resource',
      dataIndex: 'resource_id',
      key: 'resource_id',
      width: '20%',
      ellipsis: true,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: '20%',
      render: (date) => date ? new Date(date).toLocaleString() : '-',
    },
    {
      title: 'Retries',
      dataIndex: 'retry_count',
      key: 'retry_count',
      width: '10%',
    },
    {
      title: 'Actions',
      key: 'actions',
      width: '15%',
      render: (text, record) => (
        <Space size="small">
          {record.status === 'FAILED' && (
            <Button
              size="small"
              type="primary"
              onClick={() => retryMessage(record.id)}
            >
              Retry
            </Button>
          )}
          <Button
            size="small"
            danger
            onClick={() => clearMessage(record.id)}
          >
            Clear
          </Button>
        </Space>
      ),
    },
  ];

  const retryMessage = async (messageId) => {
    try {
      await queuesApi.retryMessage(messageId);
      message.success('Message queued for retry');

      // Refresh messages
      if (selectedQueue) {
        await fetchQueueMessages(selectedQueue);
      }
    } catch (err) {
      message.error(err.message);
    }
  };

  const clearMessage = async (messageId) => {
    try {
      await queuesApi.clearMessage(messageId);
      message.success('Message cleared from queue');

      // Refresh messages
      if (selectedQueue) {
        await fetchQueueMessages(selectedQueue);
      }
    } catch (err) {
      message.error(`Failed to clear message: ${err.message}`);
      throw err;
    }
  };

  return (
    <PageContainer>
      <Card
        title="Message Queue Dashboard"
        extra={<Button icon={<ReloadOutlined />} onClick={fetchQueueStats}>Refresh</Button>}
        style={{ marginBottom: '24px' }}
      >
        {error && (
          <div style={{ marginBottom: '16px', padding: '12px', background: '#fff2f0', borderRadius: '4px', color: '#ff4d4f' }}>
            {error}
          </div>
        )}

        <Spin spinning={loading}>
          {queues.length > 0 ? (
            <Table
              columns={queueColumns}
              dataSource={queues.map((q, idx) => ({ ...q, key: idx }))}
              pagination={false}
              size="middle"
              onRow={(record) => ({
                style: { cursor: 'pointer' },
              })}
            />
          ) : (
            <Empty description="No queues available" />
          )}
        </Spin>
      </Card>

      <Drawer
        title={
          <Space>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => setDrawerVisible(false)}
            />
            <span>Messages in {selectedQueue}</span>
          </Space>
        }
        placement="right"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width="90%"
      >
        {messages.length > 0 ? (
          <Table
            columns={messageColumns}
            dataSource={messages.map((m, idx) => ({ ...m, key: idx }))}
            pagination={{ pageSize: 20 }}
            size="small"
          />
        ) : (
          <Empty description="No messages in this queue" />
        )}
      </Drawer>
    </PageContainer>
  );
}

export default MessageQueueDashboard;
