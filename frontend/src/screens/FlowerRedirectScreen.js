import { useEffect } from 'react';
import { Card, Button, Space, Typography } from 'antd';
import { LinkOutlined } from '@ant-design/icons';

const { Title, Paragraph } = Typography;

export default function FlowerRedirectScreen() {
  useEffect(() => {
    // Redirect to Flower after 2 seconds
    const timer = setTimeout(() => {
      window.location.href = 'http://localhost:5555';
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div style={{ padding: '48px 24px', maxWidth: '600px', margin: '0 auto' }}>
      <Card>
        <Title level={2}>Queue Monitoring with Flower</Title>
        <Paragraph>
          The message queue dashboard has been replaced with <strong>Celery Flower</strong>,
          the industry-standard monitoring tool for Celery task queues.
        </Paragraph>

        <Paragraph>
          Flower provides real-time monitoring of:
          <ul>
            <li>Active tasks</li>
            <li>Worker pool status</li>
            <li>Task history and statistics</li>
            <li>Queue management</li>
          </ul>
        </Paragraph>

        <div style={{ background: '#f5f5f5', padding: '16px', borderRadius: '4px', marginBottom: '24px' }}>
          <Paragraph style={{ margin: 0 }}>
            <strong>Flower URL:</strong> <code>http://localhost:5555</code>
          </Paragraph>
        </div>

        <Paragraph>Redirecting you to Flower in 2 seconds...</Paragraph>

        <Space>
          <Button
            type="primary"
            icon={<LinkOutlined />}
            onClick={() => window.location.href = 'http://localhost:5555'}
          >
            Open Flower Now
          </Button>
          <Button onClick={() => window.history.back()}>
            Go Back
          </Button>
        </Space>
      </Card>
    </div>
  );
}
