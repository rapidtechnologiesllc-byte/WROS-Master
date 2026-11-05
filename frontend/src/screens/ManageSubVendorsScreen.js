// Manage Sub-vendors (CEO 2026-11-03: "a manage sub vendor page", like a Pay Bills screen): who we buy from and what
// we owe them, the bills, what needs approval, what can be paid and what was, W-9 and 1099 records, the roles sent to
// them and the candidates they sent back. HRMS never moves money: a payment is made outside and its reference recorded.
import { useCallback, useEffect, useState } from "react";
import { Button, Card, Input, Select } from "../components/ui";
import TabbedScreen from "../components/TabbedScreen";
import VendorInvoicesTab, { SubVendorsPanel } from "../components/VendorInvoicesTab";
import {
  acceptSubVendorSubmission, getContractors, getSubVendorRoles, getSubVendors, getSubVendorSubmissions,
  rejectSubVendorSubmission, requestSubVendorW9, updateSubVendor,
} from "../services/api/invoices";

const usd = (cents) => (cents == null ? "—" : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const th = "px-3 py-2 text-left text-xs font-semibold text-gray-500";
const td = "px-3 py-2 align-top text-sm text-gray-800";

function useLoad(loader) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const reload = useCallback(() => {
    setError("");
    return loader().then(setData).catch((err) => setError(err.message || "Could not load."));
  }, [loader]);
  useEffect(() => { reload(); }, [reload]);
  return { data, error, setError, reload };
}

const Failure = ({ children }) => (children ? <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{children}</div> : null);
const Empty = ({ children }) => <div className="py-6 text-center text-sm text-gray-500">{children}</div>;

const loadVendorsAndPeople = async () => {
  const [vendors, people] = await Promise.all([getSubVendors(), getContractors()]);
  return { vendors: vendors || [], people: people || { contractors: [], employees: [] } };
};

function VendorsTab() {
  const { data, error, setError, reload } = useLoad(loadVendorsAndPeople);
  const save = (id, body) => updateSubVendor(id, body).then(reload).catch((err) => setError(err.message || "Could not save."));
  const vendors = data?.vendors || [];
  return (
    <div className="grid gap-4">
      <Failure>{error}</Failure>
      <Card title="Vendors" subtitle="What each sub-vendor is owed, and whether they receive new roles.">
        {vendors.length ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr><th className={th}>Vendor</th><th className={th}>Contractors</th><th className={th}>Payment terms (days)</th>
                <th className={th}>Last paid</th><th className={th}>Unpaid bills</th><th className={th}>Open balance</th><th className={th}>New roles</th></tr></thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id} className="border-t">
                    <td className={td}><div className="font-semibold">{v.company_name}</div><div className="text-xs text-gray-500">{v.contact_email}</div></td>
                    <td className={td}>{v.contractors}</td>
                    <td className={td}>
                      <input aria-label={`Payment terms for ${v.company_name}`} type="number" min="0" defaultValue={v.payment_terms_days}
                        className="w-20 rounded border px-2 py-1 text-sm"
                        onBlur={(e) => { if (Number(e.target.value) !== v.payment_terms_days) save(v.id, { payment_terms_days: Number(e.target.value) }); }} />
                    </td>
                    <td className={td}>{v.last_paid_on || "—"}</td>
                    <td className={td}>{v.unpaid_bills}</td>
                    <td className={td}>{usd(v.open_balance_usd_cents)}</td>
                    <td className={td}>
                      <input type="checkbox" aria-label={`${v.company_name} receives new roles`} checked={v.receives_new_roles}
                        onChange={(e) => save(v.id, { receives_new_roles: e.target.checked })} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No sub-vendors yet: add the first one below, or while adding an employee.</Empty>}
      </Card>
      {data ? <SubVendorsPanel vendors={vendors} contractors={data.people.contractors} employees={data.people.employees} onChanged={reload} /> : null}
    </div>
  );
}

function TaxTab() {
  const load = useCallback(() => getSubVendors(), []);
  const { data, error, setError, reload } = useLoad(load);
  const act = (promise) => promise.then(reload).catch((err) => setError(err.message || "Could not save."));
  const vendors = data || [];
  return (
    <Card title="W-9 & 1099" subtitle="The W-9 on file for each vendor and what was paid to them this calendar year.">
      <Failure>{error}</Failure>
      {vendors.length ? (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr><th className={th}>Vendor</th><th className={th}>W-9</th><th className={th}>Tax id on file</th><th className={th}>1099 vendor</th><th className={th}>Paid this year</th><th className={th} /></tr></thead>
            <tbody>
              {vendors.map((v) => (
                <tr key={v.id} className="border-t">
                  <td className={td}>{v.company_name}</td>
                  <td className={td}>
                    <Select value={v.w9_status} onChange={(value) => act(updateSubVendor(v.id, { w9_status: value }))}
                      options={[{ value: "NOT_REQUESTED", label: "Not requested" }, { value: "REQUESTED", label: "Requested" }, { value: "RECEIVED", label: "Received" }]} />
                  </td>
                  <td className={td}>{v.has_tax_id ? "Yes" : "No"}</td>
                  <td className={td}><input type="checkbox" aria-label={`${v.company_name} is a 1099 vendor`} checked={v.is_1099} onChange={(e) => act(updateSubVendor(v.id, { is_1099: e.target.checked }))} /></td>
                  <td className={td}>{usd(v.paid_this_year_usd_cents)}</td>
                  <td className={td}>{v.w9_status !== "RECEIVED" ? <Button variant="ghost" onClick={() => act(requestSubVendorW9(v.id))}>Email W-9 request</Button> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No sub-vendors yet.</Empty>}
    </Card>
  );
}

function RolesTab() {
  const load = useCallback(() => getSubVendorRoles(), []);
  const { data, error } = useLoad(load);
  return (
    <Card title="Roles sent" subtitle="New client roles go to every approved vendor that receives them, without the client's name. Vendors reply with a resume.">
      <Failure>{error}</Failure>
      {data?.length ? (
        <table className="w-full">
          <thead><tr><th className={th}>Role</th><th className={th}>Vendor</th><th className={th}>Emailed</th><th className={th}>Candidates</th><th className={th}>Status</th></tr></thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id} className="border-t"><td className={td}>{r.job_title}</td><td className={td}>{r.sub_vendor_name}</td>
                <td className={td}>{r.notified_at ? r.notified_at.slice(0, 10) : "Waiting to send"}</td><td className={td}>{r.submissions}</td><td className={td}>{r.status}</td></tr>
            ))}
          </tbody>
        </table>
      ) : <Empty>No roles sent yet.</Empty>}
    </Card>
  );
}

function SubmissionRow({ item, onChanged, onError }) {
  const [form, setForm] = useState({ email: item.candidate_email || "", note: "" });
  const [busy, setBusy] = useState(false);
  const run = (promise) => {
    setBusy(true);
    return promise.then(onChanged).catch((err) => onError(err.message || "Could not save.")).finally(() => setBusy(false));
  };
  return (
    <div className="grid gap-2 rounded-2xl border p-4">
      <div className="flex flex-wrap justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-gray-900">{item.candidate_name} for {item.job_title}</div>
          <div className="text-xs text-gray-500">{item.sub_vendor_name} · {item.resume_name || "no resume"} · {item.candidate_phone || "no phone"}</div>
        </div>
        <span className="text-xs font-semibold text-gray-700">{item.status.replace(/_/g, " ").toLowerCase()}</span>
      </div>
      {item.feedback_note ? <div className="text-xs text-gray-600">Reason: {item.feedback_note}</div> : null}
      {item.status === "PENDING_REVIEW" ? (
        <div className="grid items-end gap-2 sm:grid-cols-[1fr_auto_1fr_auto]">
          <Input label="Candidate email" value={form.email} onChange={(v) => setForm((f) => ({ ...f, email: v }))} />
          <Button variant="primary" disabled={busy || !form.email} onClick={() => run(acceptSubVendorSubmission(item.id, { email: form.email }))}>Accept</Button>
          <Input label="Why not (sent to the vendor)" value={form.note} onChange={(v) => setForm((f) => ({ ...f, note: v }))} />
          <Button variant="ghost" disabled={busy || !form.note} onClick={() => run(rejectSubVendorSubmission(item.id, form.note))}>Reject</Button>
        </div>
      ) : null}
    </div>
  );
}

function SubmissionsTab() {
  const load = useCallback(() => getSubVendorSubmissions(), []);
  const { data, error, setError, reload } = useLoad(load);
  return (
    <Card title="Candidates from sub-vendors" subtitle="Resumes they replied with. Accepting creates the candidate; Thunder does not contact a vendor's candidate.">
      <div className="grid gap-3">
        <Failure>{error}</Failure>
        {data?.length ? data.map((item) => <SubmissionRow key={item.id} item={item} onChanged={reload} onError={setError} />) : <Empty>No candidates received yet.</Empty>}
      </div>
    </Card>
  );
}

const TABS = [
  { key: "vendors", label: "Vendors", resource: "invoices", render: () => <VendorsTab /> },
  { key: "bills", label: "Bills", resource: "invoices", render: () => <VendorInvoicesTab /> },
  { key: "approvals", label: "Approvals", resource: "invoices", render: () => <VendorInvoicesTab statuses={["RECEIVED"]} hideForm emptyText="Nothing waits for approval." /> },
  { key: "payments", label: "Payments", resource: "invoices", render: () => <VendorInvoicesTab statuses={["APPROVED", "PAID"]} hideForm emptyText="No approved or paid bills yet." /> },
  { key: "tax", label: "W-9 & 1099", resource: "invoices", render: () => <TaxTab /> },
  { key: "roles", label: "Roles sent", resource: "jobs", render: () => <RolesTab /> },
  { key: "submissions", label: "Candidates", resource: "candidates", render: () => <SubmissionsTab /> },
];

export default function ManageSubVendorsScreen() {
  return <TabbedScreen title="Sub-vendors" tabs={TABS} />;
}
