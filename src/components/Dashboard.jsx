import { useState } from "react";
import { Bell, User, ChevronDown } from "lucide-react";

export default function Dashboard({ onInviteClick }) {
  const [openMenu, setOpenMenu] = useState(false);

  return (
    <div className="flex h-screen bg-gray-100">

      {/* Sidebar */}
      <aside className="w-64 bg-[#0f172a] text-gray-200 p-6 flex flex-col shadow-xl">
        <h1 className="text-2xl font-bold mb-10 tracking-wide text-white">
          HR and Admin Portal
        </h1>

        <nav className="space-y-3">
          <button className="w-full text-left text-lg hover:bg-[#1e293b] py-2 px-3 rounded-lg transition">
            Candidates
          </button>

          <button
            onClick={onInviteClick}
            className="w-full text-left text-lg hover:bg-[#1e293b] py-2 px-3 rounded-lg transition"
          >
            Invite a Candidate
          </button>
        </nav>

        <div className="mt-auto text-xs text-gray-400 pt-6 border-t border-gray-600">
          © 2025 BlitzenX Solutions
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col">
        

        {/* Top Bar */}
        <header className="w-full bg-white/80 backdrop-blur shadow-sm flex items-center justify-between px-6 py-4 border-b border-gray-200">

  {/* LEFT: Branding */}
  <h1 className="text-xl font-bold tracking-tight text-gray-800">
    BlitzenX Solutions
  </h1>

  {/* RIGHT: Icons */}
  <div className="flex items-center gap-6">
    <button className="text-gray-600 hover:text-black transition">
      <Bell size={22} />
    </button>

    <button
      onClick={() => setOpenMenu(!openMenu)}
      className="flex items-center gap-2 text-gray-700 hover:text-black cursor-pointer transition"
    >
      <User size={22} />
      <ChevronDown size={18} />
    </button>

    {/* Dropdown */}
    {openMenu && (
      <div className="absolute right-6 top-14 bg-white shadow-lg border border-gray-100 rounded-xl w-44 py-2 z-20">
        <button className="block w-full text-left px-4 py-2 hover:bg-gray-100 transition">
          View Profile
        </button>
        <button className="block w-full text-left px-4 py-2 hover:bg-gray-100 transition">
          Change Password
        </button>
        <button className="block w-full text-left px-4 py-2 hover:bg-gray-100 text-red-600 transition">
          Logout
        </button>
      </div>
    )}
  </div>
</header>


        {/* Dashboard Content */}
        <main className="flex-1 p-10">
          <h2 className="text-3xl font-bold text-gray-800 tracking-tight">HR and Admin Dashboard</h2>
          <p className="mt-2 text-gray-600 text-lg">Welcome to the onboarding system.</p>

          {/* Example Quick Stats Section */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
            <div className="bg-white shadow-md p-6 rounded-2xl border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-700">Total Candidates</h3>
              <p className="text-3xl font-bold mt-2 text-blue-600">34</p>
            </div>

            <div className="bg-white shadow-md p-6 rounded-2xl border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-700">Pending Invites</h3>
              <p className="text-3xl font-bold mt-2 text-purple-600">12</p>
            </div>

            <div className="bg-white shadow-md p-6 rounded-2xl border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-700">Completed Profiles</h3>
              <p className="text-3xl font-bold mt-2 text-green-600">22</p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
