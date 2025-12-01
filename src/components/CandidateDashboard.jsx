// NEW INSIDE CandidateDashboard.jsx

import CandidateFormPage from "./CandidateFormPage";
import { useState } from "react";

export default function CandidateDashboard({ currentUser }) {
  const [activePage, setActivePage] = useState("dashboard");

  return (
    <div className="flex h-screen bg-gray-100">

      {/* Sidebar */}
      <aside className="w-64 bg-[#1e293b] text-gray-200 p-6 shadow-xl flex flex-col">
        <h1 className="text-2xl font-bold mb-10 text-white tracking-wide">Candidate Portal</h1>

        <nav className="space-y-3">
          <button onClick={() => setActivePage("profile")}
                  className="w-full text-left text-lg hover:bg-[#334155] py-2 px-3 rounded-lg flex items-center gap-2">
            Profile
          </button>

          <button onClick={() => setActivePage("documents")}
                  className="w-full text-left text-lg hover:bg-[#334155] py-2 px-3 rounded-lg flex items-center gap-2">
            Documents
          </button>

          <button onClick={() => setActivePage("tasks")}
                  className="w-full text-left text-lg hover:bg-[#334155] py-2 px-3 rounded-lg flex items-center gap-2">
            Tasks
          </button>

          {/* NEW — Candidate Form in Sidebar */}
          <button onClick={() => setActivePage("candidateForm")}
                  className="w-full text-left text-lg hover:bg-[#334155] py-2 px-3 rounded-lg flex items-center gap-2">
            Candidate Form
          </button>
        </nav>

        <div className="mt-auto text-xs text-gray-400 border-t border-gray-600 pt-6">
          © 2025 BlitzenX Solutions
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        
        {/* Header */}
        <header className="w-full bg-white shadow-sm flex items-center justify-between px-6 py-4 border-b">
          <h1 className="text-xl font-bold text-gray-800">BlitzenX Onboarding</h1>
          <div className="text-gray-600">{currentUser?.UserName}</div>
        </header>
        

        {/* Conditional Page Rendering */}
        <main className="flex-1 overflow-auto">
          {activePage === "dashboard" && (
            <div className="p-10">
              <h2 className="text-3xl font-bold text-gray-800">Candidate Dashboard</h2>
              <p className="mt-2 text-gray-600">Manage your onboarding progress.</p>

               <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
            <div className="bg-white shadow-md p-6 rounded-xl border">
              <h3 className="text-lg font-semibold text-gray-700">Profile Completion</h3>
              <p className="text-3xl font-bold mt-2 text-blue-600">70%</p>
            </div>
             <div className="bg-white shadow-md p-6 rounded-xl border">
              <h3 className="text-lg font-semibold text-gray-700">Documents Submitted</h3>
              <p className="text-3xl font-bold mt-2 text-green-600">4 / 6</p>
             </div>
            <div className="bg-white shadow-md p-6 rounded-xl border">
              <h3 className="text-lg font-semibold text-gray-700">Pending Tasks</h3>
              <p className="text-3xl font-bold mt-2 text-red-500">2</p>
            </div>
           </div>
            </div>

            
          )}

          {activePage === "candidateForm" && (
            <CandidateFormPage currentUser={currentUser} />
          )}

          {/* You can add components for profile/documents/tasks later */}
        </main>

      </div>
    </div>
  );
}
