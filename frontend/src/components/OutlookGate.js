// Connect Outlook is mandatory (CEO 2026-11-03: "this is mandatory and not optional. we need to read and
// process every email to find new jobs, new candidate, client updates and escalations"). Anyone with a
// company mailbox who has not connected sees only this step: HRMS opens once Microsoft confirms the
// connection. An admin of users and access may carry on for this browser session (so a Microsoft setup
// problem can be fixed); nobody else can skip it.
import { useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { connectOutlook, getOutlookStatus } from "../services/api/msgraph";

const DEFER_KEY = "hrms_outlook_deferred";

const deferred = () => {
  try {
    return sessionStorage.getItem(DEFER_KEY) === "1";
  } catch (err) {
    console.warn("[ConnectOutlook] session storage unavailable:", err);
    return false;
  }
};

export default function OutlookGate({ children }) {
  const [status, setStatus] = useState(null);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("outlook") === "error" ? params.get("reason") || "Microsoft did not connect your Outlook." : "";
  });
  const [busy, setBusy] = useState(false);
  const [skipped, setSkipped] = useState(deferred);

  useEffect(() => {
    getOutlookStatus()
      .then(setStatus)
      .catch((err) => {
        // no Outlook permission for this account: nothing to ask
        console.warn("[ConnectOutlook] status unavailable:", err?.message || err);
        setStatus(null);
      })
      .finally(() => setChecked(true));
  }, []);

  if (!checked) return null;
  if (!status || status.linked || !status.required || (skipped && status.can_defer)) return children;

  const connect = async () => {
    setBusy(true);
    setError("");
    try {
      await connectOutlook();
    } catch (err) {
      setError(err.message || "Could not start the Microsoft sign-in.");
      setBusy(false);
    }
  };

  const skip = () => {
    try {
      sessionStorage.setItem(DEFER_KEY, "1");
    } catch (err) {
      console.warn("[ConnectOutlook] could not remember the choice:", err);
    }
    setSkipped(true);
  };

  return (
    <div className="mx-auto mt-10 max-w-xl rounded-2xl border bg-white p-8 text-center shadow-sm">
      <Mail className="mx-auto h-10 w-10 text-amber-600" />
      <h1 className="mt-4 text-xl font-semibold text-gray-900">Connect your Outlook to continue</h1>
      <p className="mt-3 text-sm text-gray-600">
        HRMS sends your emails from your own mailbox (the helpdesk is copied) and reads your email to pick up new
        jobs, new candidates, client updates and escalations. Sign in with your work Microsoft account and allow
        access; HRMS opens as soon as it is connected.
      </p>
      {status.last_error || error ? (
        <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error || status.last_error}
        </p>
      ) : null}
      <button type="button" onClick={connect} disabled={busy}
        className="mt-6 rounded-lg bg-gray-900 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
        {busy ? "Opening Microsoft…" : "Connect Outlook"}
      </button>
      {status.can_defer ? (
        <div className="mt-4">
          <button type="button" onClick={skip} className="text-xs text-gray-500 underline">
            Continue for now (admins only, to fix the Microsoft setup)
          </button>
        </div>
      ) : null}
    </div>
  );
}
