// Newsletter management (create, list, schedule, send).
import { useEffect, useState } from "react";
import { Mail, Plus } from "lucide-react";
import { Button, Card, Input, Select, Table, StatusBadge } from "../components/ui";
import {
  createNewsletter,
  getNewsletters,
  getSubscribers,
  scheduleNewsletter,
  sendNewsletterNow,
  deleteNewsletter,
  subscribeNewsletter,
  unsubscribeNewsletter
} from "../services/api/newsletters";

export default function NewsletterScreen() {
  const [newsletters, setNewsletters] = useState([]);
  const [subscribers, setSubscribers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    subject: "",
    content: ""
  });
  const [subscribeEmail, setSubscribeEmail] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [nlRes, subRes] = await Promise.all([
        getNewsletters(),
        getSubscribers()
      ]);
      setNewsletters(Array.isArray(nlRes) ? nlRes : []);
      setSubscribers(Array.isArray(subRes) ? subRes : []);
    } catch (err) {
      setError(err.message || "Failed to load.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    if (!createForm.subject?.trim() || !createForm.content?.trim()) {
      setError("Subject and content required.");
      return;
    }
    setError("");
    try {
      await createNewsletter(createForm);
      setCreateForm({ subject: "", content: "" });
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(err.message || "Failed to create newsletter.");
    }
  };

  const handleSubscribe = async () => {
    if (!subscribeEmail?.trim()) return;
    setError("");
    try {
      await subscribeNewsletter({ email: subscribeEmail.trim() });
      setSubscribeEmail("");
      await load();
    } catch (err) {
      setError(err.message || "Failed to subscribe.");
    }
  };

  const handleSend = async (id) => {
    setError("");
    try {
      await sendNewsletterNow(id);
      await load();
    } catch (err) {
      setError(err.message || "Failed to send.");
    }
  };

  const handleSchedule = async (id) => {
    const date = prompt("Schedule for (YYYY-MM-DDTHH:mm:ss):");
    if (!date) return;
    setError("");
    try {
      await scheduleNewsletter(id, date);
      await load();
    } catch (err) {
      setError(err.message || "Failed to schedule.");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this newsletter?")) return;
    setError("");
    try {
      await deleteNewsletter(id);
      await load();
    } catch (err) {
      setError(err.message || "Failed to delete.");
    }
  };

  if (loading) {
    return (
      <Card title="Newsletters">
        <div className="py-4 text-center text-sm text-gray-500">Loading…</div>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      <Card
        title="Newsletters"
        icon={<Mail className="h-4 w-4" />}
        right={
          <Button onClick={() => setShowCreate(!showCreate)}>
            <Plus className="h-4 w-4" /> Create
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {showCreate ? (
          <div className="mb-4 rounded-xl border bg-gray-50 p-4">
            <Input
              label="Subject"
              value={createForm.subject}
              onChange={(v) =>
                setCreateForm((f) => ({ ...f, subject: v }))
              }
            />
            <div className="mt-2">
              <label className="mb-1 block text-xs font-semibold text-gray-700">
                Content
              </label>
              <textarea
                value={createForm.content}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, content: e.target.value }))
                }
                rows={4}
                className="w-full rounded-xl border px-3 py-2 text-sm"
              />
            </div>
            <div className="mt-2 flex gap-2">
              <Button onClick={handleCreate}>Create Draft</Button>
              <Button variant="secondary" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : null}

        <div className="mb-4 flex gap-2">
          <input
            type="email"
            placeholder="Subscribe email"
            value={subscribeEmail}
            onChange={(e) => setSubscribeEmail(e.target.value)}
            className="rounded-xl border px-3 py-2 text-sm"
          />
          <Button variant="secondary" onClick={handleSubscribe}>
            Add Subscriber
          </Button>
        </div>

        {newsletters.length ? (
          <Table
            columns={[
              { key: "subject", header: "Subject" },
              { key: "status", header: "Status" },
              { key: "created_at", header: "Created" },
              { key: "actions", header: "Actions" }
            ]}
            rows={newsletters.map((n) => ({
              subject: n.subject,
              status: <StatusBadge status={n.status} />,
              created_at: n.created_at
                ? new Date(n.created_at).toLocaleDateString()
                : "-",
              actions: (
                <div className="flex gap-1">
                  {n.status === "draft" ? (
                    <>
                      <Button
                        variant="secondary"
                        onClick={() => handleSchedule(n.id)}
                      >
                        Schedule
                      </Button>
                      <Button onClick={() => handleSend(n.id)}>Send Now</Button>
                    </>
                  ) : null}
                  <Button
                    variant="danger"
                    onClick={() => handleDelete(n.id)}
                  >
                    Delete
                  </Button>
                </div>
              )
            }))}
          />
        ) : (
          <div className="rounded-2xl border bg-gray-50 p-4 text-sm text-gray-600">
            No newsletters yet.
          </div>
        )}
      </Card>

      <Card title="Subscribers">
        {subscribers.length ? (
          <div className="space-y-1 text-sm">
            {subscribers.slice(0, 20).map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-2">
                <span>{s.email}</span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={s.is_active ? "Active" : "Inactive"} />
                  {s.is_active && (
                    <Button
                      variant="secondary"
                      onClick={async () => {
                        setError("");
                        try {
                          await unsubscribeNewsletter(s.email);
                          await load();
                        } catch (err) {
                          setError(err.message || "Failed to unsubscribe.");
                        }
                      }}
                    >
                      Unsubscribe
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {subscribers.length > 20 ? (
              <div className="text-xs text-gray-500">
                +{subscribers.length - 20} more
              </div>
            ) : null}
          </div>
        ) : (
          <div className="text-sm text-gray-600">No subscribers.</div>
        )}
      </Card>
    </div>
  );
}
