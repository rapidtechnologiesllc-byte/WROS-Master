import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
 
export default function Signup({ onSwitch }) {
  const [role, setRole] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [message, setMessage] = useState("");
 
  const handleSignup = async (e) => {
    e.preventDefault();
 
    if (password !== confirmPassword) {
      setMessage("Passwords do not match");
      return;
    }
 
    const body = {
      UserRole: role,
      UserName: name,
      UserEmail: email,
      UserPassword: password,
    };
 
    try {
      const res = await fetch("http://localhost:8000/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
 
    if (!res.ok) {
  const err = await res.json();

  // Handle FastAPI validation error format
  if (Array.isArray(err.detail)) {
    setMessage(err.detail[0].msg);  // show only the message
  } else if (typeof err.detail === "string") {
    setMessage(err.detail);
  } else {
    setMessage("Signup failed");
  }
  
  return;
}

 
      setMessage("Signup successful! You can now log in.");
      setTimeout(() => onSwitch(), 1500); // switch to login
    } catch (err) {
      setMessage("Server error. Check backend.");
    }
  };
 
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-gradient-to-br from-[#1e293b] via-[#334155] to-[#669bf0]">
      <div className="w-full max-w-lg bg-white/10 backdrop-blur-xl rounded-2xl p-10 shadow-2xl text-white">
       
        <h2 className="text-3xl font-bold text-center mb-3">Create Your Account</h2>
        <p className="text-center text-gray-300 mb-8">Sign up to get started</p>
 
       <form className="grid grid-cols-1 md:grid-cols-2 gap-6" onSubmit={handleSignup}>

  {/* Role (full width) */}
  <div className="col-span-2">
    <label className="block text-sm mb-2">Role</label>
    <select
      value={role}
      onChange={(e) => setRole(e.target.value)}
      className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 text-white"
    >
      <option value="" className="text-black">Select role</option>
      <option value="HR" className="text-black">HR</option>
      <option value="Admin" className="text-black">Admin</option>
      <option value="Candidate" className="text-black">Candidate</option>
    </select>
  </div>

  {/* Name */}
  <div>
    <label className="block text-sm mb-2">Full Name</label>
    <input
      type="text"
      value={name}
      onChange={(e) => setName(e.target.value)}
      className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 text-white"
      placeholder="Enter your name"
    />
  </div>

  {/* Email */}
  <div>
    <label className="block text-sm mb-2">Email Address</label>
    <input
      type="email"
      value={email}
      onChange={(e) => setEmail(e.target.value)}
      className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 text-white"
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
        className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 pr-12 text-white"
        placeholder="Enter password"
      />
      <button
        type="button"
        onClick={() => setShowPassword(!showPassword)}
        className="absolute right-4 top-3 text-gray-300 hover:text-white"
      >
        {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
      </button>
    </div>
  </div>

  {/* Confirm Password */}
  <div>
    <label className="block text-sm mb-2">Confirm Password</label>
    <div className="relative">
      <input
        type={showConfirmPassword ? "text" : "password"}
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 pr-12 text-white"
        placeholder="Confirm password"
      />
      <button
        type="button"
        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
        className="absolute right-4 top-3 text-gray-300 hover:text-white"
      >
        {showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
      </button>
    </div>
  </div>

  {/* Submit button full width */}
  <div className="col-span-2">
    <button
      type="submit"
      className="w-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white py-3 rounded-lg font-semibold hover:opacity-90 transition"
    >
      Sign Up
    </button>

    {message && (
      <p className="text-center text-sm text-red-300 mt-2">{message}</p>
    )}
  </div>

</form>

 
         <p className="text-center text-sm text-gray-300 mt-8">
          Already have an account?{" "}
          <button onClick={onSwitch} className="text-blue-300 font-medium hover:underline">
            Log in
          </button>
        </p>
      </div>
    </div>
  );
}
 
 