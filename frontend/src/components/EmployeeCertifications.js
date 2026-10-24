// Certificates an employee holds (one record each: earned date, expiry, issuer, certificate
// number). These records are the one truth the training and certification dashboards count.
// The current Guidewire level is derived from them (the highest Guidewire certificate held,
// active and not expired); only the target level is typed in here.
import { useCallback, useEffect, useState } from "react";
import { Award, Trash2, Pencil } from "lucide-react";
import { Button } from "./ui";
import {
  addEmployeeCertificate,
  deleteEmployeeCertificate,
  getCertificationOptions,
  listEmployeeCertificates,
  updateEmployeeCertificate,
  updateEmployeeCertifications,
} from "../services/api/employees";
import { confirmDialog } from "../utils/dialogs";

const dateOnly = (value) => (value ? String(value).slice(0, 10) : "");
const today = () => new Date().toISOString().slice(0, 10);
const EMPTY_FORM = { certificationId: "", earnedDate: "", expiresDate: "", issuer: "", certNumber: "" };

function CertificateRow({ record, statuses, employeeId, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState(record.status);
  const [expiresDate, setExpiresDate] = useState(dateOnly(record.expires_date));
  const [error, setError] = useState("");
  const expired = record.expires_date && dateOnly(record.expires_date) < today();

  const save = async () => {
    setError("");
    try {
      await updateEmployeeCertificate(employeeId, record.id, { status, expires_date: expiresDate || null });
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to save the certificate.");
    }
  };

  const remove = async () => {
    if (!(await confirmDialog(`Remove ${record.cert_name} from this employee?`))) return;
    setError("");
    try {
      await deleteEmployeeCertificate(employeeId, record.id);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to remove the certificate.");
    }
  };

  return (
    <div className="rounded border bg-gray-50 p-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold">
            {record.cert_name}
            {record.guidewire_level ? <span className="ml-2 text-xs text-gray-500">Guidewire {record.guidewire_level}</span> : null}
          </div>
          <div className="text-xs text-gray-600">
            {record.status} · earned {dateOnly(record.earned_date)} ·{" "}
            {record.expires_date ? (
              <span className={expired ? "font-semibold text-rose-700" : ""}>
                {expired ? "expired" : "expires"} {dateOnly(record.expires_date)}
              </span>
            ) : (
              "no expiry"
            )}
            {record.issuer ? ` · ${record.issuer}` : ""}
            {record.cert_number ? ` · #${record.cert_number}` : ""}
          </div>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => setEditing((v) => !v)}>
            <Pencil className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" onClick={remove}>
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
      {editing ? (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <label className="text-xs">
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="ml-1 rounded border px-2 py-1 text-xs">
              {statuses.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="text-xs">
            Expires
            <input type="date" value={expiresDate} onChange={(e) => setExpiresDate(e.target.value)}
              className="ml-1 rounded border px-2 py-1 text-xs" />
          </label>
          <Button variant="primary" size="sm" onClick={save}>Save</Button>
        </div>
      ) : null}
      {error ? <div className="mt-1 text-xs text-rose-700">{error}</div> : null}
    </div>
  );
}

export default function EmployeeCertifications({ employee, onChanged }) {
  const [options, setOptions] = useState(null);
  const [records, setRecords] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [adding, setAdding] = useState(false);
  const [target, setTarget] = useState(employee.guidewire_certification_expected || "None");
  const [currentLevel, setCurrentLevel] = useState(employee.guidewire_certification_current || null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [opts, list] = await Promise.all([getCertificationOptions(), listEmployeeCertificates(employee.id)]);
      setOptions(opts);
      setRecords(list.certificates || []);
      setCurrentLevel(list.guidewire_certification_current || null);
    } catch (err) {
      setError(err.message || "Failed to load certificates.");
    }
  }, [employee.id]);

  useEffect(() => {
    load();
  }, [load]);

  const changed = () => {
    load();
    onChanged();
  };

  const add = async () => {
    if (!form.certificationId || !form.earnedDate) {
      setError("Pick a certificate and the date it was earned.");
      return;
    }
    if (form.expiresDate && form.expiresDate < form.earnedDate) {
      setError("The expiry date must be on or after the earned date.");
      return;
    }
    setError("");
    try {
      await addEmployeeCertificate(employee.id, {
        certification_id: form.certificationId,
        earned_date: form.earnedDate,
        expires_date: form.expiresDate || null,
        issuer: form.issuer || null,
        cert_number: form.certNumber || null,
      });
      setForm(EMPTY_FORM);
      setAdding(false);
      changed();
    } catch (err) {
      setError(err.message || "Failed to add the certificate.");
    }
  };

  const saveTarget = async () => {
    setError("");
    setMessage("");
    try {
      await updateEmployeeCertifications(employee.id, { guidewire_certification_expected: target });
      setMessage("Target saved");
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to save the target level.");
    }
  };

  return (
    <div>
      <h3 className="mb-1 flex items-center gap-1 text-base font-semibold text-gray-900">
        <Award className="h-4 w-4" /> Certifications
      </h3>
      <p className="mb-3 text-xs text-gray-500">
        Every certificate held, with its expiry. The current Guidewire level comes from these records.
      </p>

      <div className="mb-3 grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="mb-1 font-semibold text-gray-700">Current Guidewire level</div>
          <div>{currentLevel || "None held"}</div>
        </div>
        <div>
          <label className="mb-1 block font-semibold text-gray-700">Target level</label>
          <div className="flex gap-2">
            <select value={target} onChange={(e) => setTarget(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm">
              {(options?.guidewire_levels || ["None"]).map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
            <Button variant="secondary" size="sm" onClick={saveTarget}>Save</Button>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        {records.length === 0 ? <div className="text-sm text-gray-500">No certificates recorded.</div> : null}
        {records.map((record) => (
          <CertificateRow key={record.id} record={record} statuses={options?.statuses || []} employeeId={employee.id}
            onChanged={changed} />
        ))}
      </div>

      {adding ? (
        <div className="mt-3 grid grid-cols-2 gap-2 rounded border p-3 text-sm">
          <label className="col-span-2">
            <span className="text-xs font-semibold text-gray-700">Certificate</span>
            <select value={form.certificationId} onChange={(e) => setForm({ ...form, certificationId: e.target.value })}
              className="w-full rounded-lg border px-3 py-2 text-sm">
              <option value="">Select a certificate</option>
              {(options?.certifications || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.cert_name}{c.validity_months ? ` (valid ${c.validity_months} months)` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="text-xs font-semibold text-gray-700">Earned</span>
            <input type="date" value={form.earnedDate} onChange={(e) => setForm({ ...form, earnedDate: e.target.value })}
              className="w-full rounded-lg border px-3 py-2 text-sm" />
          </label>
          <label>
            <span className="text-xs font-semibold text-gray-700">Expires (blank: catalog validity)</span>
            <input type="date" value={form.expiresDate} onChange={(e) => setForm({ ...form, expiresDate: e.target.value })}
              className="w-full rounded-lg border px-3 py-2 text-sm" />
          </label>
          <label>
            <span className="text-xs font-semibold text-gray-700">Issuer</span>
            <input value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })}
              className="w-full rounded-lg border px-3 py-2 text-sm" />
          </label>
          <label>
            <span className="text-xs font-semibold text-gray-700">Certificate number</span>
            <input value={form.certNumber} onChange={(e) => setForm({ ...form, certNumber: e.target.value })}
              className="w-full rounded-lg border px-3 py-2 text-sm" />
          </label>
          <div className="col-span-2 flex gap-2">
            <Button variant="primary" size="sm" onClick={add}>Add certificate</Button>
            <Button variant="ghost" size="sm" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" size="sm" className="mt-3" onClick={() => setAdding(true)}>
          Add certificate
        </Button>
      )}
      {message ? <div className="mt-2 text-xs text-gray-600">{message}</div> : null}
      {error ? <div className="mt-2 text-xs text-rose-700">{error}</div> : null}
    </div>
  );
}
