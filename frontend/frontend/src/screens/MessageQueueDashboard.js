import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Tag,
  Button,
  Drawer,
  Statistic,
  Row,
  Col,
  Space,
  Spin,
  Empty,
  message,
  Badge,
  Progress,
} from "antd";
import {
  ReloadOutlined,
  DeleteOutlined,
  RedoOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import styled from "styled-components";
import { apiRequest } from "../services/api/client";

const PageContainer = styled.div`
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
`;

const StatsContainer = styled.div`
  margin-bottom: 24px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
`;

function MessageQueueDashboard() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pagination, setPagination] = useState({
    skip: 0,
    limit: 50,
    total: 0,
  });
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    processing: 0,
    completed: 0,
    retrying: 0,
    failed: 0,
  });

  const loadMessages = async (skip = 0) => {
    try {
      setLoading(true);
      const response = await apiRequest(
        `/admin/queue?skip=${skip}&limit=${pagination.limit}`,
        {
          method: "GET",
        }
      );

      if (response?.data) {
        setMessages(response.data);
        setPagination({
          skip: response.skip || 0,
          limit: response.limit || 50,
          total: response.total || 0,
        });
        calculateStats(response.data);
      }
    } catch (error) {
      console.error("Failed to load messages", error);
      message.error("Failed to load message queue");
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (messageList) => {
    const newStats = {
      total: messageList.length,
      pending: 0,
      processing: 0,
      completed: 0,
      retrying: 0,
      failed: 0,
    };

    messageList.forEach((msg) => {
      const status = msg.status?.toUpperCase();
      if (status === "PENDING") newStats.pending++;
      if (status === "PROCESSING") newStats.processing++;
      if (status === "COMPLETED") newStats.completed++;
      if (status === "RETRYING") newStats.retrying++;
      if (status === "FAILED") newStats.failed++;
    });

    setStats(newStats);
  };

  useEffect(() => {
    loadMessages();
    // Auto-refresh every 10 seconds
    const interval = setInterval(() => loadMessages(pagination.skip), 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRetryMessage = async (messageId) => {
    try {
      await apiRequest(`/admin/queue/tasks/${messageId}/retry`, {
        method: "POST",
      });
      message.success("Message retry queued");
      loadMessages(pagination.skip);
    } catch (error) {
      console.error("Failed to retry message", error);
      message.error("Failed to retry message");
    }
  };

  const handleClearMessage = async (messageId) => {
    try {
      await apiRequest(`/admin/queue/tasks/${messageId}/clear`, {
        method: "POST",
      });
      message.success("Message cleared");
      loadMessages(pagination.skip);
    } catch (error) {
      console.error("Failed to clear message", error);
      message.error("Failed to clear message");
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toUpperCase()) {
      case "PENDING":
        return "blue";
      case "PROCESSING":
        return "processing";
      case "COMPLETED":
        return "success";
      case "RETRYING":
        return "warning";
      case "FAILED":
        return "error";
      default:
        return "default";
    }
  };

  const getStatusIcon = (status) => {
    if (status?.toUpperCase() === "FAILED") {
      return <ExclamationCircleOutlined />;
    }
    return null;
  };

  const columns = [
    {
      title: "Message ID",
      dataIndex: "id",
      key: "id",
      width: 180,
      render: (id) => <code style={{ fontSize: "11px" }}>{id?.substring(0, 16)}...</code>,
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 150,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status) => (
        <Tag color={getStatusColor(status)} icon={getStatusIcon(status)}>
          {status}
        </Tag>
      ),
    },
    {
      title: "Resource ID",
      dataIndex: "resource_id",
      key: "resource_id",
      width: 150,
      render: (id) =>
        id ? <code style={{ fontSize: "11px" }}>{id.substring(0, 16)}...</code> : "-",
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (date) =>
        date
          ? new Date(date).toLocaleString()
          : "-",
    },
    {
      title: "Retries",
      dataIndex: "retry_count",
      key: "retry_count",
      width: 80,
      render: (count) => count || 0,
    },
    {
      title: "Action",
      key: "action",
      width: 200,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setSelectedMessage(record);
              setDrawerOpen(true);
            }}
          >
            Details
          </Button>
          {record.status?.toUpperCase() === "FAILED" && (
            <>
              <Button
                type="link"
                size="small"
                icon={<RedoOutlined />}
                onClick={() => handleRetryMessage(record.id)}
              >
                Retry
              </Button>
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleClearMessage(record.id)}
              >
                Clear
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <div>
        <h1>Message Queue Dashboard</h1>
        <Space style={{ marginBottom: 16 }}>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => loadMessages(0)}
            loading={loading}
          >
            Refresh
          </Button>
        </Space>
      </div>

      <StatsContainer>
        <Card>
          <Statistic
            title="Total Messages"
            value={pagination.total}
            valueStyle={{ color: "#1890ff" }}
          />
        </Card>
        <Card>
          <Statistic
            title="Pending"
            value={stats.pending}
            valueStyle={{ color: "#1890ff" }}
          />
        </Card>
        <Card>
          <Statistic
            title="Processing"
            value={stats.processing}
            valueStyle={{ color: "#faad14" }}
          />
        </Card>
        <Card>
          <Statistic
            title="Completed"
            value={stats.completed}
            valueStyle={{ color: "#52c41a" }}
          />
        </Card>
        <Card>
          <Statistic
            title="Retrying"
            value={stats.retrying}
            valueStyle={{ color: "#faad14" }}
          />
        </Card>
        <Card>
          <Statistic
            title="Failed"
            value={stats.failed}
            valueStyle={{ color: "#ff4d4f" }}
          />
        </Card>
      </StatsContainer>

      <Card>
        <Spin spinning={loading}>
          {messages.length === 0 ? (
            <Empty description="No messages in queue" />
          ) : (
            <Table
              columns={columns}
              dataSource={messages}
              rowKey="id"
              pagination={{
                pageSize: pagination.limit,
                total: pagination.total,
                current: Math.floor(pagination.skip / pagination.limit) + 1,
                onChange: (page) => {
                  const newSkip = (page - 1) * pagination.limit;
                  loadMessages(newSkip);
                },
              }}
              scroll={{ x: 1200 }}
            />
          )}
        </Spin>
      </Card>

      <Drawer
        title={`Message Details: ${selectedMessage?.type}`}
        placement="right"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={600}
      >
        {selectedMessage && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <h3>Message Details</h3>
              <p>
                <strong>Message ID:</strong> <br />
                <code style={{ fontSize: "11px", wordBreak: "break-all" }}>
                  {selectedMessage.id}
                </code>
              </p>
              <p>
                <strong>Type:</strong> {selectedMessage.type}
              </p>
              <p>
                <strong>Status:</strong>{" "}
                <Tag color={getStatusColor(selectedMessage.status)}>
                  {selectedMessage.status}
                </Tag>
              </p>
              <p>
                <strong>Resource ID:</strong>{" "}
                {selectedMessage.resource_id ? (
                  <code style={{ fontSize: "11px" }}>{selectedMessage.resource_id}</code>
                ) : (
                  "-"
                )}
              </p>
              <p>
                <strong>Created By:</strong> {selectedMessage.created_by || "-"}
              </p>
              <p>
                <strong>Created:</strong>{" "}
                {selectedMessage.created_at
                  ? new Date(selectedMessage.created_at).toLocaleString()
                  : "-"}
              </p>
              <p>
                <strong>Updated:</strong>{" "}
                {selectedMessage.updated_at
                  ? new Date(selectedMessage.updated_at).toLocaleString()
                  : "-"}
              </p>
              <p>
                <strong>Retry Count:</strong> {selectedMessage.retry_count || 0}
              </p>
              {selectedMessage.error && (
                <p>
                  <strong>Error:</strong> <br />
                  <code style={{ fontSize: "11px", whiteSpace: "pre-wrap" }}>
                    {selectedMessage.error}
                  </code>
                </p>
              )}
            </div>

            {selectedMessage.status?.toUpperCase() === "FAILED" && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid #ddd" }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<RedoOutlined />}
                    onClick={() => {
                      handleRetryMessage(selectedMessage.id);
                      setDrawerOpen(false);
                    }}
                  >
                    Retry Message
                  </Button>
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => {
                      handleClearMessage(selectedMessage.id);
                      setDrawerOpen(false);
                    }}
                  >
                    Clear Message
                  </Button>
                </Space>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </PageContainer>
  );
}

export default MessageQueueDashboard;
