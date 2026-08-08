import { useNavigate } from "react-router-dom";
import MoveStageDrawer from "./MoveStageDrawer";
import { useState } from "react";

const CandidateActionMenu = ({
  candidate,
  openMenuId,
  setOpenMenuId,
  handleActiveStatus,
  handleCandidateStatus,
  setCandidateList,
}) => {
  const [openMoveDrawer, setOpenMoveDrawer] = useState(false);
  const navigate = useNavigate();

  const handleSendEmail = () => {
    const email = candidate.candidate_email?.trim();
    if (!email) return;

    const subject = encodeURIComponent("Regarding your application");
    const body = encodeURIComponent(`Hi ${candidate.candidate_name || "Candidate"},\n\n`);
    const to = encodeURIComponent(email);
    const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${to}&su=${subject}&body=${body}`;
    const mailtoUrl = `mailto:${to}?subject=${subject}&body=${body}`;
    const openedWindow = window.open(gmailUrl, "_blank", "noopener,noreferrer");
    if (!openedWindow) {
      window.location.href = mailtoUrl;
    }
    setOpenMenuId(null);
  };

  return (
    <div className="relative">
      <button
        className="px-2 py-1 text-gray-600 hover:text-black"
        onClick={() =>
          setOpenMenuId(openMenuId === candidate.id ? null : candidate.id)
        }
      >
        ⋮
      </button>

      {openMenuId === candidate.id && (
        <div className="absolute right-0 z-10 mt-2 w-56 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg">
          <button
            className="block w-full px-4 py-3 text-left text-sm hover:bg-gray-50"
            onClick={() => {
              navigate(`/candidates/${candidate.id}?schedule=true`);
              setOpenMenuId(null);
            }}
          >
            Schedule Interview
          </button>
          <button
            className="block w-full px-4 py-3 text-left text-sm hover:bg-gray-50"
            onClick={handleSendEmail}
          >
            Send Email
          </button>
          <button
            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!candidate?.phone}
            onClick={() => {
              if (!candidate?.phone) return;
              const cleanedPhone = candidate.candidate_mobile.replace(/\D/g, "");
              if (!cleanedPhone) {
                return;
              }
              window.open(`https://wa.me/${cleanedPhone}`, "_blank");
              setOpenMenuId(null);
            }}
          >
            Message on WhatsApp
          </button>
          <button
            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
            onClick={() => {
              navigate(`/candidates/${candidate.id}?tab=feedback`);
              setOpenMenuId(null);
            }}
          >
            Add Feedback
          </button>
          <button
            className="block w-full px-4 py-3 text-left text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
            onClick={() => {
              handleActiveStatus("Inactive", candidate?.id);
            }}
          >
            Archive
          </button>
          <button
            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
            onClick={() => {
              handleCandidateStatus(candidate?.id);
              setOpenMenuId(null);
            }}
          >
            Pre Onboarding
          </button>
          <button
            className="block w-full px-4 py-3 text-left text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 hover:text-black"
            onClick={() => {
              setOpenMoveDrawer(true);
            }}
          >
            Move Stage
          </button>
          <MoveStageDrawer
            open={openMoveDrawer}
            onClose={() => setOpenMoveDrawer(false)}
            onSubmit={(stage) => {
              setCandidateList((prev) =>
                prev.map((c) =>
                  c.id === stage.candidate_id
                    ? {
                        ...c,
                        status: stage.status,
                        pipelineStatus: stage.pipeline_status,
                      }
                    : c,
                ),
              );
            }}
            data={candidate}
          />
        </div>
      )}
    </div>
  );
};

export default CandidateActionMenu;
