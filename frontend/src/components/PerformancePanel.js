// Performance (CEO 2026-10-24): an employee's reviews by their reporting chain and the praise,
// feedback and internal notes about them. What shows is what the server lets this viewer see
// (GET /performance/employees/{id} or /performance/me); the reviewer writes their review here.
import { useEffect, useState } from "react";
import { Video } from "lucide-react";
import { Button, Input, TextArea } from "./ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";
import { alertDialog } from "../utils/dialogs";
import {
  addNote, giveFeedback, linkRecording, recordingBlobUrl, uploadRecording, writeReview,
} from "../services/api/performance";

const STATUS_TONE = {
  PENDING: "border-blue-200 bg-blue-50 text-blue-800",
  SCHEDULED: "border-purple-200 bg-purple-50 text-purple-800",
  COMPLETED: "border-green-200 bg-green-50 text-green-800",
  MISSED: "border-rose-200 bg-rose-50 text-rose-800",
  CANCELLED: "border-gray-200 bg-gray-100 text-gray-600",
};
const VISIBILITY_LABEL = {
  EMPLOYEE_AND_CHAIN: "The employee and their reporting chain",
  CHAIN_ONLY: "Reporting chain only",
};
const label = (value) => (value || "").replace(/_/g, " ").toLowerCase();
const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "");

function Recording({ review }) {
  const [src, setSrc] = useState(null);
  const [error, setError] = useState("");
  if (!review.has_recording) return null;
  if (review.recording_source === "LINK") {
    return <a href={review.recording_url} target="_blank" rel="noreferrer" className="text-sm text-blue-700 hover:underline">Open the recording</a>;
  }
  const load = async () => {
    setError("");
    try {
      setSrc(await recordingBlobUrl(review.id));
    } catch (err) {
      console.error("[Performance] Failed to load recording:", err);
      setError(err.message);
    }
  };
  return (
    <div className="space-y-1">
      {src ? (
        <video src={src} controls className="w-full max-w-xl rounded-lg border">
          <track kind="captions" />
        </video>
      ) : (
        <Button variant="secondary" size="sm" onClick={load}><Video className="h-4 w-4" /> Play recording</Button>
      )}
      {error ? <div className="text-xs text-rose-700">{error}</div> : null}
    </div>
  );
}

function ReviewForm({ review, ratingMax, visibilities, onSaved }) {
  const [form, setForm] = useState({
    rating: review.rating ? String(review.rating) : "", summary: review.summary || "", strengths: review.strengths || "",
    improvements: review.improvements || "", goals: review.goals || "", visibility: review.visibility,
  });
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (field) => (value) => setForm((current) => ({ ...current, [field]: value }));

  const run = async (action) => {
    setBusy(true);
    setError("");
    try {
      await action();
      onSaved();
    } catch (err) {
      console.error("[Performance] Review update failed:", err);
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const save = (complete) => run(() => writeReview(review.id, {
    ...form, rating: form.rating === "" ? null : Number(form.rating), complete,
  }));

  return (
    <div className="space-y-3 rounded-xl border bg-gray-50 p-4">
      <div>
        <div className="mb-1 text-xs font-semibold text-gray-700">Rating</div>
        <div className="flex gap-1" role="radiogroup" aria-label="Rating">
          {Array.from({ length: ratingMax }, (_, i) => String(i + 1)).map((value) => (
            <button key={value} type="button" role="radio" aria-checked={form.rating === value}
              onClick={() => set("rating")(value)}
              className={cx("h-9 w-9 rounded-lg border text-sm font-semibold",
                form.rating === value ? "border-bx-navy bg-bx-navy text-white" : "bg-white text-gray-700 hover:bg-gray-100")}>
              {value}
            </button>
          ))}
        </div>
      </div>
      <TextArea label="Summary" value={form.summary} onChange={set("summary")} rows={3} />
      <div className="grid gap-3 md:grid-cols-3">
        <TextArea label="Strengths" value={form.strengths} onChange={set("strengths")} rows={3} />
        <TextArea label="To improve" value={form.improvements} onChange={set("improvements")} rows={3} />
        <TextArea label="Goals for next period" value={form.goals} onChange={set("goals")} rows={3} />
      </div>
      <fieldset>
        <legend className="mb-1 text-xs font-semibold text-gray-700">Who can see this review</legend>
        <div className="flex flex-wrap gap-4 text-sm">
          {visibilities.map((value) => (
            <label key={value} className="inline-flex items-center gap-2">
              <input type="radio" name={`visibility-${review.id}`} checked={form.visibility === value}
                onChange={() => set("visibility")(value)} />
              {VISIBILITY_LABEL[value] || label(value)}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-end gap-2 border-t pt-3">
        <label className="text-sm">
          <span className="mb-1 block text-xs font-semibold text-gray-700">Attach the recording</span>
          <input type="file" accept="video/*,audio/*" disabled={busy}
            onChange={(e) => e.target.files[0] && run(() => uploadRecording(review.id, e.target.files[0]))} />
        </label>
        <span className="text-xs text-gray-500">or</span>
        <div className="min-w-[240px] flex-1"><Input label="Recording link (https://)" value={link} onChange={setLink} /></div>
        <Button variant="secondary" size="sm" disabled={busy || !link.trim()}
          onClick={() => run(() => linkRecording(review.id, link.trim()))}>Save link</Button>
      </div>
      {error ? <div className="text-sm text-rose-700">{error}</div> : null}
      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => save(false)} disabled={busy}>Save draft</Button>
        <Button onClick={() => save(true)} disabled={busy}>Complete review</Button>
      </div>
    </div>
  );
}

function ReviewCard({ review, open, onToggle, ratingMax, visibilities, onSaved }) {
  return (
    <div id={`review-${review.id}`} className={cx("rounded-2xl border bg-white p-4 shadow-sm", open && "ring-2 ring-bx-orange")}>
      <button type="button" onClick={onToggle} className="flex w-full flex-wrap items-center justify-between gap-2 text-left">
        <div>
          <div className="font-semibold text-gray-900">{review.level_label} review · {review.reviewer_name}</div>
          <div className="text-xs text-gray-500">{review.period_start} to {review.period_end} · due {review.due_date}</div>
        </div>
        <div className="flex items-center gap-2">
          {review.rating ? <span className="text-sm font-semibold text-gray-700">{review.rating}/{ratingMax}</span> : null}
          <span className={cx(pill, STATUS_TONE[review.status])}>{label(review.status)}</span>
        </div>
      </button>
      {open && (
        <div className="mt-4 space-y-3 text-sm">
          {review.meeting_start ? (
            <div>
              Meeting {when(review.meeting_start)}
              {review.meeting_join_url ? <> · <a href={review.meeting_join_url} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">Join on Teams</a></> : null}
            </div>
          ) : review.status === "PENDING" ? (
            <div className="text-gray-500">{review.meeting_note || "No meeting booked yet: set up a Teams meeting and record it."}</div>
          ) : null}
          <Recording review={review} />
          {review.recording_fetch_error && !review.has_recording ? (
            <div className="text-xs text-amber-700">Recording: {review.recording_fetch_error}</div>
          ) : null}
          {review.can_write ? (
            <ReviewForm review={review} ratingMax={ratingMax} visibilities={visibilities} onSaved={onSaved} />
          ) : review.summary ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div className="md:col-span-2"><div className="text-xs font-semibold uppercase text-gray-500">Summary</div>{review.summary}</div>
              {[["Strengths", review.strengths], ["To improve", review.improvements], ["Goals", review.goals]]
                .filter(([, text]) => text).map(([title, text]) => (
                  <div key={title}><div className="text-xs font-semibold uppercase text-gray-500">{title}</div>{text}</div>
                ))}
              <div className="text-xs text-gray-500 md:col-span-2">Visible to: {VISIBILITY_LABEL[review.visibility]}</div>
            </div>
          ) : <div className="text-gray-500">Not written up yet.</div>}
        </div>
      )}
    </div>
  );
}

export function ReviewList({ data, openReviewId, onSaved }) {
  const [open, setOpen] = useState(openReviewId || null);
  useEffect(() => {
    if (!openReviewId) return;
    setOpen(openReviewId);
    document.getElementById(`review-${openReviewId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [openReviewId, data]);
  if (!data.reviews.length) return <div className="text-sm text-gray-500">No reviews to show.</div>;
  return (
    <div className="space-y-3">
      {data.reviews.map((review) => (
        <ReviewCard key={review.id} review={review} open={open === review.id}
          onToggle={() => setOpen(open === review.id ? null : review.id)}
          ratingMax={data.rating_max} visibilities={data.visibilities} onSaved={onSaved} />
      ))}
    </div>
  );
}

export function FeedbackForm({ employeeId, onSaved, kinds = ["PRAISE", "FEEDBACK"] }) {
  const [kind, setKind] = useState(kinds[0]);
  const [body, setBody] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await giveFeedback(employeeId, { kind, body, anonymous });
      setBody("");
      setAnonymous(false);
      onSaved();
    } catch (err) {
      console.error("[Performance] Feedback failed:", err);
      alertDialog(`Could not send: ${err.message}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2 rounded-xl border bg-gray-50 p-3">
      <div className="flex gap-2">
        {kinds.map((value) => (
          <button key={value} type="button" onClick={() => setKind(value)}
            className={cx("rounded-lg px-3 py-1 text-sm font-semibold", kind === value ? "bg-bx-navy text-white" : "bg-white text-gray-700 border")}>
            {value === "PRAISE" ? "Praise" : "Feedback"}
          </button>
        ))}
      </div>
      <TextArea label={kind === "PRAISE" ? "What did they do well?" : "What could they do better?"} value={body} onChange={setBody} rows={3} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="inline-flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={anonymous} onChange={(e) => setAnonymous(e.target.checked)} />
          Anonymous (only HR can see it was you)
        </label>
        <Button size="sm" onClick={submit} disabled={busy || body.trim().length < 3}>Send</Button>
      </div>
    </div>
  );
}

function FeedbackItems({ items, empty }) {
  if (!items.length) return <div className="text-sm text-gray-500">{empty}</div>;
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id} className="rounded-xl border bg-white p-3 text-sm">
          <div className="text-gray-900">{item.body}</div>
          <div className="mt-1 text-xs text-gray-500">
            {item.author_name ? `${item.author_name}${item.anonymous ? " (anonymous)" : ""}` : "Anonymous"} · {when(item.created_at)}
          </div>
        </li>
      ))}
    </ul>
  );
}

function NoteForm({ employeeId, onSaved }) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await addNote(employeeId, body);
      setBody("");
      onSaved();
    } catch (err) {
      console.error("[Performance] Note failed:", err);
      alertDialog(`Could not save the note: ${err.message}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2">
      <TextArea label="Add an internal note (reporting chain and HR only)" value={body} onChange={setBody} rows={2} />
      <Button size="sm" onClick={submit} disabled={busy || body.trim().length < 3}>Add note</Button>
    </div>
  );
}

const FEEDBACK_TABS = [["praise", "Praises"], ["feedback", "Feedback"], ["notes", "Internal Notes"]];

export function FeedbackSection({ data, employeeId, onSaved, allowGive = true }) {
  const tabs = FEEDBACK_TABS.filter(([key]) => key !== "notes" || data.can_add_note || data.notes.length);
  const [tab, setTab] = useState("praise");
  const praise = data.feedback.filter((f) => f.kind === "PRAISE");
  const feedback = data.feedback.filter((f) => f.kind === "FEEDBACK");
  return (
    <div className="space-y-3">
      <div className="flex gap-1 border-b">
        {tabs.map(([key, title]) => (
          <button key={key} type="button" onClick={() => setTab(key)}
            className={cx("-mb-px border-b-2 px-3 py-1.5 text-sm font-semibold",
              tab === key ? "border-bx-orange text-gray-900" : "border-transparent text-gray-500 hover:text-gray-900")}>
            {title}
          </button>
        ))}
      </div>
      {tab === "praise" && (
        <>
          {allowGive && data.can_give_feedback ? <FeedbackForm employeeId={employeeId} onSaved={onSaved} kinds={["PRAISE", "FEEDBACK"]} /> : null}
          <FeedbackItems items={praise} empty="No praise yet." />
        </>
      )}
      {tab === "feedback" && (
        <>
          {allowGive && data.can_give_feedback ? <FeedbackForm employeeId={employeeId} onSaved={onSaved} kinds={["FEEDBACK", "PRAISE"]} /> : null}
          <FeedbackItems items={feedback} empty="No feedback you can see." />
        </>
      )}
      {tab === "notes" && (
        <>
          {data.can_add_note ? <NoteForm employeeId={employeeId} onSaved={onSaved} /> : null}
          <FeedbackItems items={data.notes.map((n) => ({ ...n, anonymous: false }))} empty="No internal notes." />
        </>
      )}
    </div>
  );
}
