// Hiring Manager Review (CEO 2026-10-17): the hiring manager's candidates with every interview's
// feedback (Candidate Review) and re-interview sign-offs for past no-hires (Rehire Approvals).
// Each tab keeps its screen and permission.
import TabbedScreen from "../components/TabbedScreen";
import HmCandidateReviewScreen from "./HmCandidateReviewScreen";
import RehireApprovalsScreen from "./RehireApprovalsScreen";

const TABS = [
  { key: "candidates", label: "Candidate Review", resource: "candidate-review", render: () => <HmCandidateReviewScreen /> },
  { key: "rehire", label: "Rehire Approvals", resource: "rehire-approval", render: () => <RehireApprovalsScreen /> },
];

export default function HmReviewScreen() {
  return <TabbedScreen title="Hiring Manager Review" tabs={TABS} />;
}
