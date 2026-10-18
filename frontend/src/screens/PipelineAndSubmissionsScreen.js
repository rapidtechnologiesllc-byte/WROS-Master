// Pipeline & Submissions (CEO 2026-10-17): client submissions and the hiring pipeline
// (screen -> evaluate -> BGV -> onboarding -> client start) in one screen. Each tab keeps its own
// screen and permission: submissions / convert-to-employee.
import TabbedScreen from "../components/TabbedScreen";
import SubmissionsScreen from "./SubmissionsScreen";
import HiringPipelineScreen from "./HiringPipelineScreen";

const TABS = [
  { key: "submissions", label: "Submissions", resource: "submissions", render: () => <SubmissionsScreen /> },
  { key: "pipeline", label: "Hiring Pipeline", resource: "convert-to-employee", render: () => <HiringPipelineScreen /> },
];

export default function PipelineAndSubmissionsScreen() {
  return <TabbedScreen title="Pipeline & Submissions" tabs={TABS} />;
}
