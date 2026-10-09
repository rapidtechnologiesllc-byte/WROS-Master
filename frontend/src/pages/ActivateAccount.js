// Public: set your own password from the emailed single-use link
// (new employee activation or forgot-password). No session exists yet.
import { useState } from "react";
import { getApiBaseUrl, formatApiErrorMessage } from "../services/api/client";

const post = async (path, body) => {
  const response = await fetch(`${getApiBaseUrl()}/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }
  if (!response.ok) throw new Error(formatApiErrorMessage(data));
  return data;
};

export default function ActivateAccount() {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const setOwnPassword = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < 10) return setError("Use at least 10 characters.");
    if (password !== confirm) return setError("The two passwords don't match.");
    setBusy(true);
    try {
      const res = await post("/auth/activate", { token, new_password: password });
      setStatus(`Your password is set. Sign in as ${res.email}.`);
    } catch (err) {
      setError(err.message || "Could not set the password.");
    } finally {
      setBusy(false);
    }
  };

  const requestLink = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await post("/auth/forgot-password", { email });
      setStatus(res.message);
    } catch (err) {
      setError(err.message || "Could not send the link.");
    } finally {
      setBusy(false);
    }
  };

  const input = "w-full rounded-xl border px-3 py-2 text-sm outline-none focus:border-gray-900";
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-gray-900">{token ? "Set your password" : "Reset your password"}</h1>
        {status ? (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-gray-700">{status}</p>
            <a className="text-sm font-semibold text-blue-700 hover:underline" href="/auth">Go to sign in</a>
          </div>
        ) : token ? (
          <form className="mt-4 space-y-3" onSubmit={setOwnPassword}>
            <input className={input} type="password" placeholder="New password" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            <input className={input} type="password" placeholder="Repeat it" value={confirm}
              onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
            <button className="w-full rounded-xl bg-gray-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
              disabled={busy}>Set password</button>
          </form>
        ) : (
          <form className="mt-4 space-y-3" onSubmit={requestLink}>
            <input className={input} type="email" placeholder="Your work email" value={email}
              onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            <button className="w-full rounded-xl bg-gray-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
              disabled={busy || !email}>Email me a link</button>
          </form>
        )}
        {error ? <p className="mt-3 text-sm text-rose-700">{error}</p> : null}
      </div>
    </div>
  );
}
