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
  Badge,
  Row,
  Col,
  Statistic,
  Select,
  Alert,
} from 'antd';
import {
  ReloadOutlined,
  DeleteOutlined,
  RedoOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import styled from 'styled-components';

const PageContainer = styled.div`
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
`;

const StatsContainer = styled.div`
  margin-bottom: 24px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
`;

const FilterContainer = styled.div`
  margin-bottom: 20px;
  padding: 16px;
  background: white;
  border-radius: 4px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
`;

const EmailMetricsContainer = styled.div`
  margin: 20px 0;
  padding: 16px;
  background: white;
  border-radius: 4px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
`;

function MessageQueueDashboard() {
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [filterQueueType, setFilterQueueType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(50);

  // Queue types
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
  ];

  const STATUSES = [
    'PENDING',
    'SLM_PROCESSING',
    'CHANNEL_QUEUED',
    'COMPLETED',
    'FAILED',
  ];

  // Fetch messages and stats
  useEffect(() => {
    fetchData();
    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [filterQueueType, filterStatus, skip, limit]);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Build query params (note: backend uses 'offset' not 'skip')
      const params = new URLSearchParams();
      params.append('offset', skip);
      params.append('limit', limit);
      if (filterQueueType) params.append('queue_type', filterQueueType);
      if (filterStatus) params.append('status', filterStatus);

      // Fetch messages
      const messagesRes = await fetch(`/api/v1/queues?${params}`);
      if (!messagesRes.ok) {
        const errText = await messagesRes.text();
        throw new Error(`Failed to fetch messages: ${errText}`);
      }
      const messagesData = await messagesRes.json();
      setMessages(messagesData.data || []);

      // Fetch stats
      const statsRes = await fetch(`/api/v1/queues/stats`);
      if (!statsRes.ok) {
        const errText = await statsRes.text();
        throw new Error(`Failed to fetch stats: ${errText}`);
      }
      const statsData = await statsRes.json();

      // Transform stats to match UI expectations
      const transformedStats = {
        timestamp: new Date().toISOString(),
        queues: {},
        email_metrics: null, // Could be populated from stats if needed
      };

      // Build queue stats from by_queue_type
      if (statsData.by_queue_type) {
        for (const [queueType, count] of Object.entries(statsData.by_queue_type)) {
          transformedStats.queues[queueType] = {
            total: count,
            PENDING: 0,
            COMPLETED: 0,
            FAILED: 0,
          };
        }
      }

      // Populate status counts per queue
      if (statsData.by_status) {
        // This is a simplified approach - ideally backend would return per-queue status counts
        for (const queueType of Object.keys(transformedStats.queues)) {
          transformedStats.queues[queueType].PENDING = statsData.by_status.PENDING || 0;
          transformedStats.queues[queueType].COMPLETED = statsData.by_status.COMPLETED || 0;
          transformedStats.queues[queueType].FAILED = statsData.by_status.FAILED || 0;
        }
      }

      setStats(transformedStats);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Failed to fetch queue data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async (messageId) => {
    try {
      const res = await fetch(`/api/v1/queues/${messageId}/retry`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to retry message');
      message.success('Message queued for retry');
      fetchData();
    } catch (err) {
      message.error(`Error: ${err.message}`);
    }
  };

  const handleClear = async (messageId) => {
    try {
      const res = await fetch(`/api/v1/queues/${messageId}/clear`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to clear message');
      message.success('Message cleared');
      fetchData();
    } catch (err) {
      message.error(`Error: ${err.message}`);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'PENDING':
        return 'processing';
      case 'SLM_PROCESSING':
        return 'processing';
      case 'CHANNEL_QUEUED':
        return 'processing';
      case 'COMPLETED':
        return 'success';
      case 'FAILED':
        return 'error';
      default:
        return 'default';
    }
  };

  const getQueueTypeColor = (queueType) => {
    if (!queueType) return 'default';
    if (queueType.includes('EMAIL')) return 'blue';
    if (queueType.includes('THUNDER')) return 'green';
    if (queueType.includes('APPROVAL')) return 'orange';
    if (queueType.includes('COMMISSION')) return 'purple';
    return 'default';
  };

  const columns = [
    {
      title: 'Message ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (text) => <code style={{ fontSize: '11px' }}>{text?.substring(0, 8) || '-'}</code>,
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 140,
    },
    {
      title: 'Queue',
      dataIndex: 'queue_type',
      key: 'queue_type',
      width: 110,
      render: (text) => text ? <Tag color={getQueueTypeColor(text)}>{text}</Tag> : <span>-</span>,
    },
    {
      title: 'Resource',
      dataIndex: 'resource_id',
      key: 'resource_id',
      width: 140,
      render: (text, record) => {
        if (!text) return <span>-</span>;

        // For THUNDER_QUEUE messages, link to candidate details
        if (record.queue_type === 'THUNDER_QUEUE' || record.type === 'candidate_created') {
          return (
            <a href={`/candidates/${record.resource_id}`} target="_blank" rel="noopener noreferrer">
              📋 Candidate {text?.substring(0, 8)}
            </a>
          );
        }

        // For other queue types, show generic resource link
        return <code style={{ fontSize: '11px' }}>{text?.substring(0, 8)}</code>;
      },
    },
    {
      title: 'Payload Info',
      dataIndex: 'payload',
      key: 'payload_info',
      width: 200,
      render: (payload, record) => {
        if (!payload) return <span>-</span>;

        // Extract useful info from payload
        const candidate_name = payload.candidate_name || payload.name;
        const candidate_email = payload.candidate_email || payload.email;
        const job_id = payload.job_id;

        return (
          <Space direction="vertical" size="small" style={{ fontSize: '12px' }}>
            {candidate_name && <span>{candidate_name}</span>}
            {candidate_email && <span style={{ color: '#666' }}>{candidate_email}</span>}
            {job_id && (
              <a href={`/jobs/${job_id}`} target="_blank" rel="noopener noreferrer">
                🎯 Job {job_id?.substring(0, 8)}
              </a>
            )}
          </Space>
        );
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (text) => <Tag color={getStatusColor(text)}>{text}</Tag>,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
      render: (text) => formatDate(text),
    },
    {
      title: 'Retries',
      dataIndex: 'retry_count',
      key: 'retry_count',
      width: 60,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space>
          {record.status === 'FAILED' && (
            <>
              <Button
                size="small"
                type="primary"
                icon={<RedoOutlined />}
                onClick={() => handleRetry(record.id)}
              >
                Retry
              </Button>
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleClear(record.id)}
              >
                Clear
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  if (loading && !stats) {
    return (
      <PageContainer>
        <Spin />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      {error && <Alert message={error} type="error" showIcon closable style={{ marginBottom: 16 }} />}

      {/* Statistics Section */}
      {stats && (
        <>
          {/* Queue Stats */}
          {stats.queues && Object.keys(stats.queues).length > 0 && (
            <>
              <h2>Queue Statistics</h2>
              <StatsContainer>
                {Object.entries(stats.queues).map(([queueType, queueStats]) => (
                  <Card key={queueType} size="small">
                    <Statistic title={queueType} value={queueStats.total} />
                    <Row gutter={16} style={{ marginTop: 16 }}>
                      <Col span={12}>
                        <Statistic
                          title="Completed"
                          value={queueStats.COMPLETED || 0}
                          valueStyle={{ color: '#52c41a', fontSize: '14px' }}
                        />
                      </Col>
                      <Col span={12}>
                        <Statistic
                          title="Failed"
                          value={queueStats.FAILED || 0}
                          valueStyle={{ color: '#f5222d', fontSize: '14px' }}
                        />
                      </Col>
                    </Row>
                  </Card>
                ))}
              </StatsContainer>
            </>
          )}

          {/* Email Engagement Metrics */}
          {stats.email_metrics && (
            <>
              <h2 style={{ marginTop: 24 }}>Email Engagement Metrics</h2>
              <EmailMetricsContainer>
                <Card size="small">
                  <Statistic title="Total Sent" value={stats.email_metrics.total_sent} />
                </Card>
                <Card size="small">
                  <Statistic
                    title="Open Rate"
                    value={stats.email_metrics.open_rate}
                    suffix="%"
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Card>
                <Card size="small">
                  <Statistic
                    title="Click Rate"
                    value={stats.email_metrics.click_rate}
                    suffix="%"
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Card>
                <Card size="small">
                  <Statistic
                    title="Bounce Rate"
                    value={stats.email_metrics.bounce_rate}
                    suffix="%"
                    valueStyle={{ color: '#f5222d' }}
                  />
                </Card>
                <Card size="small">
                  <Statistic
                    title="Reply Rate"
                    value={stats.email_metrics.reply_rate}
                    suffix="%"
                    valueStyle={{ color: '#faad14' }}
                  />
                </Card>
              </EmailMetricsContainer>
            </>
          )}
        </>
      )}

      {/* Filters Section */}
      <h2 style={{ marginTop: 24 }}>Filters</h2>
      <FilterContainer>
        <div>
          <label style={{ display: 'block', marginBottom: 8 }}>Queue Type</label>
          <Select
            value={filterQueueType}
            onChange={(value) => {
              setFilterQueueType(value);
              setSkip(0);
            }}
            placeholder="All Queues"
            style={{ width: '100%' }}
            options={[
              { label: 'All Queues', value: '' },
              ...QUEUE_TYPES.map(t => ({ label: t, value: t })),
            ]}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 8 }}>Status</label>
          <Select
            value={filterStatus}
            onChange={(value) => {
              setFilterStatus(value);
              setSkip(0);
            }}
            placeholder="All Statuses"
            style={{ width: '100%' }}
            options={[
              { label: 'All Statuses', value: '' },
              ...STATUSES.map(s => ({ label: s, value: s })),
            ]}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: 8 }}>Limit per Page</label>
          <Select
            value={limit}
            onChange={(value) => {
              setLimit(value);
              setSkip(0);
            }}
            style={{ width: '100%' }}
            options={[
              { label: '10', value: 10 },
              { label: '25', value: 25 },
              { label: '50', value: 50 },
              { label: '100', value: 100 },
            ]}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={fetchData}
            loading={loading}
            style={{ width: '100%' }}
          >
            Refresh
          </Button>
        </div>
      </FilterContainer>

      {/* Messages Table */}
      <h2 style={{ marginTop: 24 }}>Messages ({messages.length})</h2>
      <Card loading={loading}>
        {messages.length === 0 ? (
          <Empty description="No messages found" />
        ) : (
          <>
            <Table
              columns={columns}
              dataSource={messages}
              rowKey="id"
              size="small"
              pagination={false}
              scroll={{ x: 1200 }}
            />

            {/* Pagination */}
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <Space>
                <Button
                  onClick={() => setSkip(Math.max(0, skip - limit))}
                  disabled={skip === 0}
                >
                  Previous
                </Button>
                <span>
                  Page {Math.floor(skip / limit) + 1} (showing {messages.length} of {skip + messages.length})
                </span>
                <Button onClick={() => setSkip(skip + limit)}>Next</Button>
              </Space>
            </div>
          </>
        )}
      </Card>
    </PageContainer>
  );
}

export default MessageQueueDashboard;
