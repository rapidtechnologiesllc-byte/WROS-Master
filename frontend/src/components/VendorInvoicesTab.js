// Sub-vendor invoices (CEO 2026-11-02): a vendor's invoice is recorded against its contractors'
// approved timesheets, approved by Finance, and paid only once the client has paid for that work.
// Its amounts are the contractors' cost in the P&L. Contractors (supplied by a sub-vendor, paid
// through it at an hourly rate) get the Contractor role: their timesheets and tasks only.
import { useCallback, useEffect, useState } from "react";
import { Button, Input, Select } from "./ui";
import cx from "../utils/cx";
import {
  addSubVendor,
  addVendorInvoice,
  approveVendorInvoice,
  getContractors,
  getEligibleVendorTimesheets,
  getSubVendors,
  getVendorInvoices,
  payVendorInvoice,
  rejectVendorInvoice,
  setContractor,
} from "../services/api/invoices";

const STATUS_STYLES = {
  RECEIVED: "border-gray-200 bg-gray-50 text-gray-800",
  APPROVED: "border-amber-200 bg-amber-50 text-amber-800",
  PAID: "border-emerald-200 bg-emerald-50 text-emerald-800",
  REJECTED: "border-rose-200 bg-rose-50 text-rose-700",
};

const usd = (cents) =>
  cents == null ? "—" : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const toCents = (dollars) => Math.round(parseFloat(String(dollars).replace(/[$,]/g, "")) * 100);
const today = () => new Date().toISOString().slice(0, 10);

function Notice({ tone = "error", children }) {
  if (!children) return null;
  return (
    <div className={cx("rounded-lg border px-3 py-2 text-xs",
      tone === "error" ? "border-rose-200 bg-rose-50 text-rose-700" : "border-gray-200 bg-gray-50 text-gray-700")}>
      {children}
    </div>
  );
}

function SubVendorsPanel({ vendors, contractors, employees, onChanged }) {
  const [vendor, setVendor] = useState({ company_name: "", contact_email: "" });
  const [assign, setAssign] = useState({ employee_id: "", sub_vendor_id: "", rate: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const run = async (action) => {
    setSaving(true);
    setError("");
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(err.message || "Could not save.");
    } finally {
      setSaving(false);
    }
  };

  const approved = vendors.filter((v) => v.status === "APPROVED");
  return (
    <div className="grid gap-3 rounded-2xl border p-4">
      <div className="text-sm font-semibold text-gray-900">Sub-vendors and their contractors</div>
      <Notice>{error}</Notice>
      {vendors.length ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {vendors.map((v) => (
            <div key={v.id} className="rounded-xl border bg-gray-50 px-3 py-2 text-sm">
              <div className="font-semibold text-gray-900">{v.company_name}</div>
              <div className="text-xs text-gray-600">{v.contact_email} · {v.contractors} contractor(s) · {v.status.toLowerCase()}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-gray-600">No sub-vendors yet: add the first one below, or while adding an employee.</div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="Sub-vendor company" value={vendor.company_name} onChange={(v) => setVendor((s) => ({ ...s, company_name: v }))} />
        <Input label="Accounts email" value={vendor.contact_email} onChange={(v) => setVendor((s) => ({ ...s, contact_email: v }))} />
        <div className="flex items-end">
          <Button variant="primary" disabled={saving || !vendor.company_name || !vendor.contact_email}
            onClick={() => run(async () => { await addSubVendor(vendor); setVendor({ company_name: "", contact_email: "" }); })}>
            Add sub-vendor
          </Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <Select label="Employee" value={assign.employee_id} onChange={(v) => setAssign((s) => ({ ...s, employee_id: v }))}
          options={[{ value: "", label: "Select…" }, ...employees.map((e) => ({ value: e.employee_id, label: e.name }))]} />
        <Select label="Supplied by" value={assign.sub_vendor_id} onChange={(v) => setAssign((s) => ({ ...s, sub_vendor_id: v }))}
          options={[{ value: "", label: "Select…" }, ...approved.map((v) => ({ value: v.id, label: v.company_name }))]} />
        <Input label="Vendor rate ($/hour)" value={assign.rate} onChange={(v) => setAssign((s) => ({ ...s, rate: v }))} placeholder="70" />
        <div className="flex items-end">
          <Button variant="secondary" disabled={saving || !assign.employee_id || !assign.sub_vendor_id || !assign.rate}
            onClick={() => run(async () => {
              await setContractor(assign.employee_id, assign.sub_vendor_id, toCents(assign.rate));
              setAssign({ employee_id: "", sub_vendor_id: "", rate: "" });
            })}>
            Make contractor
          </Button>
        </div>
      </div>
      <div className="text-[11px] text-gray-500">
        A contractor fills timesheets with the limited Contractor access (their timesheets and tasks). Their cost in the P&amp;L is the
        vendor's invoice, else hours × the vendor rate.
      </div>
      {contractors.length ? (
        <div className="flex flex-wrap gap-2">
          {contractors.map((c) => (
            <span key={c.employee_id} className="rounded-full border bg-gray-50 px-3 py-1 text-xs text-gray-700">
              {c.name} · {c.sub_vendor_name} · {usd(c.hourly_rate_usd_cents)}/h
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AddVendorInvoiceForm({ vendors, onAdded }) {
  const [form, setForm] = useState({ sub_vendor_id: "", vendor_invoice_number: "", invoice_date: today(),
    period_start: "", period_end: "", amount: "", note: "" });
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  // the approved timesheets the invoice will cover, and the amount they come to at the vendor rate
  useEffect(() => {
    setPreview(null);
    if (!form.sub_vendor_id || !form.period_start || !form.period_end) return;
    getEligibleVendorTimesheets(form.sub_vendor_id, form.period_start, form.period_end)
      .then((res) => {
        setPreview(res);
        setForm((f) => (f.amount ? f : { ...f, amount: (res.expected_usd_cents / 100).toFixed(2) }));
      })
      .catch((err) => setError(err.message || "Could not load the timesheets."));
  }, [form.sub_vendor_id, form.period_start, form.period_end]);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await addVendorInvoice({
        sub_vendor_id: form.sub_vendor_id, vendor_invoice_number: form.vendor_invoice_number,
        invoice_date: form.invoice_date, period_start: form.period_start, period_end: form.period_end,
        amount_usd_cents: toCents(form.amount), note: form.note || null,
      });
      setForm({ sub_vendor_id: "", vendor_invoice_number: "", invoice_date: today(), period_start: "", period_end: "",
        amount: "", note: "" });
      onAdded();
    } catch (err) {
      setError(err.message || "Could not record the invoice.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid gap-3 rounded-2xl border p-4">
      <div className="text-sm font-semibold text-gray-900">Record a sub-vendor invoice</div>
      <Notice>{error}</Notice>
      <div className="grid gap-3 sm:grid-cols-3">
        <Select label="Sub-vendor" value={form.sub_vendor_id} onChange={set("sub_vendor_id")}
          options={[{ value: "", label: "Select…" }, ...vendors.map((v) => ({ value: v.id, label: v.company_name }))]} />
        <Input label="Their invoice number" value={form.vendor_invoice_number} onChange={set("vendor_invoice_number")} />
        <Input label="Invoice date" type="date" value={form.invoice_date} onChange={set("invoice_date")} />
        <Input label="Work from" type="date" value={form.period_start} onChange={set("period_start")} />
        <Input label="Work to" type="date" value={form.period_end} onChange={set("period_end")} />
        <Input label="Amount billed ($)" value={form.amount} onChange={set("amount")} />
      </div>
      {preview ? (
        preview.timesheets.length ? (
          <div className="rounded-lg border bg-gray-50 p-3 text-xs text-gray-700">
            Covers {preview.timesheets.length} approved timesheet(s):{" "}
            {preview.timesheets.map((t) => `${t.employee_name} wk ${t.week_starting_date} ${t.hours}h`).join(" · ")}.
            Expected at the vendor rate: <b>{usd(preview.expected_usd_cents)}</b>
            {form.amount && toCents(form.amount) !== preview.expected_usd_cents
              ? ` -- the amount differs by ${usd(toCents(form.amount) - preview.expected_usd_cents)}; add a note.` : ""}
          </div>
        ) : (
          <Notice>No approved timesheets of this vendor's contractors in that period that aren't already invoiced.</Notice>
        )
      ) : null}
      <Input label="Note" value={form.note} onChange={set("note")} placeholder="Why the amount differs, if it does" />
      <div>
        <Button variant="primary" disabled={saving || !preview?.timesheets?.length || !form.vendor_invoice_number || !form.amount}
          onClick={save}>
          {saving ? "Saving…" : "Record invoice"}
        </Button>
      </div>
    </div>
  );
}

function VendorInvoiceRow({ invoice, onChanged }) {
  const [open, setOpen] = useState(false);
  const [paidOn, setPaidOn] = useState(today());
  const [reference, setReference] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const act = async (action) => {
    setBusy(true);
    setError("");
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(err.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button type="button" className="text-left" onClick={() => setOpen((o) => !o)}>
          <div className="text-sm font-semibold text-gray-900">
            {invoice.sub_vendor_name} · {invoice.vendor_invoice_number}
          </div>
          <div className="text-xs text-gray-500">
            {invoice.period_start} → {invoice.period_end} · {invoice.lines.length} timesheet(s) · {usd(invoice.amount_usd_cents)}
            {invoice.variance_usd_cents ? ` (expected ${usd(invoice.expected_usd_cents)})` : ""}
          </div>
        </button>
        <div className="flex items-center gap-2">
          {invoice.status === "APPROVED" || invoice.status === "RECEIVED" ? (
            <span className={cx("rounded-full border px-2 py-0.5 text-[11px] font-semibold",
              invoice.client_paid ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-gray-200 bg-white text-gray-600")}>
              {invoice.client_paid ? "Client paid" : "Client not paid yet"}
            </span>
          ) : null}
          <span className={cx("rounded-full border px-2 py-0.5 text-[11px] font-semibold", STATUS_STYLES[invoice.status])}>
            {invoice.status}
          </span>
        </div>
      </div>
      <div className="mt-2"><Notice>{error}</Notice></div>
      {invoice.payment_blockers?.length && invoice.status === "APPROVED" ? (
        <div className="mt-2 text-xs text-gray-600">Pay after the client pays: {invoice.payment_blockers.join("; ")}.</div>
      ) : null}
      {invoice.status === "RECEIVED" ? (
        <div className="mt-3 flex gap-2">
          <Button variant="primary" disabled={busy} onClick={() => act(() => approveVendorInvoice(invoice.id, invoice.note))}>Approve</Button>
          <Button variant="ghost" disabled={busy} onClick={() => {
            const reason = window.prompt("Why is this invoice rejected?");
            if (reason) act(() => rejectVendorInvoice(invoice.id, reason));
          }}>Reject</Button>
        </div>
      ) : null}
      {invoice.status === "APPROVED" ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <Input label="Paid on" type="date" value={paidOn} onChange={setPaidOn} />
          <Input label="Payment reference" value={reference} onChange={setReference} placeholder="bank transfer id" />
          <div className="flex items-end">
            <Button variant="primary" disabled={busy || !invoice.client_paid || !reference}
              onClick={() => act(() => payVendorInvoice(invoice.id, paidOn, reference))}>
              Record vendor payment
            </Button>
          </div>
        </div>
      ) : null}
      {invoice.status === "PAID" ? (
        <div className="mt-2 text-xs text-gray-600">Paid {invoice.paid_at?.slice(0, 10)} · ref {invoice.payment_reference}</div>
      ) : null}
      {invoice.status === "REJECTED" ? (
        <div className="mt-2 text-xs text-gray-600">Rejected: {invoice.rejected_reason}</div>
      ) : null}
      {open ? (
        <table className="mt-3 w-full text-left text-xs">
          <thead className="text-gray-500"><tr><th>Contractor</th><th>Week</th><th>Hours</th><th>Rate</th><th>Amount</th></tr></thead>
          <tbody>
            {invoice.lines.map((l, i) => (
              <tr key={i} className="border-t"><td className="py-1">{l.employee_name}</td><td>{l.week_starting_date}</td>
                <td>{l.hours}</td><td>{usd(l.rate_usd_cents)}</td><td>{usd(l.amount_usd_cents)}</td></tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}

export default function VendorInvoicesTab() {
  const [data, setData] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [people, setPeople] = useState({ contractors: [], employees: [] });
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [list, vendorList, contractorList] = await Promise.all([getVendorInvoices(), getSubVendors(), getContractors()]);
      setData(list);
      setVendors(vendorList || []);
      setPeople(contractorList || { contractors: [], employees: [] });
    } catch (err) {
      setError(err.message || "Could not load sub-vendor invoices.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="grid gap-4">
      <Notice>{error}</Notice>
      {data ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border p-3"><div className="text-xs text-gray-500">Owed to sub-vendors</div>
            <div className="text-lg font-semibold">{usd(data.owed_usd_cents)}</div></div>
          <div className="rounded-2xl border p-3"><div className="text-xs text-gray-500">Payable now (client has paid)</div>
            <div className="text-lg font-semibold text-emerald-700">{usd(data.payable_now_usd_cents)}</div></div>
        </div>
      ) : null}
      <AddVendorInvoiceForm vendors={vendors.filter((v) => v.status === "APPROVED")} onAdded={load} />
      <div className="grid gap-3">
        {data?.vendor_invoices?.length ? (
          data.vendor_invoices.map((inv) => <VendorInvoiceRow key={inv.id} invoice={inv} onChanged={load} />)
        ) : (
          <div className="py-6 text-center text-sm text-gray-500">No sub-vendor invoices yet.</div>
        )}
      </div>
      <SubVendorsPanel vendors={vendors} contractors={people.contractors} employees={people.employees} onChanged={load} />
    </div>
  );
}
