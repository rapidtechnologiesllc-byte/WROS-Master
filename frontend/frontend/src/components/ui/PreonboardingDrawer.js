import {
  Drawer,
  Avatar,
  Typography,
  Row,
  Col,
  Input,
  Table,
  Checkbox,
  Button,
  Tag,
} from "antd";
import { UserOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import {
  assignChecklistToCandidate,
  getChecklistTemplate,
  listChecklistTemplates,
} from "../../services/api/checklists";
import { sendPlainEmail } from "../../services/api/email";
import { getEmailBodyHTML } from "../../utils/preboardingEmailTemplate";
import { toast } from "react-toastify";
import ScreenErrorDisplay from "../ScreenErrorDisplay";

const { Title, Text, Link } = Typography;

const columns = [
  {
    title: "NAME OF THE TASK",
    dataIndex: "task",
  },
  {
    title: "Description",
    dataIndex: "description",
  },
  {
    title: "Type",
    dataIndex: "type",
  },
  {
    title: "OWNER",
    dataIndex: "owner",
    render: (text) => (
      <>
        <Avatar
          size="small"
          icon={<UserOutlined />}
          style={{ marginRight: 8 }}
        />
        {text}
      </>
    ),
  },
];

const PreboardingDrawer = ({ open, onClose, record, onSuccess }) => {
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [templateList, setTemplateList] = useState([]);
  const [items, setItems] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [screenError, setScreenError] = useState(null);

  const mapItemsToTableData = (items = []) => {
    return items
      .sort((a, b) => a.order_index - b.order_index) // maintain order
      .map((item) => ({
        key: item.id,
        task: item.title,
        description: item.description || "-",
        type: item.item_type,
        createdAt: new Date(item.created_at).toLocaleDateString(),
      }));
  };

  useEffect(() => {
    if (items && items.length > 0) {
      const allKeys = items.map((item) => item.key);
      setSelectedRowKeys(allKeys);
    }
  }, [items]);

  useEffect(() => {
    const listTemplates = async () => {
      try {
        const res = await getChecklistTemplate(5);
        setItems(mapItemsToTableData(res?.items));
      } catch (err) {
        console.log(err);
      }
    };
    listTemplates();
  }, []);

  const getInitials = (name = "") => {
    const parts = name.trim().split(/\s+/);

    if (parts.length === 1) {
      return parts[0][0]?.toUpperCase();
    }

    const first = parts[0][0];
    const last = parts[parts.length - 1][0];

    return (first + last).toUpperCase();
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys) => {
      setSelectedRowKeys(keys);
    },
  };

  const handleInvite = async () => {
    try {
      setSubmitting(true);
      const res = await sendPlainEmail({
        toEmail: record?.candidate_email,
        subject: "Pre-Onboarding Task",
        bodyContent: getEmailBodyHTML(record?.candidate_name),
        isHtml: false,
      });
      const payload = {
        candidateId: record?.candidate_id,
        templateId: 5,
      };
      const assignCheckListApi = await assignChecklistToCandidate(payload);
      if (assignCheckListApi?.response?.status === 200) {
        onSuccess(record?.candidate_id);
      }
      onClose();
      if (res?.status === "success") {
        toast.success("Task assigned Successfully");
      }
    } catch (err) {
      setScreenError(err?.message || "Failed to assign task");
      console.log(err);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
      <Drawer
        title="Start preboarding"
        placement="right"
        width={720}
        onClose={onClose}
        open={open}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button style={{ marginRight: 8 }}>Cancel</Button>
            <Button type="primary" onClick={handleInvite}>
              Invite to portal
            </Button>
          </div>
        }
      >
      {/* Header */}
      <Row gutter={16} align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Avatar size={48}>{getInitials(record?.candidate_name)}</Avatar>
        </Col>
        <Col flex="auto">
          <Text strong>{record?.candidate_name}</Text>
          <br />
          <Text type="secondary">{record?.candidate_job_title}</Text>
        </Col>
        <Col>
          <Text type="secondary">Pending since</Text>
          <br />
          <Text>{record?.joiningDate ? record?.joiningDate : "-"}</Text>
        </Col>
        <Col>
          <Text type="secondary">Department</Text>
          <br />
          <Text>{record?.dept ? record?.dept : "-"}</Text>
        </Col>
        <Col>
          <Text type="secondary">Location</Text>
          <br />
          <Text>{record?.currentLocation ? record?.currentLocation : "-"}</Text>
        </Col>
      </Row>

      {/* Contact Details */}
      <Title level={5}>Confirm contact details</Title>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Text>Personal email</Text>
          <Input value={record?.candidate_email} />
        </Col>
        <Col span={12}>
          <Text>Mobile number</Text>
          <Input value={record?.candidate_mobile} />
        </Col>
      </Row>

      <div
        style={{
          background: "#f5f7fa",
          padding: 12,
          borderRadius: 6,
          marginBottom: 24,
        }}
      >
        <Text type="secondary">
          Candidates will receive email / SMS invite to portal on above details
          to complete tasks
        </Text>
        <br />
        <Text type="secondary">
          Note: Please dont select any task if job position is for interns.
        </Text>
        <br />
      </div>
      <Row justify="space-between" align="middle">
        <Title level={5}>Assign tasks</Title>
        <Tag>
          {selectedRowKeys.length} / {items.length} selected
        </Tag>
      </Row>

      <Table
        columns={columns}
        dataSource={items}
        pagination={false}
        rowSelection={rowSelection}
        bordered
      />
      </Drawer>
    </>
  );
};

export default PreboardingDrawer;
