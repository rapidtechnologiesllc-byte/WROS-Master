// S-014/HRMS-0414 -- Message Template Engine management screen.
import { useEffect, useState } from "react";
import { Check, Eye, Plus } from "lucide-react";
import { Button, Card, Input, Select, TextArea } from "../components/ui";
import {
  activateTemplate,
  createTemplate,
  listTemplates,
  previewTemplate,
} from "../services/api/messageTemplates";
import { getAllCandidates } from "../services/api/candidates";

const TEMPLATE_KEYS = ["GREETING_WHATSAPP", "GREETING_EMAIL"];
const CHANNELS = ["WHATSAPP", "EMAIL", "PORTAL", "ANY"];
const VARIABLES = ["{{candidate_name}}", "{{agent_name}}", "{{company_name}}"];

export default function MessageTemplatesScreen() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [form, setForm] = useState({ templateKey: TEMPLATE_KEYS[0], templateName: "", channel: CHANNELS[0], subject: "", body: "" });
  const [creating, setCreating] = useState(false);

  const [candidates, setCandidates] = useState([]);
  const [previewCandidateId, setPreviewCandidateId] = useState("");
  const [previewTemplateId, setPreviewTemplateId] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [previewing, setPreviewing] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listTemplates();
      setTemplates(res?.templates || []);
    } catch (err) {
      setError(err.message || "Failed to load templates.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    getAllCandidates()
      .then((res) => setCandidates(res?.candidates || []))
      .catch(() => setCandidates([]));
  }, []);

  const insertVariable = (variable) => {
    setForm((f) => ({ ...f, body: `${f.body}${variable}` }));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.templateName.trim() || !form.body.trim()) return;
    if (form.channel === "EMAIL" && !form.subject.trim()) {
      setError("Subject is required for EMAIL channel templates.");
      return;
    }
    setCreating(true);
    setError("");
    try {
      await createTemplate(form);
      setForm({ templateKey: TEMPLATE_KEYS[0], templateName: "", channel: CHANNELS[0], subject: "", body: "" });
      await load();
    } catch (err) {
      setError(err.message || "Failed to create template.");
    } finally {
      setCreating(false);
    }
  };

  const handleActivate = async (templateId) => {
    if (!window.confirm("Activate this version? The current active version will be deactivated.")) return;
    setError("");
    try {
      await activateTemplate(templateId);
      await load();
    } catch (err) {
      setError(err.message || "Failed to activate template.");
    }
  };

  const handlePreview = async (templateId) => {
    if (!previewCandidateId) {
      setError("Select a candidate to preview with first.");
      return;
    }
    setPreviewing(true);
    setPreviewTemplateId(templateId);
    setError("");
    try {
      const res = await previewTemplate(templateId, previewCandidateId);
      setPreviewResult(res);
    } catch (err) {
      setError(err.message || "Failed to preview template.");
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="grid gap-4">
      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      ) : null}

      <Card title="Create Template Version" icon={<Plus className="h-4 w-4" />}>
        <form onSubmit={handleCreate} className="grid gap-3 md:grid-cols-2">
          <Select
            label="Template Key"
            value={form.templateKey}
            onChange={(v) => setForm((f) => ({ ...f, templateKey: v }))}
            options={TEMPLATE_KEYS.map((k) => ({ value: k, label: k }))}
          />
          <Select
            label="Channel"
            value={form.channel}
            onChange={(v) => setForm((f) => ({ ...f, channel: v }))}
            options={CHANNELS.map((c) => ({ value: c, label: c }))}
          />
          <div className="md:col-span-2">
            <Input label="Template Name" value={form.templateName} onChange={(v) => setForm((f) => ({ ...f, templateName: v }))} placeholder="e.g. WhatsApp Greeting — Standard" />
          </div>
          {form.channel === "EMAIL" ? (
            <div className="md:col-span-2">
              <Input label="Subject" value={form.subject} onChange={(v) => setForm((f) => ({ ...f, subject: v }))} placeholder="Hi {{candidate_name}} — Thunder from BlitzenX wants to connect" />
            </div>
          ) : null}
          <div className="md:col-span-2">
            <TextArea label="Body" value={form.body} onChange={(v) => setForm((f) => ({ ...f, body: v }))} placeholder="Type your message..." rows={5} />
            <div className="mt-1 text-xs text-gray-500">{form.body.length} characters</div>
          </div>
          <div className="md:col-span-2 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-gray-500">Insert variable:</span>
            {VARIABLES.map((v) => (
              <button key={v} type="button" onClick={() => insertVariable(v)} className="rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs font-mono hover:bg-gray-100">
                {v}
              </button>
            ))}
          </div>
          <div className="md:col-span-2">
            <Button type="submit" disabled={creating}>{creating ? "Creating…" : "Create Draft Version"}</Button>
          </div>
        </form>
      </Card>

      <Card title="Preview With Real Candidate">
        <div className="flex items-end gap-3">
          <div className="w-72">
            <Select
              label="Test Candidate"
              value={previewCandidateId}
              onChange={setPreviewCandidateId}
              options={[{ value: "", label: "Select a candidate…" }, ...candidates.map((c) => ({ value: c.candidate_id, label: c.candidate_name || c.candidate_email }))]}
            />
          </div>
        </div>
        {previewResult ? (
          <div className="mt-3 rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm">
            {previewResult.rendered_subject ? <div className="mb-1 font-semibold">Subject: {previewResult.rendered_subject}</div> : null}
            <div className="whitespace-pre-wrap">{previewResult.rendered_body}</div>
          </div>
        ) : null}
      </Card>

      <Card title="Templates" subtitle="All versions, newest first per key/channel">
        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : templates.length === 0 ? (
          <div className="py-8 text-center text-sm text-gray-500">No templates yet. Create one above.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold uppercase text-gray-500">
                  <th className="py-2 pr-3">Name</th>
                  <th className="py-2 pr-3">Key</th>
                  <th className="py-2 pr-3">Channel</th>
                  <th className="py-2 pr-3">Version</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((t) => (
                  <tr key={t.id} className="border-b last:border-b-0">
                    <td className="py-2 pr-3">{t.template_name}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{t.template_key}</td>
                    <td className="py-2 pr-3">{t.channel}</td>
                    <td className="py-2 pr-3">v{t.version}</td>
                    <td className="py-2 pr-3">
                      {t.is_active ? (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">ACTIVE</span>
                      ) : (
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">DRAFT</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      <div className="flex gap-2">
                        <Button variant="secondary" onClick={() => handlePreview(t.id)} disabled={previewing && previewTemplateId === t.id}>
                          <Eye className="h-3.5 w-3.5" /> Preview
                        </Button>
                        {!t.is_active ? (
                          <Button variant="success" onClick={() => handleActivate(t.id)}>
                            <Check className="h-3.5 w-3.5" /> Activate
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
