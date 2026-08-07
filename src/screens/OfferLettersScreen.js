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
  Drawer,
  Button,
} from "antd";
import { getAllOffers } from "../services/api/offerLetters";
import {
  FiltersContainer,
  PageContainer,
  StatsContainer,
} from "../styles/OfferLetterStyles";
const { Search } = Input;

function OfferLettersScreen() {
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

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

  const candidateRows = useMemo(() => {
    const groupedCandidates = {};
    offers?.forEach((offer) => {
      const candidateId = offer?.candidate_id;
      if (!candidateId) return;
      if (!groupedCandidates[candidateId]) {
        groupedCandidates[candidateId] = {
          candidate_id: candidateId,
          candidate_name: offer?.candidate_name,
          candidate_email: offer?.candidate_email,
          offers: [],
        };
      }
      groupedCandidates[candidateId]?.offers?.push(offer);
    });
    let candidates = Object.values(groupedCandidates);
    candidates = candidates.map((candidate) => {
      const latestOffer = [...candidate.offers].sort(
        (a, b) => new Date(b?.created_at) - new Date(a?.created_at),
      )[0];
      return {
        ...candidate,
        latestStatus: latestOffer?.offer_status ?? "-",
        offersCount: candidate?.offers?.length ?? 0,
      };
    });
    if (statusFilter !== "all") {
      candidates = candidates.filter(
        (candidate) =>
          candidate?.latestStatus?.toLowerCase() ===
          statusFilter?.toLowerCase(),
      );
    }
    if (searchText?.trim()) {
      const search = searchText.toLowerCase();

      candidates = candidates.filter(
        (candidate) =>
          candidate?.candidate_name?.toLowerCase()?.includes(search) ||
          candidate?.candidate_email?.toLowerCase()?.includes(search),
      );
    }
    return candidates;
  }, [offers, searchText, statusFilter]);

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "accepted":
        return "success";
      case "approved":
        return "processing";
      case "awaitingapproval":
        return "warning";
      case "released":
        return "cyan";
      case "pending":
        return "gold";
      case "rejected":
        return "error";
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
      title: "Latest Status",
      dataIndex: "latestStatus",
      key: "latestStatus",
      render: (status) => (
        <Tag color={getStatusColor(status)}>{status || "N/A"}</Tag>
      ),
    },
    {
      title: "Offers Count",
      dataIndex: "offersCount",
      key: "offersCount",
    },
    {
      title: "Action",
      key: "action",
      render: (_, record) => (
        <Button
          type="link"
          onClick={() => {
            setSelectedCandidate(record);
            setDrawerOpen(true);
          }}
        >
          View All Offers
        </Button>
      ),
    },
  ];
  const historyColumns = [
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
      <div className="rounded-2xl border bg-white p-4 shadow-sm mb-4">
        <div className="text-lg font-bold text-gray-900">Offer Letters</div>
      </div>
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
      <Card
        title={`Offer Tracking  (${candidateRows.length})`}
        bordered={false}
      >
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
          dataSource={candidateRows}
          loading={loading}
          pagination={{
            defaultPageSize: 10,
            showSizeChanger: true,
          }}
        />
      </Card>
      <Drawer
        title="Offer History"
        open={drawerOpen}
        width={900}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedCandidate(null);
        }}
      >
        <div style={{ marginBottom: 20 }}>
          <h3>{selectedCandidate?.candidate_name}</h3>
          <p>{selectedCandidate?.candidate_email}</p>
          <p>
            <strong>Total Offers:</strong> {selectedCandidate?.offersCount ?? 0}
          </p>
          <p>
            <strong>Latest Status:</strong>{" "}
            {selectedCandidate?.latestStatus ?? "-"}
          </p>
        </div>
        <Table
          rowKey="id"
          columns={historyColumns}
          dataSource={[...(selectedCandidate?.offers ?? [])].sort(
            (a, b) => new Date(b?.created_at) - new Date(a?.created_at),
          )}
          pagination={false}
        />
      </Drawer>
    </PageContainer>
  );
}
export default OfferLettersScreen;
