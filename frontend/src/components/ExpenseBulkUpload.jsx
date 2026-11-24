// Bulk receipt upload for Accounts (backend POST /expenses/from-receipt, expenses:create on the role
// template). One expense per receipt, each read and checked like any receipt; files go one per
// request (the web server limits each request) and every file gets its own result: created,
// needs review (with reasons) or failed (with the reason). A failed request is a failed file, never
// a silent skip.
import React, { useState } from "react";
import { Upload } from "lucide-react";
import { Button, Select } from "./ui";
import { createExpenseFromReceipt } from "../services/api/expenses";

const RESULT_LOOK = {
  CREATED: { label: "Created - receipt verified", tone: "bg-emerald-100 text-emerald-800" },
  NEEDS_REVIEW: { label: "Created - needs review", tone: "bg-amber-100 text-amber-800" },
  FAILED: { label: "Failed - not created", tone: "bg-rose-100 text-rose-800" },
};
const SPEND_FOR = [
  { label: "Choose who it is on", value: "" },
  { label: "Internal / personal (the employee's BU)", value: "INTERNAL" },
];

const usd = (cents) => (cents == null ? "" : `$${(cents / 100).toFixed(2)}`);

export default function ExpenseBulkUpload({ employees, categories, onUploaded }) {
  const [defaultEmployeeId, setDefaultEmployeeId] = useState("");
  const [spendFor, setSpendFor] = useState("");
  const [rows, setRows] = useState([]); // {file, employeeId, amount, date, category}
  const [uploading, setUploading] = useState("");
  const [error, setError] = useState("");
  const [results, setResults] = useState(null);

  const employeeOptions = employees.map((e) => ({ label: e.email ? `${e.name} (${e.email})` : e.name, value: e.id }));
  const nameOf = (id) => employees.find((e) => e.id === id)?.name || "—";

  const pickFiles = (fileList) => {
    setResults(null);
    setError("");
    setRows(Array.from(fileList || []).map((file) => ({ file, employeeId: "", amount: "", date: "", category: "OTHER" })));
  };

  const setRow = (index, field) => (value) =>
    setRows((current) => current.map((r, i) => (i === index ? { ...r, [field]: value } : r)));

  const upload = async () => {
    if (!rows.length) {
      setError("Choose the receipts to upload.");
      return;
    }
    if (!spendFor) {
      setError("Say who the spend is on.");
      return;
    }
    const missing = rows.filter((r) => !(r.employeeId || defaultEmployeeId)).map((r) => r.file.name);
    if (missing.length) {
      setError(`Choose who each receipt is for (missing: ${missing.join(", ")}).`);
      return;
    }
    const badAmount = rows.filter((r) => r.amount && !(parseFloat(r.amount) > 0)).map((r) => r.file.name);
    if (badAmount.length) {
      setError(`Amount must be a positive number (${badAmount.join(", ")}).`);
      return;
    }
    setError("");
    const out = [];
    for (let i = 0; i < rows.length; i += 1) {
      const r = rows[i];
      const employeeId = r.employeeId || defaultEmployeeId;
      setUploading(`Reading receipt ${i + 1} of ${rows.length}…`);
      try {
        const result = await createExpenseFromReceipt(r.file, {
          expense_for_employee_id: employeeId,
          spend_for: spendFor,
          expense_category: r.category,
          amount_usd_cents: r.amount ? Math.round(parseFloat(r.amount) * 100) : null,
          expense_date: r.date || null,
        });
        out.push({ ...result, employeeId });
      } catch (err) {
        console.error(`[ExpenseBulkUpload] ${r.file.name} failed:`, err);
        out.push({ filename: r.file.name, status: "FAILED", employeeId, reasons: [err.message] });
      }
    }
    setUploading("");
    setResults(out);
    setRows([]);
    if (onUploaded) {
      try {
        await onUploaded();
      } catch (err) {
        setError(`Uploaded, but the list could not be refreshed: ${err.message}`);
      }
    }
  };

  const count = (status) => (results || []).filter((r) => r.status === status).length;

  return (
    <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-1 text-sm font-semibold text-gray-900">Upload receipts for employees</div>
      <div className="mb-3 text-xs text-gray-500">
        One expense per receipt, logged as the employee's. Amount and date are read from the receipt unless you
        type them (then they are checked against it). A verified receipt skips the manager step; Finance still
        approves payment. Client spend: log it from the employee's expense form instead.
      </div>
      {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Select label="Expense for (default)" value={defaultEmployeeId} onChange={setDefaultEmployeeId}
          options={[{ label: "Choose employee", value: "" }, ...employeeOptions]} />
        <Select label="Who the spend is on" value={spendFor} onChange={setSpendFor} options={SPEND_FOR} />
        <label className="block">
          <div className="mb-1 text-xs font-semibold text-gray-700">Receipts (photos or PDFs)</div>
          <input type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(e) => pickFiles(e.target.files)} className="block w-full text-sm" />
        </label>
      </div>

      {rows.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-gray-500">
              <tr>
                <th className="py-1 pr-2">File</th>
                <th className="py-1 pr-2">Expense for</th>
                <th className="py-1 pr-2">Amount USD (optional)</th>
                <th className="py-1 pr-2">Date (optional)</th>
                <th className="py-1 pr-2">Category</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.file.name}-${i}`} className="border-t">
                  <td className="py-1 pr-2">{r.file.name}</td>
                  <td className="py-1 pr-2">
                    <Select value={r.employeeId} onChange={setRow(i, "employeeId")} options={[
                      { label: defaultEmployeeId ? `Default: ${nameOf(defaultEmployeeId)}` : "Choose employee", value: "" },
                      ...employeeOptions]} />
                  </td>
                  <td className="py-1 pr-2">
                    <input className="w-24 rounded-lg border px-2 py-1" value={r.amount} placeholder="from receipt"
                      onChange={(e) => setRow(i, "amount")(e.target.value)} />
                  </td>
                  <td className="py-1 pr-2">
                    <input type="date" className="rounded-lg border px-2 py-1" value={r.date}
                      onChange={(e) => setRow(i, "date")(e.target.value)} />
                  </td>
                  <td className="py-1 pr-2">
                    <Select value={r.category} onChange={setRow(i, "category")} options={categories} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 flex items-center gap-3">
        <Button onClick={upload} disabled={Boolean(uploading) || rows.length === 0}>
          <Upload className="h-4 w-4" /> {rows.length ? `Upload ${rows.length} receipt${rows.length === 1 ? "" : "s"}` : "Upload"}
        </Button>
        {uploading ? <span className="text-xs text-gray-600">{uploading}</span> : null}
      </div>

      {results && (
        <div className="mt-4 overflow-x-auto">
          <div className="mb-2 text-xs font-semibold text-gray-700">
            {count("CREATED")} created · {count("NEEDS_REVIEW")} need review · {count("FAILED")} failed
          </div>
          <table className="w-full text-left text-xs">
            <thead className="text-gray-500">
              <tr>
                <th className="py-1 pr-2">File</th>
                <th className="py-1 pr-2">Result</th>
                <th className="py-1 pr-2">For</th>
                <th className="py-1 pr-2">Amount</th>
                <th className="py-1 pr-2">Date</th>
                <th className="py-1 pr-2">Reasons</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => {
                const look = RESULT_LOOK[r.status] || RESULT_LOOK.FAILED;
                return (
                  <tr key={`${r.filename}-${i}`} className="border-t align-top">
                    <td className="py-1 pr-2">{r.filename}</td>
                    <td className="py-1 pr-2">
                      <span className={`rounded-full px-2 py-0.5 font-semibold ${look.tone}`}>{look.label}</span>
                    </td>
                    <td className="py-1 pr-2">{nameOf(r.employeeId)}</td>
                    <td className="py-1 pr-2">{usd(r.amount_usd_cents)}</td>
                    <td className="py-1 pr-2">{r.expense_date || ""}</td>
                    <td className="py-1 pr-2 text-amber-800">{(r.reasons || []).join("; ")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
