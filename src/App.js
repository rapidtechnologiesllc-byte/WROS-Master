// src/App.js
import React, { useState } from "react";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./components/Dashboard";
import CandidateDashboard from "./components/CandidateDashboard";

export default function App() {
  const [screen, setScreen] = useState("auth");
  const [currentUser, setCurrentUser] = useState(null);

  const handleAuthSuccess = (userObj) => {
    // userObj should be the full user object returned from /login
    setCurrentUser(userObj);
    if (userObj.UserRole === "HR" || userObj.UserRole === "Admin") {
      setScreen("hradmin");
    } else if (userObj.UserRole === "Candidate") {
      setScreen("candidate");
    } else {
      // fallback
      setScreen("auth");
    }
  };

  return (
    <>
      {screen === "auth" && <AuthPage onAuthSuccess={handleAuthSuccess} />}
      {screen === "hradmin" && <Dashboard currentUser={currentUser} />}
      {screen === "candidate" && (
        <CandidateDashboard currentUser={currentUser} />
      )}
    </>
  );
}
