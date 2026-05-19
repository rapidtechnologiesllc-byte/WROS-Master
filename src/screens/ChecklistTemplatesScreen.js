// HR: manage checklist templates and template items (backend /checklist/hr/templates).
import { useCallback, useEffect, useState } from "react";
import { ListChecks, Plus, Trash2 } from "lucide-react";
import { Button, Card, Input, Select } from "../components/ui";
import {
  addChecklistTemplateItem,
  assignChecklistToCandidate,
  createChecklistTemplate,
  deleteChecklistTemplate,
  deleteChecklistTemplateItem,
  getChecklistTemplate,
  listChecklistTemplates,
  updateChecklistTemplate,
  updateChecklistTemplateItem,
} from "../services/api/checklists";
import { getAllCandidates } from "../services/api/candidates";
import { AssignButton, ContentDiv } from "../styles/ChecklistTemplate";
import { toast } from "react-toastify";
import { sendPlainEmail } from "../services/api/email";
import { getEmailBodyHTML } from "../utils/preboardingEmailTemplate";

const emptyItemForm = () => ({
  title: "",
  description: "",
  item_type: "todo",
  order_index: 0,
  due_days_offset: "",
});

export default function ChecklistTemplatesScreen() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [summaries, setSummaries] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [itemForm, setItemForm] = useState(emptyItemForm);
  const [savingItem, setSavingItem] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [candidateList, setCandidateList] = useState();
  const [selectedCandidate, setSelectedCandidate] = useState();
  const [selectedTemplate, setSelectedTemplate] = useState();

  useEffect(() => {
    const fetchCandidates = async () => {
      const result = await getAllCandidates();
      setCandidateList(result?.candidates);
    };
    fetchCandidates();
  }, []);

  const candidateOptions = [
    { label: "Please select Candidate", value: "", disabled: true },
    ...(candidateList?.map((can) => ({
      label: can?.candidate_name,
      value: can?.candidate_id,
      email: can?.candidate_email,
      candidate: can,
    })) || []),
  ];

  const selectedCandidateData = candidateList?.find(
    (can) => String(can.candidate_id) === String(selectedCandidate),
  );

  const templateOptions = [
    { label: "Please select Template", value: "", disabled: true },
    ...(summaries?.map((sum) => ({
      label: sum?.name,
      value: sum?.id,
    })) || []),
  ];

  const loadList = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res = await listChecklistTemplates();
      setSummaries(res?.templates || []);
    } catch (err) {
      setError(err.message || "Failed to load templates.");
      setSummaries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const loadDetail = async (templateId) => {
    setDetailLoading(true);
    setError("");
    try {
      const d = await getChecklistTemplate(templateId);
      setDetail(d);
      setEditName(d?.name || "");
      setEditDescription(d?.description || "");
    } catch (err) {
      setError(err.message || "Failed to load template.");
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleExpand = async (id) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    await loadDetail(id);
  };

  const handleCreate = async () => {
    if (!newName.trim()) {
      setError("Template name is required.");
      return;
    }
    setCreateBusy(true);
    setError("");
    try {
      await createChecklistTemplate({
        name: newName.trim(),
        description: newDescription.trim() || null,
        items: [],
      });
      setNotice("Template created.");
      setCreateOpen(false);
      setNewName("");
      setNewDescription("");
      await loadList();
    } catch (err) {
      setError(err.message || "Failed to create template.");
    } finally {
      setCreateBusy(false);
    }
  };

  const handleSaveMeta = async () => {
    if (!detail?.id) return;
    setError("");
    try {
      await updateChecklistTemplate(detail.id, {
        name: editName.trim() || detail.name,
        description: editDescription,
      });
      setNotice("Template updated.");
      await loadDetail(detail.id);
      await loadList();
    } catch (err) {
      setError(err.message || "Failed to update template.");
    }
  };

  const handleDeleteTemplate = async (templateId) => {
    if (!window.confirm("Delete this template and all its items?")) return;
    setError("");
    try {
      await deleteChecklistTemplate(templateId);
      setNotice("Template deleted.");
      setExpandedId(null);
      setDetail(null);
      await loadList();
    } catch (err) {
      setError(err.message || "Failed to delete template.");
    }
  };

  const handleAddItem = async () => {
    if (!detail?.id) return;
    if (!itemForm.title.trim()) {
      setError("Item title is required.");
      return;
    }
    setSavingItem(true);
    setError("");
    try {
      const payload = {
        title: itemForm.title.trim(),
        description: itemForm.description.trim() || null,
        item_type: itemForm.item_type,
        order_index: Number(itemForm.order_index) || 0,
        due_days_offset:
          itemForm.due_days_offset === "" || itemForm.due_days_offset == null
            ? null
            : Number(itemForm.due_days_offset),
      };
      await addChecklistTemplateItem(detail.id, payload);
      setNotice("Item added.");
      setItemForm(emptyItemForm());
      await loadDetail(detail.id);
      await loadList();
    } catch (err) {
      setError(err.message || "Failed to add item.");
    } finally {
      setSavingItem(false);
    }
  };

  const handleDeleteItem = async (itemId) => {
    if (!detail?.id) return;
    if (!window.confirm("Delete this template item?")) return;
    setError("");
    try {
      await deleteChecklistTemplateItem(detail.id, itemId);
      setNotice("Item deleted.");
      await loadDetail(detail.id);
      await loadList();
    } catch (err) {
      setError(err.message || "Failed to delete item.");
    }
  };

  const handleQuickUpdateItem = async (itemId, patch) => {
    if (!detail?.id) return;
    setError("");
    try {
      await updateChecklistTemplateItem(detail.id, itemId, patch);
      setNotice("Item updated.");
      await loadDetail(detail.id);
    } catch (err) {
      setError(err.message || "Failed to update item.");
    }
  };

  const handleAssignTask = async () => {
    if (!selectedTemplate) return;

    try {
      const payload = {
        candidateId: selectedCandidate,
        templateId: parseInt(selectedTemplate),
      };
      const [emailRes, checklistRes] = await Promise.all([
        sendPlainEmail({
          toEmail: selectedCandidateData?.candidate_email,
          subject: "Pre-Onboarding Task",
          bodyContent: getEmailBodyHTML(selectedCandidateData?.candidate_name),
          isHtml: true,
        }),
        assignChecklistToCandidate(payload),
      ]);
      if (checklistRes?.response?.status === 200) {
        toast.success("Template assigned successfully");
      }
    } catch (err) {
      toast.error(err?.message || "Something went wrong");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Checklist templates"
        icon={<ListChecks className="h-4 w-4" />}
      >
        <p className="mb-4 text-sm text-gray-600">
          Create reusable templates for pre-onboarding. Assign them to
          candidates from the Pre-Onboarding screen.
        </p>

        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {notice}
          </div>
        ) : null}
        {/* Need this code for Future use */}
        {/* <div className="mt-3 grid gap-3 md:grid-cols-4"> */}
        {/* <Button variant="secondary" onClick={() => setCreateOpen((v) => !v)}>
            <Plus className="h-4 w-4" /> New template
          </Button>
          <Button variant="ghost" onClick={loadList} disabled={loading}>
            Refresh
          </Button> */}
        <ContentDiv>
          <Select
            label="Select Candidate"
            options={candidateOptions}
            onChange={setSelectedCandidate}
            value={selectedCandidate}
          />
          <Select
            label="Select Template"
            options={templateOptions}
            onChange={setSelectedTemplate}
            value={selectedTemplate}
          />
          <AssignButton onClick={() => handleAssignTask()}>
            <Plus className="h-4 w-4" /> Assign Task
          </AssignButton>
        </ContentDiv>
        {/* </div> */}

        {createOpen ? (
          <div className="mb-6 rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">
              Create template
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Input label="Name *" value={newName} onChange={setNewName} />
              <Input
                label="Description"
                value={newDescription}
                onChange={setNewDescription}
              />
            </div>
            <div className="mt-3 flex gap-2">
              <Button onClick={handleCreate} disabled={createBusy}>
                {createBusy ? "Creating…" : "Create"}
              </Button>
              <Button variant="secondary" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : null}

        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">
            Loading templates…
          </div>
        ) : !summaries.length ? (
          <div className="rounded-xl border border-dashed p-6 text-center text-sm text-gray-600">
            No templates yet. Create one to use with Pre-Onboarding.
          </div>
        ) : (
          <div className="space-y-2">
            {summaries.map((t) => (
              <div key={t.id} className="rounded-2xl border bg-white">
                <div className="flex flex-wrap items-center justify-between gap-2 p-4">
                  <div>
                    <div className="font-semibold">{t.name}</div>
                    <div className="text-xs text-gray-500">
                      {t.item_count ?? 0} items · ID {t.id}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => handleExpand(t.id)}
                    >
                      {expandedId === t.id ? "Collapse" : "Manage"}
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => handleDeleteTemplate(t.id)}
                    >
                      <Trash2 className="h-4 w-4" /> Delete
                    </Button>
                  </div>
                </div>

                {expandedId === t.id ? (
                  <div className="border-t bg-gray-50 p-4">
                    {detailLoading ? (
                      <div className="text-sm text-gray-500">Loading…</div>
                    ) : detail ? (
                      <>
                        <div className="mb-4 grid gap-3 md:grid-cols-2">
                          <Input
                            label="Name"
                            value={editName}
                            onChange={setEditName}
                          />
                          <Input
                            label="Description"
                            value={editDescription}
                            onChange={setEditDescription}
                          />
                        </div>
                        <Button variant="secondary" onClick={handleSaveMeta}>
                          Save name / description
                        </Button>

                        <div className="mt-6 text-xs font-semibold text-gray-700">
                          Template items
                        </div>
                        <div className="mt-2 space-y-2">
                          {(detail.items || [])
                            .slice()
                            .sort(
                              (a, b) =>
                                (a.order_index ?? 0) - (b.order_index ?? 0),
                            )
                            .map((it) => (
                              <div
                                key={it.id}
                                className="flex flex-col gap-2 rounded-xl border bg-white p-3 md:flex-row md:items-center md:justify-between"
                              >
                                <div>
                                  <div className="text-sm font-medium">
                                    {it.title}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    {it.item_type} · order {it.order_index}
                                    {it.due_days_offset != null
                                      ? ` · due +${it.due_days_offset}d`
                                      : ""}
                                  </div>
                                </div>
                                <div className="flex flex-wrap items-end gap-2">
                                  <Select
                                    label="Type"
                                    value={it.item_type}
                                    onChange={(v) =>
                                      handleQuickUpdateItem(it.id, {
                                        item_type: v,
                                      })
                                    }
                                    options={["todo", "queue"]}
                                  />
                                  <Button
                                    variant="danger"
                                    onClick={() => handleDeleteItem(it.id)}
                                  >
                                    Remove
                                  </Button>
                                </div>
                              </div>
                            ))}
                        </div>

                        <div className="mt-4 rounded-xl border bg-white p-3">
                          <div className="text-xs font-semibold text-gray-700">
                            Add item
                          </div>
                          <div className="mt-2 grid gap-3 md:grid-cols-2">
                            <Input
                              label="Title *"
                              value={itemForm.title}
                              onChange={(v) =>
                                setItemForm((f) => ({ ...f, title: v }))
                              }
                            />
                            <Input
                              label="Description"
                              value={itemForm.description}
                              onChange={(v) =>
                                setItemForm((f) => ({ ...f, description: v }))
                              }
                            />
                            <Select
                              label="Type"
                              value={itemForm.item_type}
                              onChange={(v) =>
                                setItemForm((f) => ({ ...f, item_type: v }))
                              }
                              options={["todo", "queue"]}
                            />
                            <Input
                              label="Order index"
                              value={String(itemForm.order_index)}
                              onChange={(v) =>
                                setItemForm((f) => ({
                                  ...f,
                                  order_index: Number(v) || 0,
                                }))
                              }
                            />
                            <Input
                              label="Due days offset (optional)"
                              value={
                                itemForm.due_days_offset === ""
                                  ? ""
                                  : String(itemForm.due_days_offset)
                              }
                              onChange={(v) =>
                                setItemForm((f) => ({
                                  ...f,
                                  due_days_offset: v === "" ? "" : Number(v),
                                }))
                              }
                            />
                          </div>
                          <div className="mt-3">
                            <Button
                              onClick={handleAddItem}
                              disabled={savingItem}
                            >
                              {savingItem ? "Adding…" : "Add item"}
                            </Button>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="text-sm text-gray-500">
                        Could not load template.
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
