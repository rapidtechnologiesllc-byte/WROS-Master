// Auth page: login, signup, Azure SSO, and candidate login.
import React, { useState } from "react";
import { Lock, Mail, User } from "lucide-react";
import {
  candidateLogin,
  fetchAzureProfile,
  getAzureSigninUrl,
  login,
  signup
} from "../services/api/auth";

export default function AuthPage() {
  // mode controls which auth form is shown (login/signup/azure/candidate).
  const [mode, setMode] = useState("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loginForm, setLoginForm] = useState({
    UserEmail: "",
    UserPassword: ""
  });
  const [signupForm, setSignupForm] = useState({
    user_name: "",
    user_email: "",
    user_password: "",
    user_role: ""
  });
  const [candidateForm, setCandidateForm] = useState({
    candidate_email: "",
    candidate_password: ""
  });

  const submitLogin = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const data = await login(loginForm);
      if (data?.access_token) {
        localStorage.setItem("hrms_token", data.access_token);
        localStorage.setItem("hrms_user_type", "employee");
        if (data?.user_role) {
          localStorage.setItem("hrms_role", data.user_role.toUpperCase());
        }
        if (data?.user_name) {
          localStorage.setItem("hrms_user_name", data.user_name);
        }
        window.location.href = "/";
        return;
      }
      setNotice(`Welcome ${data?.user_name || ""}`.trim());
    } catch (err) {
      setError(err.message || "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  const submitSignup = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const data = await signup({
        ...signupForm,
        user_role: signupForm.user_role.trim().toUpperCase()
      });
      setNotice(data?.response || "User created successfully.");
      setMode("login");
    } catch (err) {
      setError(err.message || "Signup failed.");
    } finally {
      setLoading(false);
    }
  };

  const submitCandidateLogin = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    try {
      // Clear stale auth context before candidate auth attempt.
      localStorage.removeItem("hrms_token");
      localStorage.removeItem("hrms_role");
      localStorage.removeItem("hrms_user_name");
      localStorage.removeItem("hrms_user_email");
      localStorage.removeItem("hrms_candidate_id");
      localStorage.removeItem("hrms_user_type");

      // Candidate login uses a dedicated endpoint and role token.
      const data = await candidateLogin(candidateForm);
      if (!data?.access_token) {
        throw new Error("Candidate login failed: token not returned by server.");
      }
      localStorage.setItem("hrms_token", data.access_token);
      localStorage.setItem("hrms_user_type", "candidate");
      // Store candidate identity for role-based routing.
      localStorage.setItem("hrms_role", String(data?.candidate_role || "Candidate").toUpperCase());
      if (data?.candidate_name) {
        localStorage.setItem("hrms_user_name", data.candidate_name);
      }
      if (data?.candidate_email) {
        localStorage.setItem("hrms_user_email", data.candidate_email);
      }
      if (data?.candidate_id) {
        localStorage.setItem("hrms_candidate_id", data.candidate_id);
      }
      window.location.href = "/";
    } catch (err) {
      setError(err.message || "Candidate login failed.");
    } finally {
      setLoading(false);
    }
  };

  const submitAzure = (event) => {
    event.preventDefault();
    setError("");
    window.location.href = getAzureSigninUrl();
  };

  const completeAzure = async () => {
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const data = await fetchAzureProfile();
      if (data?.access_token) {
        localStorage.setItem("hrms_token", data.access_token);
        localStorage.setItem("hrms_user_type", "employee");
      }
      if (data?.user?.type) {
        localStorage.setItem("hrms_role", String(data.user.type).toUpperCase());
      }
      if (data?.user?.name || data?.user?.display_name) {
        localStorage.setItem(
          "hrms_user_name",
          data.user.name || data.user.display_name
        );
      }
      if (data?.user?.email) {
        localStorage.setItem("hrms_user_email", data.user.email);
      }
      window.location.href = "/";
    } catch (err) {
      setError(err.message || "SSO sign-in failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-5">
          <div>
            <p className="text-sm text-slate-500">Blitzenx HRMS</p>
            <h1 className="text-2xl font-semibold text-slate-900">
              Sign Up / Login
            </h1>
          </div>
          <a
            className="text-sm font-semibold text-slate-600 hover:text-slate-900"
            href="/"
          >
            Back to Job Flow
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-10">
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="mb-6 flex flex-wrap gap-3">
            <button
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                mode === "login"
                  ? "bg-slate-900 text-white"
                  : "border border-slate-200 text-slate-700"
              }`}
              onClick={() => setMode("login")}
            >
              Login
            </button>
            <button
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                mode === "signup"
                  ? "bg-slate-900 text-white"
                  : "border border-slate-200 text-slate-700"
              }`}
              onClick={() => setMode("signup")}
            >
              Sign Up
            </button>
            <button
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                mode === "azure"
                  ? "bg-blue-600 text-white"
                  : "border border-blue-200 text-blue-700"
              }`}
              onClick={() => setMode("azure")}
            >
              Azure SSO
            </button>
            <button
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                mode === "candidate"
                  ? "bg-emerald-600 text-white"
                  : "border border-emerald-200 text-emerald-700"
              }`}
              onClick={() => setMode("candidate")}
            >
              Candidate Login
            </button>
          </div>

          {error ? (
            <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          ) : null}
          {notice ? (
            <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              {notice}
            </div>
          ) : null}

          {mode === "login" ? (
            <form className="space-y-4" onSubmit={submitLogin}>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Mail className="h-4 w-4 text-slate-500" />
                  Email
                </label>
                <input
                  type="email"
                  required
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={loginForm.UserEmail}
                  onChange={(event) =>
                    setLoginForm((prev) => ({
                      ...prev,
                      UserEmail: event.target.value
                    }))
                  }
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Lock className="h-4 w-4 text-slate-500" />
                  Password
                </label>
                <input
                  type="password"
                  required
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={loginForm.UserPassword}
                  onChange={(event) =>
                    setLoginForm((prev) => ({
                      ...prev,
                      UserPassword: event.target.value
                    }))
                  }
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-70"
                disabled={loading}
              >
                {loading ? "Signing in..." : "Login"}
              </button>
            </form>
          ) : mode === "signup" ? (
            <form className="space-y-4" onSubmit={submitSignup}>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <User className="h-4 w-4 text-slate-500" />
                  Name
                </label>
                <input
                  type="text"
                  required
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={signupForm.user_name}
                  onChange={(event) =>
                    setSignupForm((prev) => ({
                      ...prev,
                      user_name: event.target.value
                    }))
                  }
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Mail className="h-4 w-4 text-slate-500" />
                  Email
                </label>
                <input
                  type="email"
                  required
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={signupForm.user_email}
                  onChange={(event) =>
                    setSignupForm((prev) => ({
                      ...prev,
                      user_email: event.target.value
                    }))
                  }
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Lock className="h-4 w-4 text-slate-500" />
                  Password
                </label>
                <input
                  type="password"
                  required
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={signupForm.user_password}
                  onChange={(event) =>
                    setSignupForm((prev) => ({
                      ...prev,
                      user_password: event.target.value
                    }))
                  }
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <User className="h-4 w-4 text-slate-500" />
                  Role
                </label>
                <select
                  required
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={signupForm.user_role}
                  onChange={(event) =>
                    setSignupForm((prev) => ({
                      ...prev,
                      user_role: event.target.value
                    }))
                  }
                >
                  <option value="">Select role</option>
                  <option value="HR">HR</option>
                  <option value="Admin">Admin</option>
                </select>
              </div>
              <button
                type="submit"
                className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-70"
                disabled={loading}
              >
                {loading ? "Creating account..." : "Create Account"}
              </button>
            </form>
          ) : (
            mode === "azure" ? (
              <form className="space-y-4" onSubmit={submitAzure}>
                <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  Sign in with Azure Active Directory using your company account.
                </div>
                <button
                  type="submit"
                  className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-70"
                  disabled={loading}
                >
                  Continue with Azure SSO
                </button>
                <button
                  type="button"
                  className="w-full rounded-lg border border-blue-200 px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-70"
                  onClick={completeAzure}
                  disabled={loading}
                >
                  Complete Azure SSO
                </button>
              </form>
            ) : (
              <form className="space-y-4" onSubmit={submitCandidateLogin}>
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                    <Mail className="h-4 w-4 text-slate-500" />
                    Email
                  </label>
                  <input
                    type="email"
                    required
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={candidateForm.candidate_email}
                    onChange={(event) =>
                      setCandidateForm((prev) => ({
                        ...prev,
                        candidate_email: event.target.value
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                    <Lock className="h-4 w-4 text-slate-500" />
                    Password
                  </label>
                  <input
                    type="password"
                    required
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={candidateForm.candidate_password}
                    onChange={(event) =>
                      setCandidateForm((prev) => ({
                        ...prev,
                        candidate_password: event.target.value
                      }))
                    }
                  />
                </div>
                <button
                  type="submit"
                  className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-70"
                  disabled={loading}
                >
                  {loading ? "Signing in..." : "Login as Candidate"}
                </button>
              </form>
            )
          )}
        </div>
      </main>
    </div>
  );
}
