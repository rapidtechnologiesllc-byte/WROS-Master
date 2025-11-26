import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

export default function Login({ onSwitch, onSuccess }) {
  const [role, setRole] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();

    const body = {
      UserRole: role,
      UserEmail: email,
      UserPassword: password,
    };

    try {
      const res = await fetch("http://localhost:8000/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      setMessage(data.message);

      if (data.success) {
        onSuccess(role); // go to dashboard
      }
    } catch (err) {
      setMessage("Server error. Check backend.");
    }
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-gradient-to-br from-[#1e293b] via-[#334155] to-[#669bf0]">
      <div className="w-full max-w-lg bg-white/10 backdrop-blur-xl rounded-2xl p-10 shadow-2xl text-white">

        <h2 className="text-3xl font-bold text-center mb-6">Welcome Back</h2>

        {message && <p className="text-center text-red-300 mb-2">{message}</p>}

        <form className="space-y-6" onSubmit={handleLogin}>

          {/* Role */}
          <div>
            <label className="block text-sm mb-2">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 text-white"
            >
              <option value="">Select role</option>
              <option value="HR">HR</option>
              <option value="Admin">Admin</option>
              <option value="Candidate">Candidate</option>
            </select>
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3"
              placeholder="Enter your email"
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm mb-2">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 pr-12"
                placeholder="Enter your password"
              />
              <button
                type="button"
                className="absolute right-4 top-3"
                onClick={() => setShowPassword(!showPassword)}
               >
                {showPassword ? <EyeOff size={20}/> : <Eye size={20}/>}
              </button>
            </div>
          </div>

          <button type="submit" className="w-full bg-blue-600 py-3 rounded-lg">
            Log In
          </button>
        </form>

        <p className="text-center text-sm mt-8">
          Don’t have an account?{" "}
          <button onClick={onSwitch} className="text-blue-300 underline">
            Sign up
          </button>
        </p>

      </div>
    </div>
  );
}
