import { Briefcase } from "lucide-react";
import { Card } from "../components/ui";
import TableView from "../components/ui/TableView";
import PreonboardingTable from "./PreonboardingTable";
import { useEffect, useState } from "react";
import PreboardingDrawer from "../components/ui/PreonboardingDrawer";
import { getAllCandidates } from "../services/api/candidates";

const PreOnboardingPage = ({ candidates }) => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [preboardingStatus, setPreboardingStatus] = useState({});
  const [preBoardingCandidates, setPreBoardingCandidates] = useState([]);

  useEffect(() => {
    const getAllCandidatesApi = async () => {
      const candidateList = await getAllCandidates();
      setPreBoardingCandidates(candidateList?.candidates)
    };
    getAllCandidatesApi();
  }, []);

  const preOnboardingCandidates = (preBoardingCandidates || []).filter(
    (c) => c.pipline_status === "Pre-Onboarding",
  );
  const formattedCandidates = preOnboardingCandidates;

  const columns = [
    {
      title: "Name",
      dataIndex: "candidate_name",
    },
    {
      title: "Email",
      dataIndex: "candidate_email",
    },
    {
      title: "Phone",
      dataIndex: "candidate_mobile",
    },
    {
      title: "Action",
      render: (_, record) => {
        const isAssigned = preboardingStatus[record.candidate_id] === "assigned";
        return (
          <button
            className="px-4 py-1.5 text-sm font-medium text-blue-600 
                   border border-blue-400 rounded-md 
                   bg-blue-50 hover:bg-blue-100 transition"
            onClick={() => {
              if (isAssigned) {
                console.log("Verify clicked", record);
              } else {
                setSelectedRecord(record);
                setDrawerOpen(true);
              }
            }}
          >
            {isAssigned ? "Verify" : "Start preboarding"}
          </button>
        );
      },
    },
  ];

  return (
    <>
      <div className="grid gap-4">
        <Card title="All Jobs" icon={<Briefcase className="h-4 w-4" />}>
          <PreonboardingTable columns={columns} data={formattedCandidates} />
          <PreboardingDrawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            record={selectedRecord}
            onSuccess={(candidateId) => {
              setPreboardingStatus((prev) => ({
                ...prev,
                [candidateId]: "assigned",
              }));
            }}
          />
        </Card>
      </div>
    </>
  );
};

export default PreOnboardingPage;
