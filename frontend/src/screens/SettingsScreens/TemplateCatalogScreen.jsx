// Every message the system sends, in one place (CEO 2026-11-03): occasions, candidate notices, hiring stages, Thunder's
// outreach. Pick one, edit it, click a field to insert it. Message templates keep their earlier versions.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Input, Select, TextArea } from "../../components/ui";
import { hasPermission } from "../../utils/permissionsRoleTemplate";
import { getTemplateCatalog, saveCatalogTemplate } from "../../services/api/templateCatalog";

const idOf = (t) => `${t.store}:${t.id}`;

export default function TemplateCatalogScreen() {
  const [data, setData] = useState({ templates: [], channels: [] });
  const [group, setGroup] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [form, setForm] = useState({ subject: "", body: "", channel: "" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const canEdit = hasPermission("checklists", "edit");

  const load = useCallback(() => {
    setError("");
    return getTemplateCatalog().then(setData).catch((err) => setError(`Could not load the templates: ${err.message}`));
  }, []);
  useEffect(() => { load(); }, [load]);

  const groups = useMemo(() => [...new Set(data.templates.map((t) => t.group))], [data.templates]);
  const shown = data.templates.filter((t) => !group || t.group === group);
  const selected = data.templates.find((t) => idOf(t) === selectedId);
  useEffect(() => {
    if (selected) setForm({ subject: selected.subject || "", body: selected.body || "", channel: selected.channel });
    setNotice("");
  }, [selected]);

  const insert = (field) => {
    const token = selected.syntax === "{field}" ? `{${field}}` : `{{${field}}}`;
    setForm((f) => ({ ...f, body: `${f.body}${token}` }));
  };
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const saved = await saveCatalogTemplate(selected.store, selected.id, form);
      await load();
      setSelectedId(`${selected.store}:${saved.id}`);
      setNotice("Saved. New sends use it from now on.");
    } catch (err) {
      setError(err.message || "Could not save.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card title="Templates" subtitle={`${data.templates.length} messages`}>
        <Select label="Show" value={group} onChange={setGroup}
          options={[{ value: "", label: "All" }, ...groups.map((g) => ({ value: g, label: g }))]} />
        <div className="mt-3 max-h-[560px] space-y-1 overflow-y-auto">
          {shown.map((t) => (
            <button key={idOf(t)} type="button" onClick={() => setSelectedId(idOf(t))}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm ${selectedId === idOf(t) ? "bg-gray-900 text-white" : "hover:bg-gray-100"}`}>
              <div className="font-medium">{t.name}</div>
              <div className="text-xs opacity-70">{t.group} · {t.channel}{t.version > 1 ? ` · v${t.version}` : ""}</div>
            </button>
          ))}
        </div>
      </Card>
      <Card title={selected?.name || "Pick a template"} subtitle={selected ? `${selected.group} · ${selected.key}` : "Choose one on the left to read or edit it."}>
        {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}
        {notice ? <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">{notice}</div> : null}
        {selected ? (
          <div className="grid gap-3">
            {selected.store === "message" ? (
              <Select label="Channel" value={form.channel} onChange={(v) => setForm((f) => ({ ...f, channel: v }))}
                options={data.channels.map((c) => ({ value: c, label: c }))} />
            ) : null}
            {form.channel === "EMAIL" ? (
              <Input label="Subject" value={form.subject} onChange={(v) => setForm((f) => ({ ...f, subject: v }))} />
            ) : null}
            <TextArea label="Message" rows={12} value={form.body} onChange={(v) => setForm((f) => ({ ...f, body: v }))} />
            {selected.fields.length ? (
              <div>
                <div className="mb-1 text-xs font-semibold text-gray-600">Fields this message uses (click to add)</div>
                <div className="flex flex-wrap gap-1">
                  {selected.fields.map((f) => (
                    <button key={f} type="button" onClick={() => insert(f)} className="rounded-full border bg-gray-50 px-2 py-0.5 text-xs hover:bg-gray-100">{f}</button>
                  ))}
                </div>
              </div>
            ) : null}
            {canEdit ? <div><Button variant="primary" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save"}</Button></div> : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
