// Candidate stage email templates: one subject + HTML body per pipeline stage. The stages and the
// placeholders come from the server (GET /email-templates); editing needs checklists.edit.
import React, { useCallback, useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { Button, Card, Input, TextArea } from "../../components/ui";
import { alertDialog } from "../../utils/dialogs";
import cx from "../../utils/cx";
import { hasPermission } from "../../utils/permissionsRoleTemplate";
import {
  listStageEmailTemplates,
  previewStageEmailTemplate,
  saveStageEmailTemplate,
} from "../../services/api/emailTemplates";

export default function EmailTemplatesScreen() {
  const [stages, setStages] = useState([]);
  const [placeholders, setPlaceholders] = useState([]);
  const [templates, setTemplates] = useState({});
  const [selectedStage, setSelectedStage] = useState("");
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [previewData, setPreviewData] = useState(null);
  const [sampleName, setSampleName] = useState("Candidate");
  const [sampleJob, setSampleJob] = useState("Position");
  const canEdit = hasPermission("checklists", "edit");

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const data = await listStageEmailTemplates();
      setStages(data.stages);
      setPlaceholders(data.placeholders);
      setTemplates(Object.fromEntries(data.templates.map((t) => [t.stage, t])));
      setSelectedStage((current) => current || data.stages[0]?.key || "");
    } catch (error) {
      console.error("[EmailTemplates] Failed to load templates:", error);
      setLoadError(error.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const template = templates[selectedStage];
  useEffect(() => {
    setSubject(template?.subject || "");
    setBodyHtml(template?.body_html || "");
    setEditing(false);
  }, [selectedStage, template]);

  const stageLabel = stages.find((s) => s.key === selectedStage)?.label || selectedStage;

  const handleSave = async () => {
    setSaving(true);
    try {
      const saved = await saveStageEmailTemplate(selectedStage, { subject, body_html: bodyHtml });
      setTemplates((prev) => ({ ...prev, [saved.stage]: saved }));
      alertDialog("Template saved.");
    } catch (error) {
      console.error("[EmailTemplates] Failed to save template:", error);
      alertDialog(`Failed to save template: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    try {
      setPreviewData(await previewStageEmailTemplate(selectedStage, { candidateName: sampleName, jobTitle: sampleJob }));
    } catch (error) {
      console.error("[EmailTemplates] Failed to preview template:", error);
      alertDialog(`Failed to preview template: ${error.message}`);
    }
  };

  if (loadError) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Could not load email templates: {loadError}{" "}
        <button className="font-semibold underline" onClick={load}>Retry</button>
      </div>
    );
  }

  const placeholderHint = `Placeholders: ${placeholders.join(", ")}`;

  return (
    <div className="grid gap-4 md:grid-cols-[200px_1fr]">
      <div className="flex flex-row flex-wrap gap-1 md:flex-col" role="tablist" aria-label="Stages">
        {stages.map((s) => (
          <button
            key={s.key}
            role="tab"
            aria-selected={s.key === selectedStage}
            onClick={() => setSelectedStage(s.key)}
            className={cx(
              "flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-semibold transition",
              s.key === selectedStage
                ? "bg-bx-navy text-white dark:bg-gray-700"
                : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800",
            )}
          >
            {s.label}
            {!templates[s.key] && <span className="text-xs font-normal opacity-70">not set</span>}
          </button>
        ))}
      </div>

      <Card title={`${stageLabel} email`} subtitle="The email a candidate receives at this pipeline stage." icon={<Mail size={16} />}>
        {editing ? (
          <div className="space-y-4">
            <Input label="Subject line" value={subject} onChange={setSubject} />
            <TextArea label="Email body (HTML)" value={bodyHtml} onChange={setBodyHtml} rows={12} />
            <p className="text-xs text-gray-500">{placeholderHint}</p>
            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save template"}</Button>
              <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {template ? (
              <>
                <div>
                  <div className="mb-1 text-xs font-semibold text-gray-700">Subject line</div>
                  <div className="text-sm text-gray-900">{subject}</div>
                </div>
                <div>
                  <div className="mb-1 text-xs font-semibold text-gray-700">Email body</div>
                  <div className="rounded-lg border bg-gray-50 p-4 text-sm text-gray-900" dangerouslySetInnerHTML={{ __html: bodyHtml }} />
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-600">No template saved for this stage yet.</p>
            )}
            {canEdit && (
              <Button onClick={() => setEditing(true)}>{template ? "Edit template" : "Create template"}</Button>
            )}
            {template && (
              <div className="flex flex-wrap items-end gap-2 border-t pt-4">
                <Input label="Preview with candidate name" value={sampleName} onChange={setSampleName} />
                <Input label="and job title" value={sampleJob} onChange={setSampleJob} />
                <Button variant="secondary" onClick={handlePreview}>Preview</Button>
              </div>
            )}
          </div>
        )}
      </Card>

      {previewData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setPreviewData(null)}>
          <div
            role="dialog"
            aria-label="Email preview"
            className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Email preview</h2>
              <Button variant="ghost" onClick={() => setPreviewData(null)}>Close</Button>
            </div>
            <div className="mb-3 text-sm text-gray-900"><strong>Subject:</strong> {previewData.subject}</div>
            <div className="rounded-lg border p-4 text-sm text-gray-900" dangerouslySetInnerHTML={{ __html: previewData.body_html }} />
          </div>
        </div>
      )}
    </div>
  );
}
