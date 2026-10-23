// A task's comment thread (CEO 2026-10-22): the assignee, the creator and anyone who can see the
// task read and add to it; approval decisions post their note here as well.
import { useCallback, useEffect, useState } from "react";
import { Button } from "./ui";
import { addTaskComment, getTaskComments } from "../services/api/tasks";

export default function TaskComments({ taskId }) {
  const [comments, setComments] = useState([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setComments(await getTaskComments(taskId));
    } catch (err) {
      setError(`Could not load comments: ${err.message}`);
    }
  }, [taskId]);

  useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    setBusy(true);
    setError("");
    try {
      await addTaskComment(taskId, text.trim());
      setText("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-t border-bx-border px-5 py-4">
      <div className="mb-2 text-sm font-semibold text-gray-800">Comments</div>
      {error ? <div className="mb-2 text-xs text-red-700">{error}</div> : null}
      {comments.length === 0 ? <p className="text-sm text-gray-400">No comments yet.</p> : (
        <ul className="mb-3 space-y-2">
          {comments.map((c) => (
            <li key={c.id} className="rounded-bx border border-bx-border px-3 py-2 text-sm">
              <div className="text-xs text-gray-500">
                {c.author_name} · {c.created_at ? new Date(c.created_at).toLocaleString() : ""}
              </div>
              <div className="whitespace-pre-wrap text-gray-800">{c.body}</div>
            </li>
          ))}
        </ul>
      )}
      <textarea className="w-full rounded-bx border border-bx-border px-2 py-1 text-sm" rows={2}
        placeholder="Add a comment" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-2 flex justify-end">
        <Button variant="secondary" disabled={busy || !text.trim()} onClick={add}>{busy ? "Posting..." : "Comment"}</Button>
      </div>
    </div>
  );
}
