// Auth page with sample-style two-step sign-in flow.
import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { getAzureSigninUrl, login } from "../services/api/auth";
import { getHrMe } from "../services/api/users";

export default function AuthPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState("email");
  const [loginForm, setLoginForm] = useState({
    UserEmail: "",
    UserPassword: "",
  });
  const [showPassword, setShowPassword] = useState(false);

  const handleNext = (event) => {
    event.preventDefault();
    setError("");
    if (!String(loginForm.UserEmail || "").trim()) {
      setError("Email is required.");
      return;
    }
    setStep("password");
  };

  const getCurrentUser = async () => {
    try {
      const response = await getHrMe();
      const user = response;
      return user;
    } catch (error) {
      console.error("Failed to fetch user details", error);
      return null;
    }
  };

  const submitLogin = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      // Clear stale auth context before a fresh unified login attempt.
      localStorage.removeItem("hrms_token");
      localStorage.removeItem("hrms_role");
      localStorage.removeItem("hrms_user_name");
      localStorage.removeItem("hrms_user_email");
      localStorage.removeItem("hrms_candidate_id");
      localStorage.removeItem("hrms_user_type");

      const data = await login({
        email: loginForm.UserEmail,
        password: loginForm.UserPassword,
      });
      if (data?.access_token) {
        localStorage.setItem("hrms_token", data.access_token);
        const user = await getCurrentUser();
        if (user) {
          localStorage.setItem("user_info", JSON.stringify(user));
          localStorage.setItem("permission_role", user.permission_role);
        }
        const entityType = String(data?.entity_type || "")
          .trim()
          .toLowerCase();
        const looksLikeCandidate =
          entityType === "candidate" ||
          Boolean(
            data?.candidate_id || data?.candidate_email || data?.candidate_role,
          );

        localStorage.setItem("hrms_token", data.access_token);
        if (looksLikeCandidate) {
          localStorage.setItem("hrms_user_type", "candidate");
          localStorage.setItem(
            "hrms_role",
            String(data?.candidate_role || "Candidate").toUpperCase(),
          );
          if (data?.candidate_name) {
            localStorage.setItem("hrms_user_name", data.candidate_name);
          }
          if (data?.candidate_email) {
            localStorage.setItem("hrms_user_email", data.candidate_email);
          }
          if (data?.candidate_id) {
            localStorage.setItem("hrms_candidate_id", data.candidate_id);
          }
        } else {
          localStorage.setItem("hrms_user_type", "employee");
          if (data?.user_role) {
            localStorage.setItem("hrms_role", data.user_role.toUpperCase());
          }
          if (data?.user_name) {
            localStorage.setItem("hrms_user_name", data.user_name);
          }
          if (data?.user_email) {
            localStorage.setItem("hrms_user_email", data.user_email);
          }
        }
        window.location.href = "/";
        return;
      }
    } catch (err) {
      setError(err.message || "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-bx-navy">
      <div className="pointer-events-none absolute bottom-0 left-1/3 h-52 w-52 rotate-12 rounded-2xl bg-bx-orange/20" />
      <div className="pointer-events-none absolute bottom-0 right-14 h-56 w-56 -rotate-12 rounded-3xl bg-bx-orange/10" />
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col items-center justify-center px-4 py-8">
        <img
          src="/blitzenx-logo.svg"
          alt="Blitzenx"
          className="mb-6 h-12 w-auto rounded-bx shadow-lg"
        />
        <p className="mb-8 max-w-xl text-center text-sm font-medium italic text-white/70">
          Behind you to keep the business moving. Beside you to execute &amp;
          deliver. In front of you when accountability matters.
        </p>
        <h1 className="mb-8 text-center text-4xl font-extrabold text-white">
          Sign In to Your Account
        </h1>

        <div className="w-full max-w-xl rounded-bx-lg border border-bx-border bg-white/95 p-7 shadow-xl">
          {error ? (
            <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          {step === "email" ? (
            <form onSubmit={handleNext} className="space-y-5">
              <div>
                <label className="mb-1 block text-sm font-semibold text-slate-700">
                  Email Address
                </label>
                <input
                  type="email"
                  required
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-bx-orange"
                  value={loginForm.UserEmail}
                  onChange={(event) =>
                    setLoginForm((prev) => ({
                      ...prev,
                      UserEmail: event.target.value,
                    }))
                  }
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-xl bg-bx-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-bx-orange-hover disabled:opacity-70"
                disabled={loading}
              >
                Next
              </button>
            </form>
          ) : (
            <form onSubmit={submitLogin} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-semibold text-slate-700">
                  Email Address
                </label>
                <input
                  type="email"
                  readOnly
                  className="w-full rounded-xl border border-slate-300 bg-slate-100 px-3 py-2.5 text-sm text-slate-600 outline-none"
                  value={loginForm.UserEmail}
                />
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between text-sm font-semibold text-slate-700">
                  <span>Password</span>
                  <button
                    type="button"
                    className="text-sm font-semibold text-bx-orange hover:underline"
                    onClick={() =>
                      setError("Please contact admin to reset your password.")
                    }
                  >
                    Forgot Password?
                  </button>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 pr-10 text-sm outline-none focus:border-bx-orange"
                    value={loginForm.UserPassword}
                    onChange={(event) =>
                      setLoginForm((prev) => ({
                        ...prev,
                        UserPassword: event.target.value,
                      }))
                    }
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500"
                    onClick={() => setShowPassword((prev) => !prev)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>
              <button
                type="submit"
                className="w-full rounded-xl bg-bx-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-bx-orange-hover disabled:opacity-70"
                disabled={loading}
              >
                {loading ? "Signing in..." : "Sign In"}
              </button>
              <button
                type="button"
                className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-70"
                onClick={() => {
                  setError("");
                  window.location.href = getAzureSigninUrl();
                }}
                disabled={loading}
              >
                Sign in with Microsoft
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800"
                onClick={() => {
                  setError("");
                  setStep("email");
                  setLoginForm((prev) => ({ ...prev, UserPassword: "" }));
                }}
              >
                Go Back
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
