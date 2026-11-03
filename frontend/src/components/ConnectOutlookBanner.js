// Connect Outlook (CEO 2026-11-03): after setting their password, every user is asked to let HRMS read
// and send email as them, so emails they cause go from their own mailbox (the helpdesk mailbox is
// copied as the repository). Until they connect, those emails go from the helpdesk, and this
// banner stays on every page (it can be hidden for the browser session only).
import { useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { connectOutlook, getOutlookStatus } from "../services/api/msgraph";

const HIDE_KEY = "hrms_outlook_banner_hidden";

export default function ConnectOutlookBanner() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState(() => {
    try {
      return sessionStorage.getItem(HIDE_KEY) === "1";
    } catch (err) {
      console.warn("[ConnectOutlook] session storage unavailable:", err);
      return false;
    }
  });

  useEffect(() => {
    getOutlookStatus()
      .then(setStatus)
      .catch((err) => {
        // no Outlook permission for this account (e.g. a candidate): nothing to ask
        console.warn("[ConnectOutlook] status unavailable:", err?.message || err);
        setStatus(null);
      });
  }, []);

  if (!status || status.linked || hidden) return null;

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

  const hide = () => {
    try {
      sessionStorage.setItem(HIDE_KEY, "1");
    } catch (err) {
      console.warn("[ConnectOutlook] could not remember the choice:", err);
    }
    setHidden(true);
  };

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
      <Mail className="h-5 w-5 text-amber-700" />
      <div className="min-w-0 flex-1 text-sm text-amber-900">
        <span className="font-semibold">Connect your Outlook.</span> Emails you send from HRMS then go from your own
        mailbox, with the helpdesk copied, and replies come back to you.
        {status.last_error ? <span className="block text-xs text-amber-800">Last attempt: {status.last_error}</span> : null}
        {error ? <span className="block text-xs text-rose-700">{error}</span> : null}
      </div>
      <button type="button" onClick={connect} disabled={busy}
        className="rounded-lg bg-gray-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">
        {busy ? "Opening Microsoft…" : "Connect Outlook"}
      </button>
      <button type="button" onClick={hide} className="text-xs text-amber-800 underline">Later</button>
    </div>
  );
}
