import React, { useState } from "react";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./components/Dashboard";
import CandidateDashboard from "./components/CandidateDashboard";


export default function App() {
  const [screen, setScreen] = useState("auth");

  const handleAuthSuccess = (role) => {
    if (role === "HR" || role === "Admin") {
      setScreen("hradmin");
    } else if (role === "Candidate") {
      setScreen("candidate");
    }
  };

  return (
    <>
      {screen === "auth" && <AuthPage onAuthSuccess={handleAuthSuccess} />}

      {screen === "hradmin" && <Dashboard />}

      {screen === "candidate" && <CandidateDashboard />}
    </>
  );
}
