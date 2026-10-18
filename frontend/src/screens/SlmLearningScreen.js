// SLM Learning (CEO 2026-10-17): the resume-parser model's accuracy and retraining (SLM Dashboard),
// its training data, and the learning-transcript audit, in one screen. Each tab keeps its screen
// and the permission its API checks (slm-dashboard / slm-training-data; the transcript API is
// gated by slm-dashboard).
import TabbedScreen from "../components/TabbedScreen";
import SLMDashboard from "./SLMDashboard";
import SLMTrainingData from "./SLMTrainingData";
import SLMLearningTranscript from "./SLMLearningTranscript";

const TABS = [
  { key: "dashboard", label: "Model", resource: "slm-dashboard", render: () => <SLMDashboard /> },
  { key: "training", label: "Training Data", resource: "slm-training-data", render: () => <SLMTrainingData /> },
  { key: "transcript", label: "Learning Transcript", resource: "slm-dashboard", render: () => <SLMLearningTranscript /> },
];

export default function SlmLearningScreen() {
  return <TabbedScreen title="SLM Learning" tabs={TABS} />;
}
