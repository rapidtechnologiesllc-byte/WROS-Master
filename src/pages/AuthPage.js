// Auth page with sample-style two-step sign-in flow.
import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import {
  confirmMfaSetup,
  getAzureSigninUrl,
  login,
  resendCandidateEmailOtp,
  resendStaffEmailOtp,
  setCandidateEmail2faOptIn,
  setupMfa,
  verifyCandidateEmailOtp,
  verifyMfa,
  verifyStaffEmailOtp,
} from "../services/api/auth";
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

  // Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate half).
  // pendingOtpToken is the short-lived candidate_otp_pending token --
  // deliberately kept in React state, never written to hrms_token
  // (that slot means "real session" everywhere else in this app).
  const [pendingOtpToken, setPendingOtpToken] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpNotice, setOtpNotice] = useState("");
  const [show2faOptInPopup, setShow2faOptInPopup] = useState(false);

  // 2026-08-07 -- Staff MFA (Phase 1 B3). pendingMfaToken is the
  // short-lived mfa_pending token (same "never written to hrms_token"
  // discipline as pendingOtpToken above). mfaSetupData holds the
  // one-time-shown provisioning_uri/secret/backup_codes from /setup --
  // never re-fetchable, so it stays in React state only until the user
  // confirms enrollment.
  const [pendingMfaToken, setPendingMfaToken] = useState("");
  const [mfaSetupData, setMfaSetupData] = useState(null);
  const [mfaCode, setMfaCode] = useState("");
  const [useBackupCode, setUseBackupCode] = useState(false);
  const [staffOtpCode, setStaffOtpCode] = useState("");
  const [staffOtpNotice, setStaffOtpNotice] = useState("");

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

  // Shared by the direct-success path and the post-OTP-verify path --
  // stores the real session and either redirects immediately or, for a
  // never-asked candidate, shows the opt-in popup first.
  const finishLogin = async (data, { offer2faOptIn = false } = {}) => {
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

    if (offer2faOptIn) {
      setShow2faOptInPopup(true);
      return;
    }
    window.location.href = "/";
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
      localStorage.removeItem("hrms_active_bu_id");

      const data = await login({
        email: loginForm.UserEmail,
        password: loginForm.UserPassword,
      });

      // Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate
      // half): this candidate has opted into email 2FA -- data.access_token
      // here is a pending token, not a real session. Don't finish login.
      if (data?.candidate_otp_required && data?.access_token) {
        setPendingOtpToken(data.access_token);
        setStep("candidate-otp");
        return;
      }

      // Staff MFA (Phase 1 B3) -- the backend has always returned these
      // flags + a real mfa_pending token when the (off-by-default) gate
      // applies to this role; this frontend just never checked for them
      // before 2026-08-07. email_otp_required checked first since its
      // code is already sent server-side as part of this same login
      // call -- time-sensitive, shouldn't sit behind a TOTP step first.
      if (data?.access_token && data?.email_otp_required) {
        setPendingMfaToken(data.access_token);
        setStep("staff-email-otp");
        return;
      }
      if (data?.access_token && data?.mfa_setup_required) {
        setPendingMfaToken(data.access_token);
        setLoading(true);
        try {
          const setupData = await setupMfa(data.access_token);
          setMfaSetupData(setupData);
          setStep("mfa-setup");
        } catch (setupErr) {
          setError(setupErr.message || "Could not start MFA enrollment.");
        } finally {
          setLoading(false);
        }
        return;
      }
      if (data?.access_token && data?.mfa_required) {
        setPendingMfaToken(data.access_token);
        setStep("mfa-verify");
        return;
      }

      if (data?.access_token) {
        await finishLogin(data, { offer2faOptIn: Boolean(data?.show_2fa_opt_in_popup) });
        return;
      }
    } catch (err) {
      setError(err.message || "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  const submitCandidateOtp = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await verifyCandidateEmailOtp(pendingOtpToken, otpCode.trim());
      await finishLogin(data);
    } catch (err) {
      setError(err.message || "Invalid or expired code.");
    } finally {
      setLoading(false);
    }
  };

  // 2026-08-07 -- Staff MFA (Phase 1 B3). Confirms the just-generated
  // TOTP secret works (first successful code proves enrollment), then
  // finishes login with the real full token /setup/confirm returns.
  const submitMfaSetupConfirm = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await confirmMfaSetup(pendingMfaToken, mfaCode.trim());
      setMfaSetupData(null);
      await finishLogin(data);
    } catch (err) {
      setError(err.message || "Invalid code. Check your authenticator app and try again.");
    } finally {
      setLoading(false);
    }
  };

  // Already-enrolled path -- accepts either a fresh TOTP code or a
  // single-use backup code, same real /auth/mfa/verify contract.
  const submitMfaVerify = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = useBackupCode
        ? await verifyMfa(pendingMfaToken, { backupCode: mfaCode.trim() })
        : await verifyMfa(pendingMfaToken, { code: mfaCode.trim() });
      await finishLogin(data);
    } catch (err) {
      setError(err.message || "Invalid or expired code.");
    } finally {
      setLoading(false);
    }
  };

  const submitStaffEmailOtp = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await verifyStaffEmailOtp(pendingMfaToken, staffOtpCode.trim());
      await finishLogin(data);
    } catch (err) {
      setError(err.message || "Invalid or expired code.");
    } finally {
      setLoading(false);
    }
  };

  const handleResendStaffOtp = async () => {
    setError("");
    setStaffOtpNotice("");
    try {
      await resendStaffEmailOtp(pendingMfaToken);
      setStaffOtpNotice("A new code has been sent to your email.");
    } catch (err) {
      setError(err.message || "Could not resend the code.");
    }
  };

  const handleResendOtp = async () => {
    setError("");
    setOtpNotice("");
    try {
      await resendCandidateEmailOtp(pendingOtpToken);
      setOtpNotice("A new code has been sent to your email.");
    } catch (err) {
      setError(err.message || "Could not resend the code.");
    }
  };

  const handle2faOptInChoice = async (optedIn) => {
    try {
      await setCandidateEmail2faOptIn(optedIn);
    } catch (err) {
      // Non-blocking -- a failed preference save must never trap the
      // candidate on the login screen after they've already authenticated.
    } finally {
      setShow2faOptInPopup(false);
      window.location.href = "/";
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

          {step === "candidate-otp" ? (
            <form onSubmit={submitCandidateOtp} className="space-y-4">
              <p className="text-sm text-slate-600">
                We emailed a verification code to{" "}
                <span className="font-semibold">{loginForm.UserEmail}</span>.
                Enter it below to finish signing in.
              </p>
              {otpNotice ? (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                  {otpNotice}
                </div>
              ) : null}
              <div>
                <label className="mb-1 block text-sm font-semibold text-slate-700">
                  Verification Code
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-lg tracking-[0.5em] outline-none focus:border-bx-orange"
                  value={otpCode}
                  onChange={(event) =>
                    setOtpCode(event.target.value.replace(/[^0-9]/g, ""))
                  }
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-xl bg-bx-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-bx-orange-hover disabled:opacity-70"
                disabled={loading || otpCode.length !== 6}
              >
                {loading ? "Verifying..." : "Verify & Sign In"}
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800"
                onClick={handleResendOtp}
                disabled={loading}
              >
                Resend code
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800"
                onClick={() => {
                  setError("");
                  setOtpNotice("");
                  setOtpCode("");
                  setPendingOtpToken("");
                  setStep("password");
                }}
              >
                Go Back
              </button>
            </form>
          ) : step === "staff-email-otp" ? (
            <form onSubmit={submitStaffEmailOtp} className="space-y-4">
              <p className="text-sm text-slate-600">
                We emailed a verification code to{" "}
                <span className="font-semibold">{loginForm.UserEmail}</span>.
                Enter it below to finish signing in.
              </p>
              {staffOtpNotice ? (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                  {staffOtpNotice}
                </div>
              ) : null}
              <div>
                <label className="mb-1 block text-sm font-semibold text-slate-700">
                  Verification Code
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-lg tracking-[0.5em] outline-none focus:border-bx-orange"
                  value={staffOtpCode}
                  onChange={(event) =>
                    setStaffOtpCode(event.target.value.replace(/[^0-9]/g, ""))
                  }
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-xl bg-bx-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-bx-orange-hover disabled:opacity-70"
                disabled={loading || staffOtpCode.length !== 6}
              >
                {loading ? "Verifying..." : "Verify & Sign In"}
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800"
                onClick={handleResendStaffOtp}
                disabled={loading}
              >
                Resend code
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800"
                onClick={() => {
                  setError("");
                  setStaffOtpNotice("");
                  setStaffOtpCode("");
                  setPendingMfaToken("");
                  setStep("password");
                }}
              >
                Go Back
              </button>
            </form>
          ) : step === "mfa-setup" ? (
            <form onSubmit={submitMfaSetupConfirm} className="space-y-4">
              <p className="text-sm text-slate-600">
                Your account requires an authenticator app for sign-in. Scan
                this into Google Authenticator, Authy, or similar — or enter
                the key manually if you can't scan.
              </p>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Setup key (manual entry)
                </div>
                <div className="select-all break-all font-mono text-sm text-slate-800">
                  {mfaSetupData?.secret}
                </div>
              </div>
              {mfaSetupData?.backup_codes?.length ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
                    Backup codes — save these now, shown only once
                  </div>
                  <div className="grid grid-cols-2 gap-1 font-mono text-sm text-amber-900">
                    {mfaSetupData.backup_codes.map((c) => (
                      <div key={c}>{c}</div>
                    ))}
                  </div>
                </div>
              ) : null}
              <div>
                <label className="mb-1 block text-sm font-semibold text-slate-700">
                  Enter the 6-digit code from your app to confirm setup
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-lg tracking-[0.5em] outline-none focus:border-bx-orange"
                  value={mfaCode}
                  onChange={(event) => setMfaCode(event.target.value.replace(/[^0-9]/g, ""))}
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-xl bg-bx-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-bx-orange-hover disabled:opacity-70"
                disabled={loading || mfaCode.length !== 6}
              >
                {loading ? "Confirming..." : "Confirm & Sign In"}
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800"
                onClick={() => {
                  setError("");
                  setMfaCode("");
                  setMfaSetupData(null);
                  setPendingMfaToken("");
                  setStep("password");
                }}
              >
                Go Back
              </button>
            </form>
          ) : step === "mfa-verify" ? (
            <form onSubmit={submitMfaVerify} className="space-y-4">
              <p className="text-sm text-slate-600">
                Enter the 6-digit code from your authenticator app.
              </p>
              <div>
                <label className="mb-1 flex items-center justify-between text-sm font-semibold text-slate-700">
                  <span>{useBackupCode ? "Backup Code" : "Verification Code"}</span>
                  <button
                    type="button"
                    className="text-xs font-semibold text-bx-orange hover:underline"
                    onClick={() => {
                      setUseBackupCode((prev) => !prev);
                      setMfaCode("");
                    }}
                  >
                    {useBackupCode ? "Use authenticator code instead" : "Use a backup code instead"}
                  </button>
                </label>
                <input
                  type="text"
                  inputMode={useBackupCode ? "text" : "numeric"}
                  maxLength={useBackupCode ? 20 : 6}
                  required
                  autoFocus
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-lg tracking-[0.3em] outline-none focus:border-bx-orange"
                  value={mfaCode}
                  onChange={(event) =>
                    setMfaCode(useBackupCode ? event.target.value : event.target.value.replace(/[^0-9]/g, ""))
                  }
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-xl bg-bx-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-bx-orange-hover disabled:opacity-70"
                disabled={loading || !mfaCode}
              >
                {loading ? "Verifying..." : "Verify & Sign In"}
              </button>
              <button
                type="button"
                className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800"
                onClick={() => {
                  setError("");
                  setMfaCode("");
                  setUseBackupCode(false);
                  setPendingMfaToken("");
                  setStep("password");
                }}
              >
                Go Back
              </button>
            </form>
          ) : step === "email" ? (
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

      {show2faOptInPopup ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-md rounded-bx-lg bg-white p-6 shadow-2xl">
            <h2 className="mb-2 text-lg font-bold text-slate-900">
              Add an extra layer of security?
            </h2>
            <p className="mb-5 text-sm text-slate-600">
              You can turn on email verification for future sign-ins --
              we'll send a one-time code to your email each time you log
              in. You can change this anytime.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                className="flex-1 rounded-xl bg-bx-orange px-4 py-2.5 text-sm font-semibold text-white hover:bg-bx-orange-hover"
                onClick={() => handle2faOptInChoice(true)}
              >
                Enable
              </button>
              <button
                type="button"
                className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                onClick={() => handle2faOptInChoice(false)}
              >
                Not now
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
