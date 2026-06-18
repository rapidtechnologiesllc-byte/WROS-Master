import { useEffect, useMemo, useState } from "react";
import {
  Card,
  Input,
  Table,
  Tag,
  Avatar,
  Row,
  Col,
  Statistic,
  Select,
} from "antd";
import styled from "styled-components";
import { getAllOffers } from "../services/api/offerLetters";
const { Search } = Input;
const PageContainer = styled.div`
  padding: 24px;
`;
const FiltersContainer = styled.div`
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
`;
const StatsContainer = styled.div`
  margin-bottom: 20px;
`;

function OfferLettersScreen() {
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    loadOffers();
  }, []);

  const loadOffers = async () => {
    try {
      setLoading(true);
      const response = await getAllOffers();
      setOffers(response?.offers ?? []);
    } catch (error) {
      console.error("Failed to load offers", error);
    } finally {
      setLoading(false);
    }
  };

  const statistics = useMemo(() => {
    const counts = {};
    offers.forEach((offer) => {
      const status = offer?.offer_status || "Unknown";
      counts[status] = (counts[status] || 0) + 1;
    });

    return {
      total: offers.length,
      pending: counts.Pending || 0,
      approved:
        (counts.Approved || 0) +
        (counts.AwaitingApproval || 0) +
        (counts.Released || 0),
      accepted: counts.Accepted || 0,
      rejected: (counts.Rejected || 0) + (counts.Cancelled || 0),
    };
  }, [offers]);
  const filteredOffers = useMemo(() => {
    let filtered = [...offers];

    if (statusFilter !== "all") {
      filtered = filtered.filter(
        (offer) =>
          offer?.offer_status?.toLowerCase() === statusFilter.toLowerCase(),
      );
    }

    if (searchText.trim()) {
      const search = searchText.toLowerCase();

      filtered = filtered.filter(
        (offer) =>
          offer?.candidate_name?.toLowerCase().includes(search) ||
          offer?.candidate_email?.toLowerCase().includes(search) ||
          offer?.position?.toLowerCase().includes(search),
      );
    }

    return filtered;
  }, [offers, searchText, statusFilter]);

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "accepted":
        return "success";
      case "rejected":
        return "error";
      case "pending":
        return "warning";
      case "cancelled":
        return "default";
      default:
        return "default";
    }
  };

  const columns = [
    {
      title: "Candidate",
      key: "candidate",

      render: (_, record) => {
        const initials =
          record?.candidate_name
            ?.split(" ")
            ?.map((word) => word?.[0])
            ?.join("")
            ?.slice(0, 2)
            ?.toUpperCase() || "NA";

        return (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <Avatar>{initials}</Avatar>

            <div>
              <div style={{ fontWeight: 500 }}>
                {record?.candidate_name || "-"}
              </div>

              <div
                style={{
                  fontSize: 12,
                  color: "#8c8c8c",
                }}
              >
                {record?.candidate_email || "-"}
              </div>
            </div>
          </div>
        );
      },
    },
    {
      title: "Position",
      dataIndex: "position",
      key: "position",
    },
    {
      title: "Salary",
      dataIndex: "salary",
      key: "salary",
      render: (salary) =>
        salary ? `₹${Number(salary).toLocaleString("en-IN")}` : "-",
    },
    {
      title: "Joining Date",
      dataIndex: "joining_date",
      key: "joining_date",
      render: (date) =>
        date
          ? new Date(date).toLocaleDateString("en-IN", {
              day: "2-digit",
              month: "short",
              year: "numeric",
            })
          : "-",
    },
    {
      title: "Offer Expiry",
      dataIndex: "offer_expire_date",
      key: "offer_expire_date",
      render: (date) =>
        date
          ? new Date(date).toLocaleDateString("en-IN", {
              day: "2-digit",
              month: "short",
              year: "numeric",
            })
          : "-",
    },
    {
      title: "Status",
      dataIndex: "offer_status",
      key: "offer_status",
      render: (status) => (
        <Tag color={getStatusColor(status)}>{status || "N/A"}</Tag>
      ),
    },
  ];

  return (
    <PageContainer>
      <StatsContainer>
        <Row gutter={[16, 16]}>
          <Col span={4}>
            <Card>
              <Statistic title="Total Offers" value={statistics.total} />
            </Card>
          </Col>

          <Col span={5}>
            <Card>
              <Statistic title="Pending" value={statistics.pending} />
            </Card>
          </Col>

          <Col span={5}>
            <Card>
              <Statistic title="Approved" value={statistics.approved} />
            </Card>
          </Col>

          <Col span={5}>
            <Card>
              <Statistic title="Accepted" value={statistics.accepted} />
            </Card>
          </Col>

          <Col span={5}>
            <Card>
              <Statistic title="Rejected" value={statistics.rejected} />
            </Card>
          </Col>
        </Row>
      </StatsContainer>

      <Card title={`Offer Letters (${filteredOffers.length})`} bordered={false}>
        <FiltersContainer>
          <Search
            placeholder="Search by candidate, email, or position"
            allowClear
            style={{ maxWidth: 400 }}
            onChange={(e) => setSearchText(e.target.value)}
          />

          <Select
            value={statusFilter}
            style={{ width: 180 }}
            onChange={setStatusFilter}
            options={[
              { label: "All Statuses", value: "all" },
              { label: "Pending", value: "pending" },
              { label: "Approved", value: "approved" },
              { label: "Awaiting Approval", value: "awaitingapproval" },
              { label: "Released", value: "released" },
              { label: "Accepted", value: "accepted" },
              { label: "Rejected", value: "rejected" },
              { label: "Cancelled", value: "cancelled" },
            ]}
          />
        </FiltersContainer>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={filteredOffers}
          loading={loading}
          pagination={{
            defaultPageSize: 10,
            showSizeChanger: true,
          }}
        />
      </Card>
    </PageContainer>
  );
}

export default OfferLettersScreen;
