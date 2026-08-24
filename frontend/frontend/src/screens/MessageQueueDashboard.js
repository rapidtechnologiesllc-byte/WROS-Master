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
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [stats, setStats] = useState({
    total: 0,
    queued: 0,
    active: 0,
    completed: 0,
    failed: 0,
  });

  const loadTasks = async () => {
    try {
      setLoading(true);
      const response = await apiRequest("/admin/queue/tasks", {
        method: "GET",
      });

      if (response?.data?.tasks) {
        setTasks(response.data.tasks);
        calculateStats(response.data.tasks);
      }
    } catch (error) {
      console.error("Failed to load tasks", error);
      message.error("Failed to load message queue tasks");
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (taskList) => {
    const newStats = {
      total: taskList.length,
      queued: 0,
      active: 0,
      completed: 0,
      failed: 0,
    };

    taskList.forEach((task) => {
      const status = task.status?.toLowerCase();
      if (status === "queued") newStats.queued++;
      if (status === "active") newStats.active++;
      if (status === "completed") newStats.completed++;
      if (status === "failed") newStats.failed++;
    });

    setStats(newStats);
  };

  useEffect(() => {
    loadTasks();
    // Auto-refresh every 10 seconds
    const interval = setInterval(loadTasks, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRetryTask = async (taskId) => {
    try {
      await apiRequest(`/admin/queue/tasks/${taskId}/retry`, {
        method: "POST",
      });
      message.success("Task retry queued");
      loadTasks();
    } catch (error) {
      console.error("Failed to retry task", error);
      message.error("Failed to retry task");
    }
  };

  const handleClearTask = async (taskId) => {
    try {
      await apiRequest(`/admin/queue/tasks/${taskId}/clear`, {
        method: "POST",
      });
      message.success("Task cleared");
      loadTasks();
    } catch (error) {
      console.error("Failed to clear task", error);
      message.error("Failed to clear task");
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "queued":
        return "blue";
      case "active":
        return "processing";
      case "completed":
        return "success";
      case "failed":
        return "error";
      default:
        return "default";
    }
  };

  const getStatusIcon = (status) => {
    if (status?.toLowerCase() === "failed") {
      return <ExclamationCircleOutlined />;
    }
    return null;
  };

  const columns = [
    {
      title: "Task ID",
      dataIndex: "task_id",
      key: "task_id",
      width: 200,
      render: (id) => <code style={{ fontSize: "11px" }}>{id?.substring(0, 20)}...</code>,
    },
    {
      title: "Task Name",
      dataIndex: "task_name",
      key: "task_name",
      width: 200,
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
      title: "Progress",
      dataIndex: "progress",
      key: "progress",
      width: 150,
      render: (progress) => (
        <Progress percent={progress || 0} size="small" />
      ),
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
      title: "Action",
      key: "action",
      width: 250,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setSelectedTask(record);
              setDrawerOpen(true);
            }}
          >
            View Messages
          </Button>
          {record.status?.toLowerCase() === "failed" && (
            <>
              <Button
                type="link"
                size="small"
                icon={<RedoOutlined />}
                onClick={() => handleRetryTask(record.task_id)}
              >
                Retry
              </Button>
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleClearTask(record.task_id)}
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
            onClick={loadTasks}
            loading={loading}
          >
            Refresh
          </Button>
        </Space>
      </div>

      <StatsContainer>
        <Card>
          <Statistic
            title="Total Tasks"
            value={stats.total}
            valueStyle={{ color: "#1890ff" }}
          />
        </Card>
        <Card>
          <Statistic
            title="Queued"
            value={stats.queued}
            valueStyle={{ color: "#1890ff" }}
          />
        </Card>
        <Card>
          <Statistic
            title="Active"
            value={stats.active}
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
            title="Failed"
            value={stats.failed}
            valueStyle={{ color: "#ff4d4f" }}
          />
        </Card>
      </StatsContainer>

      <Card>
        <Spin spinning={loading}>
          {tasks.length === 0 ? (
            <Empty description="No tasks in queue" />
          ) : (
            <Table
              columns={columns}
              dataSource={tasks}
              rowKey="task_id"
              pagination={{ pageSize: 20 }}
              scroll={{ x: 1200 }}
            />
          )}
        </Spin>
      </Card>

      <Drawer
        title={`Task Messages: ${selectedTask?.task_name}`}
        placement="right"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={600}
      >
        {selectedTask && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <h3>Task Details</h3>
              <p><strong>Task ID:</strong> <code>{selectedTask.task_id}</code></p>
              <p><strong>Status:</strong> <Tag color={getStatusColor(selectedTask.status)}>{selectedTask.status}</Tag></p>
              <p><strong>Created:</strong> {new Date(selectedTask.created_at).toLocaleString()}</p>
              <p><strong>Progress:</strong> <Progress percent={selectedTask.progress || 0} /></p>
            </div>

            <div>
              <h3>Messages & Events</h3>
              {selectedTask.messages && selectedTask.messages.length > 0 ? (
                <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                  {selectedTask.messages.map((msg, idx) => (
                    <Card
                      key={idx}
                      size="small"
                      style={{ marginBottom: 12 }}
                      type={msg.level === "error" ? "error" : "default"}
                    >
                      <p style={{ margin: 0, marginBottom: 4 }}>
                        <strong>
                          <Tag color={msg.level === "error" ? "red" : "blue"}>
                            {msg.level?.toUpperCase()}
                          </Tag>
                        </strong>
                        <small style={{ marginLeft: 8 }}>
                          {new Date(msg.timestamp).toLocaleTimeString()}
                        </small>
                      </p>
                      <p style={{ margin: 0, fontFamily: "monospace", fontSize: "12px", whiteSpace: "pre-wrap" }}>
                        {msg.message}
                      </p>
                    </Card>
                  ))}
                </div>
              ) : (
                <Empty description="No messages yet" />
              )}
            </div>

            {selectedTask.status?.toLowerCase() === "failed" && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid #ddd" }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<RedoOutlined />}
                    onClick={() => {
                      handleRetryTask(selectedTask.task_id);
                      setDrawerOpen(false);
                    }}
                  >
                    Retry Task
                  </Button>
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => {
                      handleClearTask(selectedTask.task_id);
                      setDrawerOpen(false);
                    }}
                  >
                    Clear Task
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
