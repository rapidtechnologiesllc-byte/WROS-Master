
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

export default function Login({ onSwitch }) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-gradient-to-br from-[#1e293b] via-[#334155] to-[#669bf0]">
      <div className="w-full max-w-lg bg-white/10 backdrop-blur-xl rounded-2xl p-10 shadow-2xl text-white">
        {/* Heading */}
        <h2 className="text-3xl font-bold text-center mb-3">Welcome Back</h2>
        <p className="text-center text-gray-300 mb-8">Log in to your account</p>

        {/* Form */}
        <form className="space-y-6">
          {/* Email */}
          <div>
            <label className="block text-sm mb-2">Email Address</label>
            <input
              type="email"
              className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 text-white placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter your email"
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm mb-2">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                className="w-full bg-white/20 border border-white/30 rounded-lg px-4 py-3 pr-12 text-white placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your password"
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

          {/* Remember me + Forgot password */}
          <div className="flex items-center justify-between text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" className="h-4 w-4 accent-blue-500" />
              Remember me
            </label>
            <button type="button" className="text-blue-300 hover:underline">
              Forgot password?
            </button>
          </div>

          {/* Log In button */}
          <button
            type="submit"
            className="w-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white py-3 rounded-lg font-semibold hover:opacity-90 transition"
          >
            Log In
          </button>
        </form>

        {/* Footer */}
        <p className="text-center text-sm text-gray-300 mt-8">
          Don't have an account?{" "}
          <button onClick={onSwitch} className="text-blue-300 font-medium hover:underline">
            Sign up
          </button>
        </p>
      </div>
    </div>
  );
}
