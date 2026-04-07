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
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_10%_10%,#ffffff_0%,#eef2ff_38%,#e7eaf9_100%)] p-0 md:p-4 lg:p-6">
      <div className="pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-white/60 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-10 h-80 w-80 rounded-full bg-indigo-200/40 blur-3xl" />
      <div className="mx-auto flex min-h-screen w-full max-w-[1200px] items-stretch justify-center md:min-h-[calc(100vh-2rem)] lg:min-h-[calc(100vh-3rem)]">
        <div className="w-full overflow-hidden rounded-none border-0 bg-white/70 shadow-none backdrop-blur-xl backdrop-saturate-150 md:rounded-3xl md:border md:border-white/70 md:shadow-[0_25px_80px_rgba(15,23,42,0.18)]">
          <div className="grid min-h-screen md:min-h-[calc(100vh-2rem)] md:grid-cols-[0.95fr_1.25fr] lg:min-h-[calc(100vh-3rem)]">
            <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-white/10 bg-gradient-to-b from-[#08113f]/95 via-[#070c2f]/95 to-[#050a22]/95 p-8 text-white md:flex">
              <div className="pointer-events-none absolute inset-0 opacity-25">
                <div className="absolute -bottom-20 -right-16 h-56 w-56 rounded-full border-2 border-indigo-300/40" />
                <div className="absolute -bottom-28 -right-4 h-40 w-40 rounded-full border border-indigo-300/30" />
              </div>
              <div className="relative z-10">
                <img
                  src="/blitzenx-logo.svg"
                  alt="Blitzenx"
                  className="h-10 w-auto rounded-md border border-slate-700/80"
                />
                <p className="mt-12 text-xl font-semibold leading-snug">
                  Insights that drive action.
                </p>
                <p className="mt-3 text-sm leading-6 text-indigo-100">
                  Streamline candidate journeys from hiring to onboarding in one workflow.
                </p>
                <ul className="mt-8 space-y-3 text-sm text-indigo-100">
                  <li>- Candidate search and job matching</li>
                  <li>- Interview scheduling and tracking</li>
                  <li>- Offer, onboarding, and checklists</li>
                </ul>
              </div>
              <div className="relative z-10 text-xs text-indigo-200">
                Recruitment Suite
              </div>
            </aside>

            <main className="flex items-center p-5 sm:p-8 md:p-10 lg:p-12">
              <div className="mx-auto w-full max-w-md lg:max-w-lg">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Blitzenx HRMS
                </div>
                <h1 className="text-2xl font-bold text-slate-900">Welcome back</h1>
                <p className="mt-1 text-sm text-slate-500">
                  Sign in to continue
                </p>

                <div className="mt-6 grid grid-cols-2 gap-2 rounded-xl border border-white/80 bg-white/65 p-1 shadow-sm backdrop-blur sm:grid-cols-4">
                  <button
                    type="button"
                    className={`rounded-lg px-2 py-2 text-xs font-semibold ${
                      mode === "login"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600"
                    }`}
                    onClick={() => setMode("login")}
                  >
                    Login
                  </button>
                  <button
                    type="button"
                    className={`rounded-lg px-2 py-2 text-xs font-semibold ${
                      mode === "signup"
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-600"
                    }`}
                    onClick={() => setMode("signup")}
                  >
                    Sign Up
                  </button>
                  <button
                    type="button"
                    className={`rounded-lg px-2 py-2 text-xs font-semibold ${
                      mode === "azure"
                        ? "bg-white text-blue-700 shadow-sm"
                        : "text-blue-700/80"
                    }`}
                    onClick={() => setMode("azure")}
                  >
                    Azure SSO
                  </button>
                  <button
                    type="button"
                    className={`rounded-lg px-2 py-2 text-xs font-semibold ${
                      mode === "candidate"
                        ? "bg-white text-emerald-700 shadow-sm"
                        : "text-emerald-700/80"
                    }`}
                    onClick={() => setMode("candidate")}
                  >
                    Candidate
                  </button>
                </div>

                {error ? (
                  <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    {error}
                  </div>
                ) : null}
                {notice ? (
                  <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                    {notice}
                  </div>
                ) : null}

                <div className="mt-5">
                  {mode === "login" ? (
                    <form className="space-y-4" onSubmit={submitLogin}>
                      <div>
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <Mail className="h-4 w-4 text-slate-500" />
                          Email
                        </label>
                        <input
                          type="email"
                          required
                          className="w-full rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-sm outline-none backdrop-blur focus:border-slate-400"
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
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <Lock className="h-4 w-4 text-slate-500" />
                          Password
                        </label>
                        <input
                          type="password"
                          required
                          className="w-full rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-sm outline-none backdrop-blur focus:border-slate-400"
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
                        className="w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-70"
                        disabled={loading}
                      >
                        {loading ? "Signing in..." : "Login"}
                      </button>
                    </form>
                  ) : mode === "signup" ? (
                    <form className="space-y-4" onSubmit={submitSignup}>
                      <div>
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <User className="h-4 w-4 text-slate-500" />
                          Name
                        </label>
                        <input
                          type="text"
                          required
                          className="w-full rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-sm outline-none backdrop-blur focus:border-slate-400"
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
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <Mail className="h-4 w-4 text-slate-500" />
                          Email
                        </label>
                        <input
                          type="email"
                          required
                          className="w-full rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-sm outline-none backdrop-blur focus:border-slate-400"
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
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <Lock className="h-4 w-4 text-slate-500" />
                          Password
                        </label>
                        <input
                          type="password"
                          required
                          className="w-full rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-sm outline-none backdrop-blur focus:border-slate-400"
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
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <User className="h-4 w-4 text-slate-500" />
                          Role
                        </label>
                        <select
                          required
                          className="w-full rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-sm outline-none backdrop-blur focus:border-slate-400"
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
                        className="w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-70"
                        disabled={loading}
                      >
                        {loading ? "Creating account..." : "Create Account"}
                      </button>
                    </form>
                  ) : mode === "azure" ? (
                    <form className="space-y-4" onSubmit={submitAzure}>
                      <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                        Sign in with Azure Active Directory using your company account.
                      </div>
                      <button
                        type="submit"
                        className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-70"
                        disabled={loading}
                      >
                        Continue with Azure SSO
                      </button>
                      <button
                        type="button"
                        className="w-full rounded-lg border border-blue-200 px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-70"
                        onClick={completeAzure}
                        disabled={loading}
                      >
                        Complete Azure SSO
                      </button>
                    </form>
                  ) : (
                    <form className="space-y-4" onSubmit={submitCandidateLogin}>
                      <div>
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <Mail className="h-4 w-4 text-slate-500" />
                          Email
                        </label>
                        <input
                          type="email"
                          required
                          className="w-full rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-sm outline-none backdrop-blur focus:border-slate-400"
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
                        <label className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                          <Lock className="h-4 w-4 text-slate-500" />
                          Password
                        </label>
                        <input
                          type="password"
                          required
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
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
                        className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-70"
                        disabled={loading}
                      >
                        {loading ? "Signing in..." : "Login as Candidate"}
                      </button>
                    </form>
                  )}
                </div>
              </div>
            </main>
          </div>
        </div>
      </div>
    </div>
  );
}
