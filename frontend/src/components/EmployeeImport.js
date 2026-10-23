// Employee import (CEO 2026-10-22): upload a CSV -> dry-run preview (nothing written) -> apply
// exactly the previewed file -> per-row results. The Add employee form is the same path with one
// row (POST /employees). Columns and the employment types each country accepts come from the
// server (GET /employees/import/template), never from this file.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Upload, Download, X, UserPlus } from "lucide-react";
import { Button, Card } from "./ui";
import cx from "../utils/cx";
import {
  applyEmployeeImport, createEmployee, dryRunEmployeeImport, getEmployeeImportTemplate,
} from "../services/api/employees";

const STATUS_STYLES = {
  applied: "bg-emerald-50 text-emerald-800",
  unchanged: "bg-gray-50 text-gray-700",
  skipped: "bg-amber-50 text-amber-800",
  failed: "bg-rose-50 text-rose-800",
};

function Modal({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className={cx("max-h-[90vh] w-full overflow-y-auto", wide ? "max-w-6xl" : "max-w-2xl")}>
        <Card title={title} right={<Button variant="ghost" onClick={onClose}><X className="h-4 w-4" /></Button>}>
          {children}
        </Card>
      </div>
    </div>
  );
}

function downloadTemplate(csv) {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "employee-import-template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function ImportEmployeesModal({ onClose, onImported }) {
  const [template, setTemplate] = useState(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getEmployeeImportTemplate().then(setTemplate).catch((err) => setError(`Could not load the template: ${err.message}`));
  }, []);

  const runDryRun = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    setPreview(null);
    setResults(null);
    try {
      setPreview(await dryRunEmployeeImport(file));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runApply = async () => {
    setBusy(true);
    setError("");
    try {
      setResults(await applyEmployeeImport(preview.token, file));
      onImported();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const ready = preview ? preview.counts.total - preview.counts.error : 0;
  const toApply = preview ? preview.counts.create + preview.counts["link-existing-user"] + preview.counts.update : 0;

  return (
    <Modal title="Import employees" onClose={onClose} wide>
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Upload a CSV of current employees. The dry run shows what each row would do and changes nothing; Apply
          then creates each login, employee record, bench or allocation and sends one activation email per new login.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" disabled={!template} onClick={() => downloadTemplate(template.csv)}>
            <Download className="h-4 w-4" /> Download template
          </Button>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => { setFile(e.target.files[0] || null); setPreview(null); setResults(null); }}
            className="text-sm"
          />
          <Button variant="primary" disabled={!file || busy} onClick={runDryRun}>
            <Upload className="h-4 w-4" /> {busy && !preview ? "Checking…" : "Dry run"}
          </Button>
        </div>
        {template ? (
          <details className="text-xs text-gray-600">
            <summary className="cursor-pointer font-semibold">Columns</summary>
            <ul className="mt-2 grid gap-1 sm:grid-cols-2">
              {template.columns.map((c) => (
                <li key={c.name}><span className="font-mono">{c.name}</span>{c.required ? " (required)" : ""}: {c.description}</li>
              ))}
            </ul>
          </details>
        ) : null}
        {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

        {preview && !results ? (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-3 text-sm">
              <span>{preview.counts.total} rows</span>
              <span className="text-emerald-700">{preview.counts.create} new</span>
              <span className="text-blue-700">{preview.counts["link-existing-user"]} link existing login</span>
              <span className="text-indigo-700">{preview.counts.update} update</span>
              <span className="text-gray-600">{preview.counts.unchanged} unchanged</span>
              <span className="text-rose-700">{preview.counts.error} with errors (skipped)</span>
            </div>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    {["Row", "Employee", "Action", "Business unit / center", "Manager", "Billable", "After import", "Problems / changes"].map((h) => (
                      <th key={h} className="px-3 py-2 font-semibold">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {preview.rows.map((r) => (
                    <tr key={r.row} className={r.errors.length ? "bg-rose-50" : ""}>
                      <td className="px-3 py-2">{r.row}</td>
                      <td className="px-3 py-2"><div className="font-semibold">{r.name}</div>{r.email}</td>
                      <td className="px-3 py-2">{r.action}<div className="text-gray-500">{r.login}</div></td>
                      <td className="px-3 py-2">{r.business_unit || "—"}<div className="text-gray-500">{r.delivery_center || "—"} {r.country || ""}</div></td>
                      <td className="px-3 py-2">{r.manager || "—"}</td>
                      <td className="px-3 py-2">{r.billable ? "yes" : "no"}</td>
                      <td className="px-3 py-2">
                        {r.status_after}
                        {r.allocation ? <div className="text-gray-500">{r.allocation.job_title} {r.allocation.pct}%</div> : null}
                      </td>
                      <td className="px-3 py-2">
                        {r.errors.length
                          ? <ul className="text-rose-700">{r.errors.map((e) => <li key={e}>{e}</li>)}</ul>
                          : <ul className="text-gray-600">{(r.changes || []).map((c) => <li key={c}>{c}</li>)}</ul>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Button variant="primary" disabled={busy || toApply === 0} onClick={runApply}>
              {busy ? "Applying…" : `Apply ${toApply} row${toApply === 1 ? "" : "s"}`}
            </Button>
            {ready !== toApply ? <span className="ml-2 text-xs text-gray-500">Unchanged rows are left as they are.</span> : null}
          </div>
        ) : null}

        {results ? (
          <div className="space-y-2">
            <div className="text-sm font-semibold">
              {Object.entries(results.counts).map(([k, v]) => `${v} ${k}`).join(" · ")}
            </div>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50">
                  <tr>{["Row", "Employee", "Result", "Activation email", "Details"].map((h) => <th key={h} className="px-3 py-2">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y">
                  {results.rows.map((r) => (
                    <tr key={r.row}>
                      <td className="px-3 py-2">{r.row}</td>
                      <td className="px-3 py-2">
                        {r.employee_id
                          ? <Link className="font-semibold text-blue-700 hover:underline" to={`/employees?employee=${encodeURIComponent(r.employee_id)}`}>{r.name}</Link>
                          : <span className="font-semibold">{r.name}</span>}
                        <div>{r.email}</div>
                      </td>
                      <td className="px-3 py-2"><span className={cx("rounded px-2 py-0.5", STATUS_STYLES[r.status])}>{r.status}</span></td>
                      <td className="px-3 py-2">{r.activation_email_queued ? "queued" : "—"}</td>
                      <td className="px-3 py-2 text-rose-700">{(r.errors || []).join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}

const EMPTY_FORM = {
  first_name: "", last_name: "", email: "", joining_date: "", business_unit_id: "", company_id: "", country: "",
  current_title: "", reporting_manager_id: "", employment_type: "", billable: "", existing_staff: true,
  monthly_salary_usd: "", bill_rate_usd: "",
};

export function AddEmployeeModal({ orgOptions, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [template, setTemplate] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getEmployeeImportTemplate().then(setTemplate).catch((err) => setError(`Could not load the form options: ${err.message}`));
  }, []);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const country = (template?.countries || []).find((c) => c.code === form.country);
  const employmentTypes = country ? country.employment_types
    : ((template?.countries || [])[0]?.employment_types || []);
  // The manager is recorded in the org chart: the new seat goes under the manager's seat, which the
  // org rules allow one or two levels above the designation's level (same rule as the backend).
  const roleLevel = (template?.org_roles || []).find((r) => r.name === form.current_title)?.level;
  const managers = (template?.managers || []).filter((m) => !roleLevel || (m.level > roleLevel && m.level <= roleLevel + 2));

  const submit = async () => {
    if (!form.first_name || !form.last_name || !form.email || !form.joining_date || !form.business_unit_id
      || form.billable === "" || form.monthly_salary_usd === "") {
      setError("Name, email, joining date, business unit, billable and monthly salary are required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await createEmployee({
        first_name: form.first_name, last_name: form.last_name, email: form.email, joining_date: form.joining_date,
        business_unit_id: Number(form.business_unit_id), company_id: form.company_id || null,
        country: form.country || null, current_title: form.current_title || null,
        reporting_manager_id: form.reporting_manager_id || null, employment_type: form.employment_type || null,
        billable: form.billable === "yes", existing_staff: form.existing_staff,
        base_salary_usd_cents: Math.round(Number(form.monthly_salary_usd) * 100),
        billing_rate_usd_cents: form.bill_rate_usd ? Math.round(Number(form.bill_rate_usd) * 100) : null,
      });
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full rounded-lg border px-3 py-2 text-sm";
  const label = "mb-1 block text-xs font-semibold text-gray-700";
  return (
    <Modal title="Add employee" onClose={onClose}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label><span className={label}>First name *</span><input className={field} value={form.first_name} onChange={set("first_name")} /></label>
        <label><span className={label}>Last name *</span><input className={field} value={form.last_name} onChange={set("last_name")} /></label>
        <label><span className={label}>Work email *</span><input className={field} type="email" value={form.email} onChange={set("email")} /></label>
        <label><span className={label}>Joining date *</span><input className={field} type="date" value={form.joining_date} onChange={set("joining_date")} /></label>
        <label><span className={label}>Business unit *</span>
          <select className={field} value={form.business_unit_id} onChange={set("business_unit_id")}>
            <option value="">Pick a business unit</option>
            {orgOptions.businessUnits.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label><span className={label}>Delivery center</span>
          <select className={field} value={form.company_id} onChange={set("company_id")}>
            <option value="">The business unit's only company</option>
            {orgOptions.companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label><span className={label}>Country</span>
          <select className={field} value={form.country} onChange={set("country")}>
            <option value="">The delivery center's country</option>
            {(template?.countries || []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        </label>
        <label><span className={label}>Employment type</span>
          <select className={field} value={form.employment_type} onChange={set("employment_type")}>
            <option value="">{employmentTypes[0] ? `${employmentTypes[0].label} (default)` : "Default"}</option>
            {employmentTypes.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </label>
        <label><span className={label}>Designation (org role)</span>
          <select className={field} value={form.current_title} onChange={set("current_title")}>
            <option value="">Pick a role</option>
            {(template?.org_roles || []).map((r) => <option key={r.name} value={r.name}>{r.name} (level {r.level})</option>)}
          </select>
        </label>
        <label><span className={label}>Reporting manager (their seat in the org chart; approves timesheets)</span>
          <select className={field} value={form.reporting_manager_id} onChange={set("reporting_manager_id")}>
            <option value="">None: their BU head</option>
            {managers.map((m) => <option key={m.user_id} value={m.user_id}>{m.name} ({m.title || `level ${m.level}`})</option>)}
          </select>
          {roleLevel && !managers.length ? <span className="text-xs text-amber-700">Nobody is seated one or two levels above {form.current_title}: seat their manager under Organizational Hierarchy first.</span> : null}
        </label>
        <label><span className={label}>Billable? *</span>
          <select className={field} value={form.billable} onChange={set("billable")}>
            <option value="">Choose</option>
            <option value="yes">Billable: client-facing, bench when not on a project</option>
            <option value="no">Non-billable: internal staff, cost is overhead</option>
          </select>
        </label>
        <label><span className={label}>Monthly salary (USD) *</span><input className={field} type="number" min="0" value={form.monthly_salary_usd} onChange={set("monthly_salary_usd")} /></label>
        <label><span className={label}>Bill rate (USD / hour)</span><input className={field} type="number" min="0" value={form.bill_rate_usd} onChange={set("bill_rate_usd")} /></label>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={form.existing_staff} onChange={set("existing_staff")} />
          Already working here (recorded as Buddy Program graduated, audited under your name)
        </label>
      </div>
      {error ? <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
      <div className="mt-4 flex gap-2">
        <Button variant="primary" disabled={busy} onClick={submit}><UserPlus className="h-4 w-4" /> {busy ? "Adding…" : "Add employee"}</Button>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
      </div>
    </Modal>
  );
}
