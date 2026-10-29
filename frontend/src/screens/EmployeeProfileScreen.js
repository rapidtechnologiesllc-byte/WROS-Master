// One employee's profile (CEO 2026-10-24): header with who they are and where they stand, then tabs
// for About, Profile, Job, Documents, Finances and Timeline. Every section edits in place (its own
// Edit button); the server decides what each viewer may see and change (GET /employees/{id}/profile).
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Briefcase, Camera, IdCard, Mail, MapPin, Pencil, Phone } from "lucide-react";
import { Button, Input, Select, TextArea } from "../components/ui";
import cx from "../utils/cx";
import { alertDialog } from "../utils/dialogs";
import useTabParam from "../utils/useTabParam";
import { apiRequest } from "../services/api/client";
import {
  employeePhotoUrl,
  uploadEmployeePhoto,
  getEmployeeImportTemplate,
  getEmployeeProfile,
  updateEmployeeBillable,
  updateEmployeeDetails,
  updateEmployeeManager,
  updateEmployeeOrganization,
} from "../services/api/employees";
import { DeploymentStatus, EmploymentStatus, fullName, isPast, statusLabel } from "../components/EmployeeStatus";
import { EmploymentActions, HtdControl } from "../components/EmployeeEditPanels";
import EmployeeAllocations from "../components/EmployeeAllocations";
import EmployeeCertifications from "../components/EmployeeCertifications";
import EscalationsPanel from "../components/EmployeeEscalations";
import { FeedbackSection, ReviewList } from "../components/PerformancePanel";
import { getEmployeePerformance, getMyPerformance } from "../services/api/performance";
import ActivityTimeline from "../components/timeline/ActivityTimeline";

const TABS = [
  ["about", "About"], ["profile", "Profile"], ["job", "Job"], ["documents", "Documents"],
  ["finance", "Finances"], ["performance", "Performance"], ["timeline", "Timeline"],
];
const COMPANIES_PATH = "/api/v1/api/admin/users-access-control/delivery-centers";

const money = (cents) => (cents == null ? "—" : `$${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}`);
const initials = (emp) => `${(emp.first_name || "?")[0]}${(emp.last_name || "")[0] || ""}`.toUpperCase();
const months = (n) => (n == null ? "—" : `${Math.floor(n / 12)}y ${n % 12}m`);
function tenure(joined) {
  if (!joined) return "—";
  const days = Math.floor((Date.now() - new Date(joined).getTime()) / 86400000);
  if (days < 0) return `joins in ${-days}d`;
  return months(Math.floor(days / 30.44));
}

function Section({ title, subtitle, action, children }) {
  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-gray-900">{title}</h3>
          {subtitle ? <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-0.5 text-sm text-gray-900 break-words">{children ?? "—"}</div>
    </div>
  );
}

// A section of plain fields with its own Edit button. fields: [{ key, label, type, options, readOnly,
// help, display }]; values: current values by key; onSave(changes) gets only what changed.
function EditableSection({ title, subtitle, fields, values, canEdit, onSave }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const start = () => {
    setForm(Object.fromEntries(fields.map((f) => [f.key, values[f.key] ?? ""])));
    setError("");
    setEditing(true);
  };
  const save = async () => {
    const changes = {};
    fields.forEach((f) => {
      if (f.readOnly) return;
      const before = values[f.key] ?? "";
      const after = form[f.key] ?? "";
      if (String(before) !== String(after)) {
        changes[f.key] = after === "" ? null : f.type === "number" ? Number(after) : after;
      }
    });
    if (!Object.keys(changes).length) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave(changes);
      setEditing(false);
    } catch (err) {
      console.error(`[EmployeeProfile] Failed to save ${title}:`, err);
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const action = canEdit && !editing ? (
    <Button variant="ghost" size="sm" onClick={start}><Pencil className="h-3.5 w-3.5" /> Edit</Button>
  ) : null;

  return (
    <Section title={title} subtitle={subtitle} action={action}>
      {editing ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            {fields.map((f) => {
              const set = (value) => setForm((current) => ({ ...current, [f.key]: value }));
              const common = { label: f.label, value: form[f.key] ?? "", onChange: set };
              let control;
              if (f.type === "select") {
                control = <Select {...common} disabled={f.readOnly}
                  options={[{ value: "", label: "—" }, ...(f.options || [])]} />;
              } else if (f.type === "textarea") {
                control = <TextArea {...common} rows={3} disabled={f.readOnly} />;
              } else {
                control = <Input {...common} type={f.type === "date" ? "date" : f.type === "number" ? "number" : "text"}
                  disabled={f.readOnly} />;
              }
              return (
                <div key={f.key} className={f.type === "textarea" ? "sm:col-span-2" : undefined}>
                  {control}
                  {f.help ? <div className="mt-1 text-xs text-gray-500">{f.help}</div> : null}
                </div>
              );
            })}
          </div>
          {error ? <div className="text-sm text-rose-700">{error}</div> : null}
          <div className="flex gap-2">
            <Button onClick={save} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map((f) => (
            <div key={f.key} className={f.type === "textarea" ? "sm:col-span-2 lg:col-span-3" : undefined}>
              <Field label={f.label}>
                {f.display ? f.display(values[f.key]) : f.type === "select"
                  ? (f.options || []).find((o) => o.value === values[f.key])?.label || values[f.key] || null
                  : values[f.key] || null}
              </Field>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

function OrganizationSection({ profile, orgOptions, managers, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [companyId, setCompanyId] = useState("");
  const [buId, setBuId] = useState("");
  const [managerId, setManagerId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const manager = profile.job.reporting_manager;

  const start = () => {
    setCompanyId(profile.company_id || "");
    setBuId(profile.bu_id ? String(profile.bu_id) : "");
    setManagerId(manager?.user_id || "");
    setError("");
    setEditing(true);
  };
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      if (companyId !== (profile.company_id || "") || buId !== (profile.bu_id ? String(profile.bu_id) : "")) {
        await updateEmployeeOrganization(profile.id, { company_id: companyId || null,
          business_unit_id: buId ? Number(buId) : null });
      }
      if (managerId && managerId !== (manager?.user_id || "")) {
        await updateEmployeeManager(profile.id, managerId);
      }
      setEditing(false);
      onChanged();
    } catch (err) {
      console.error("[EmployeeProfile] Failed to save organization:", err);
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Section title="Organization" subtitle="Headcount is counted by employer company and business unit; approvals follow the reporting line."
      action={profile.can_edit && !editing
        ? <Button variant="ghost" size="sm" onClick={start}><Pencil className="h-3.5 w-3.5" /> Edit</Button> : null}>
      {editing ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Select label="Company (employer)" value={companyId} onChange={setCompanyId}
              options={[{ value: "", label: "Not set" }, ...orgOptions.companies.map((c) => ({ value: c.id, label: c.name }))]} />
            <Select label="Business unit" value={buId} onChange={setBuId}
              options={[{ value: "", label: "Not set" },
                ...orgOptions.businessUnits.map((b) => ({ value: String(b.id), label: b.name }))]} />
            <Select label="Reporting manager" value={managerId} onChange={setManagerId}
              options={[{ value: "", label: manager ? manager.name : "Not set" },
                ...managers.filter((m) => m.user_id !== manager?.user_id)
                  .map((m) => ({ value: m.user_id, label: `${m.name}${m.title ? ` (${m.title})` : ""}` }))]} />
          </div>
          {error ? <div className="text-sm text-rose-700">{error}</div> : null}
          <div className="flex gap-2">
            <Button onClick={save} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
          <Field label="Company">{profile.job.company_name || <span className="text-amber-700">Not set</span>}</Field>
          <Field label="Business unit">{profile.job.business_unit_name}</Field>
          <Field label="Reporting manager"><ManagerLink manager={manager} /></Field>
        </div>
      )}
    </Section>
  );
}

function ManagerLink({ manager }) {
  if (!manager) return null;
  return manager.employee_id
    ? <Link to={`/employees/${manager.employee_id}`} className="text-blue-700 hover:underline">{manager.name}</Link>
    : manager.name;
}

// A stored photo as a blob URL; null while loading or when there is none
function usePhoto(profile, kind, present) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let cancelled = false;
    let made = null;
    if (!present) {
      setUrl(null);
      return undefined;
    }
    employeePhotoUrl(profile.id, kind)
      .then((value) => {
        made = value;
        if (!cancelled) setUrl(value);
      })
      .catch((err) => console.error(`[EmployeeProfile] Failed to load ${kind}:`, err));
    return () => {
      cancelled = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [profile.id, kind, present, profile.photo_version]);
  return url;
}

function PhotoButton({ profile, kind, onChanged, className, label }) {
  const [busy, setBusy] = useState(false);
  const pick = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      await uploadEmployeePhoto(profile.id, kind, file);
      onChanged();
    } catch (err) {
      console.error(`[EmployeeProfile] Failed to upload ${kind}:`, err);
      alertDialog(`Could not change the ${kind === "cover" ? "cover photo" : "photo"}: ${err.message}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <label title={label} aria-label={label}
      className={cx("inline-flex cursor-pointer items-center gap-1 rounded-full bg-white/90 text-gray-700 shadow hover:bg-white", className,
        busy && "opacity-60")}>
      <Camera className="h-4 w-4" />
      <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={pick} disabled={busy} />
    </label>
  );
}

function Header({ profile, onChanged }) {
  const photo = usePhoto(profile, "photo", profile.has_photo);
  const cover = usePhoto(profile, "cover", profile.has_cover);
  const canChange = profile.is_self || profile.can_edit;
  const contact = [
    [Mail, profile.email, `mailto:${profile.email}`],
    [Phone, profile.personal.phone, profile.personal.phone ? `tel:${profile.personal.phone}` : null],
    [MapPin, statusLabel(profile.work_location)],
    [IdCard, profile.employee_number],
  ].filter(([, text]) => text);
  return (
    <div className="overflow-hidden rounded-2xl border bg-white shadow-sm">
      <div className="relative h-32 bg-gradient-to-r from-bx-navy via-[#1d3a63] to-bx-orange/70 bg-cover bg-center"
        style={cover ? { backgroundImage: `url(${cover})` } : undefined}>
        {canChange && <PhotoButton profile={profile} kind="cover" onChanged={onChanged} label="Change cover photo"
          className="absolute right-3 top-3 px-2.5 py-1.5" />}
      </div>
      <div className="px-6 pb-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="relative -mt-10 shrink-0">
              {photo ? (
                <img src={photo} alt={fullName(profile)} className="h-20 w-20 rounded-full border-4 border-white object-cover shadow" />
              ) : (
                <div className="flex h-20 w-20 items-center justify-center rounded-full border-4 border-white bg-bx-orange text-2xl font-bold text-white shadow">
                  {initials(profile)}
                </div>
              )}
              {canChange && <PhotoButton profile={profile} kind="photo" onChanged={onChanged} label="Change photo"
                className="absolute -bottom-1 -right-1 p-1.5" />}
            </div>
            <div className="pt-3">
              <h1 className="text-2xl font-bold text-gray-900">{fullName(profile)}</h1>
              <div className="flex items-center gap-1.5 text-sm text-gray-600">
                <Briefcase className="h-4 w-4" /> {profile.current_title || "No title"}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 pt-4">
            <EmploymentStatus employee={profile} />
            <DeploymentStatus employee={profile} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-b pb-4 text-sm text-gray-700">
          {contact.map(([Icon, text, href]) => (
            <span key={text} className="inline-flex items-center gap-1.5">
              <Icon className="h-4 w-4 text-gray-400" />
              {href ? <a href={href} className="text-blue-700 hover:underline">{text}</a> : text}
            </span>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <div className="grid grid-cols-2 gap-x-10 gap-y-2 sm:grid-cols-3">
            <Field label="Business unit">{profile.job.business_unit_name}</Field>
            <Field label="Company">{profile.job.company_name}</Field>
            <Field label="Reporting manager"><ManagerLink manager={profile.job.reporting_manager} /></Field>
          </div>
          {profile.can_edit && <EmploymentActions employee={profile} onChanged={onChanged} />}
        </div>
      </div>
    </div>
  );
}

function AboutTab({ profile }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Section title="Summary">
          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
            <Field label="Joined">{profile.joining_date}</Field>
            <Field label="Tenure">{tenure(profile.joining_date)}</Field>
            <Field label="Experience">{months(profile.job.total_experience_months)}</Field>
            <Field label="Employment"><EmploymentStatus employee={profile} /></Field>
            <Field label="Deployment"><DeploymentStatus employee={profile} /></Field>
            <Field label="Allocated">{profile.allocated_pct}% · {profile.is_billable ? "billable" : "internal"}</Field>
            {profile.exit_date ? <Field label={isPast(profile) ? "Exited" : "Last working day"}>{profile.exit_date}</Field> : null}
          </div>
        </Section>
        <Section title="Current allocations">
          <EmployeeAllocations employee={profile} onChanged={() => {}} canAdd={false} />
        </Section>
        <Section title="Notes & history" subtitle="Notes, including emails forwarded to the HRMS mailbox about this employee.">
          <ActivityTimeline entityType="employee" entityId={profile.id} />
        </Section>
      </div>
      <Section title={`Reporting team (${profile.reporting_team.length})`}>
        {profile.reporting_team.length ? (
          <ul className="space-y-3">
            {profile.reporting_team.map((member) => (
              <li key={member.employee_id} className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-700">
                  {member.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}
                </span>
                <div>
                  <Link to={`/employees/${member.employee_id}`} className="text-sm font-medium text-blue-700 hover:underline">
                    {member.name}
                  </Link>
                  <div className="text-xs text-gray-500">{member.title || "—"}</div>
                </div>
              </li>
            ))}
          </ul>
        ) : <div className="text-sm text-gray-500">Nobody reports to {profile.first_name}.</div>}
      </Section>
    </div>
  );
}

function ProfileTab({ profile, save }) {
  const values = { ...profile, ...profile.personal };
  return (
    <div className="space-y-4">
      <EditableSection title="Basic information" canEdit={profile.can_edit} values={values} onSave={save} fields={[
        { key: "first_name", label: "First name" },
        { key: "last_name", label: "Last name" },
        { key: "legal_name", label: "Legal name (as on documents)" },
        { key: "gender", label: "Gender" },
        { key: "date_of_birth", label: "Date of birth", type: "date" },
        { key: "nationality", label: "Nationality" },
      ]} />
      <EditableSection title="Contact" canEdit={profile.can_edit} values={values} onSave={save} fields={[
        { key: "email", label: "Work email", readOnly: profile.has_login,
          help: profile.has_login ? "They sign in with this email: change it in Users & Access." : null },
        { key: "personal_email", label: "Personal email" },
        { key: "phone", label: "Phone" },
        { key: "current_address", label: "Current address", type: "textarea" },
        { key: "permanent_address", label: "Permanent address", type: "textarea" },
      ]} />
      <EditableSection title="Emergency contact" canEdit={profile.can_edit} values={values} onSave={save} fields={[
        { key: "emergency_contact_name", label: "Name" },
        { key: "emergency_contact_phone", label: "Phone" },
      ]} />
    </div>
  );
}

function JobTab({ profile, save, reload, orgOptions, managers }) {
  const values = { ...profile, ...profile.job };
  const optionsOf = (list) => list.map((value) => ({ value, label: statusLabel(value) }));
  return (
    <div className="space-y-4">
      <EditableSection title="Employment" canEdit={profile.can_edit} values={values} onSave={save} fields={[
        { key: "employee_number", label: "Employee number", readOnly: true },
        { key: "current_title", label: "Job title" },
        { key: "employment_type", label: "Employment type", type: "select", options: optionsOf(profile.options.employment_types) },
        { key: "work_location", label: "Work location", type: "select", options: optionsOf(profile.options.work_locations) },
        { key: "joining_date", label: "Date of joining", type: "date", readOnly: profile.employment_status !== "JOINING",
          help: profile.employment_status !== "JOINING" ? "Fixed once they have joined." : null },
        { key: "confirmation_date", label: "Confirmation date", type: "date" },
        { key: "visa_status", label: "Visa / work authorization" },
        { key: "total_experience_months", label: "Total experience (months)", type: "number", display: months },
      ]} />
      <OrganizationSection profile={profile} orgOptions={orgOptions} managers={managers} onChanged={reload} />
      <Section title="Deployment & programs" subtitle="Where they are deployed now; HTD and the Buddy Program come before deployment.">
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
          <Field label="Deployment"><DeploymentStatus employee={profile} /></Field>
          <Field label="Delivery engine">{statusLabel(profile.job.delivery_engine)}{profile.job.core_certified ? " · Core certified" : ""}</Field>
          <Field label="Buddy Program">
            {statusLabel(profile.programs.buddy_program_status)}
            {profile.programs.buddy_program_graduation_date ? ` · graduated ${profile.programs.buddy_program_graduation_date}` : ""}
          </Field>
          {!isPast(profile) && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Hire-Train-Deploy</div>
              <div className="mt-1"><HtdControl employee={profile} canEdit={profile.can_edit} onChanged={reload} /></div>
            </div>
          )}
        </div>
      </Section>
      <Section title="Allocations">
        <EmployeeAllocations employee={profile} onChanged={reload} canAdd={!isPast(profile)} />
      </Section>
      <div className="rounded-2xl border bg-white p-5 shadow-sm">
        <EmployeeCertifications employee={profile} onChanged={reload} />
      </div>
      <div className="rounded-2xl border bg-white p-5 shadow-sm">
        <EscalationsPanel employeeId={profile.id} />
      </div>
    </div>
  );
}

function DocumentsTab({ profile }) {
  const origin = profile.origin;
  if (!origin) {
    return (
      <Section title="Hiring record">
        <div className="text-sm text-gray-500">
          {fullName(profile)} was added directly (not hired through a candidate record), so there is no offer, background
          check or onboarding checklist on file.
        </div>
      </Section>
    );
  }
  const docLink = (url, label) => (url ? <a href={url} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">{label}</a> : null);
  return (
    <div className="space-y-4">
      <Section title="Candidate record" subtitle="Resume, interviews and everything recruitment collected live on the candidate record."
        action={<Link to={`/candidates/${origin.candidate_id}`} className="text-sm font-semibold text-blue-700 hover:underline">Open candidate record</Link>}>
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
          <Field label="Source">{origin.source}{origin.referred ? " (employee referral)" : ""}</Field>
          <Field label="Applied for">{origin.applied_for}</Field>
          <Field label="Recruiter">{origin.recruiter}</Field>
          {origin.linkedin_url ? <Field label="LinkedIn">{docLink(origin.linkedin_url, "Profile")}</Field> : null}
        </div>
      </Section>
      <Section title="Offer">
        {origin.offer ? (
          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
            <Field label="Status">{origin.offer.status}</Field>
            <Field label="Released">{origin.offer.released_at?.slice(0, 10)}</Field>
            <Field label="Offered joining date">{origin.offer.joining_date}</Field>
            <Field label="Offer letter">{docLink(origin.offer.document_url, "Download")}</Field>
          </div>
        ) : <div className="text-sm text-gray-500">No offer letter on file.</div>}
      </Section>
      <Section title="Background check">
        {origin.background_check ? (
          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
            <Field label="Status">{statusLabel(origin.background_check.status)}</Field>
            <Field label="Verdict">{origin.background_check.verdict_at?.slice(0, 10)}</Field>
            <Field label="Report">{docLink(origin.background_check.report_url, "Open report")}</Field>
          </div>
        ) : <div className="text-sm text-gray-500">No background check on file.</div>}
      </Section>
      <Section title="Onboarding checklists">
        {origin.checklists.length ? (
          <ul className="space-y-1 text-sm">
            {origin.checklists.map((c) => (
              <li key={c.id}>Checklist #{c.id}: {c.status}{c.completed_at ? ` (completed ${c.completed_at.slice(0, 10)})` : ""}</li>
            ))}
          </ul>
        ) : <div className="text-sm text-gray-500">No onboarding checklist was assigned.</div>}
      </Section>
    </div>
  );
}

function FinanceTab({ profile, save, reload }) {
  const finance = profile.finance;
  const [message, setMessage] = useState("");
  const toggleBillable = async () => {
    setMessage("");
    try {
      await updateEmployeeBillable(profile.id, !profile.is_billable);
      reload();
    } catch (err) {
      console.error("[EmployeeProfile] Failed to change billable:", err);
      setMessage(`Could not change: ${err.message}`);
    }
  };
  return (
    <div className="space-y-4">
      <Section title="Billing" subtitle="Billable people sit on the bench between projects; internal staff are overhead, never bench."
        action={profile.can_edit ? (
          <Button variant="ghost" size="sm" onClick={toggleBillable}>
            Make {profile.is_billable ? "internal (non-billable)" : "billable"}
          </Button>
        ) : null}>
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
          <Field label="Billable">{profile.is_billable ? "Billable" : "Internal (non-billable)"}</Field>
          <Field label="Classification">{statusLabel(finance.billing_classification)}</Field>
          <Field label="Default bill rate">{money(finance.billing_rate_usd_cents)}{finance.billing_rate_usd_cents != null ? " / hr" : ""}</Field>
        </div>
        {message ? <div className="mt-2 text-sm text-rose-700">{message}</div> : null}
      </Section>
      {finance.compensation_visible ? (
        <EditableSection title="Compensation & tax" subtitle="Visible to Finance only. Government ids show the last 4 characters."
          canEdit={profile.can_edit_compensation} onSave={save}
          values={{ pay: finance.pay_amount_cents == null ? "" : finance.pay_amount_cents / 100,
            pay_basis: finance.pay_basis || "", pay_currency: finance.pay_currency || "",
            monthly_cost: finance.base_salary_usd_cents,
            billing_rate: finance.billing_rate_usd_cents == null ? "" : finance.billing_rate_usd_cents / 100,
            pan_number: finance.pan_number, tax_id: finance.tax_id }}
          fields={[
            { key: "pay", label: "Pay (amount)", type: "number",
              display: (v) => (v === "" ? "—" : `${Number(v).toLocaleString()} ${finance.pay_currency || ""}`) },
            { key: "pay_basis", label: "Paid", type: "select",
              options: profile.options.pay_bases.map((b) => ({ value: b, label: statusLabel(b) })) },
            { key: "pay_currency", label: "Pay currency", type: "select",
              options: profile.options.currencies.map((c) => ({ value: c, label: c })) },
            { key: "monthly_cost", label: "Monthly cost (USD, before statutory and overhead)", readOnly: true,
              display: (v) => (v == null ? "Unknown: no exchange rate for this currency" : money(v)),
              help: "Worked out from the pay; this is what the P&L and bench cost use." },
            { key: "billing_rate", label: "Default bill rate (USD / hour)", type: "number", display: (v) => (v === "" ? "—" : money(v * 100)) },
            { key: "pan_number", label: "PAN", help: "Type the full number to replace it." },
            { key: "tax_id", label: "Tax id (SSN / other)", help: "Type the full number to replace it." },
          ]} />
      ) : (
        <Section title="Compensation">
          <div className="text-sm text-gray-500">Salary is visible to Finance only.</div>
        </Section>
      )}
      <Section title="Bank details">
        <div className="text-sm text-gray-700">
          {finance.bank_on_file ? "Bank account on file (stored encrypted; never shown here)." : "No bank account on file."}
        </div>
      </Section>
    </div>
  );
}

// Performance: reviews by the reporting chain, then praise / feedback / internal notes. A task link
// (?review=<id>) opens that review.
function PerformanceTab({ profile }) {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      setData(await (profile.is_self ? getMyPerformance() : getEmployeePerformance(profile.id)));
    } catch (err) {
      console.error("[EmployeeProfile] Failed to load performance:", err);
      setError(err.message);
    }
  }, [profile.id, profile.is_self]);
  useEffect(() => {
    load();
  }, [load]);
  if (error) return <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>;
  if (!data) return <div className="py-6 text-center text-gray-500">Loading performance...</div>;
  return (
    <div className="space-y-4">
      <Section title="Reviews" subtitle="Reporting manager every two weeks, BU head monthly, partner quarterly. Only the reporting chain and HR see them; the employee sees a review once it is completed and shared with them.">
        <ReviewList data={data} openReviewId={searchParams.get("review")} onSaved={load} />
      </Section>
      <Section title="Feedback" subtitle="Praise is visible to everyone; feedback to the employee, their reporting chain and HR.">
        <FeedbackSection data={data} employeeId={profile.id} onSaved={load} allowGive={!profile.is_self} />
      </Section>
    </div>
  );
}

const HISTORY_LABEL = { STATUS: "Status", ENGINE: "Delivery engine" };
function describe(value) {
  if (value == null) return "—";
  if (typeof value === "object") return Object.values(value).map((v) => statusLabel(String(v))).join(", ");
  return statusLabel(String(value));
}

function TimelineTab({ profile }) {
  if (!profile.history.length) {
    return <Section title="Timeline"><div className="text-sm text-gray-500">No changes recorded yet.</div></Section>;
  }
  return (
    <Section title="Timeline" subtitle="Every recorded change, newest first.">
      <ol className="relative space-y-4 border-l border-gray-200 pl-5">
        {profile.history.map((event, index) => (
          // eslint-disable-next-line react/no-array-index-key -- history rows have no stable id of their own
          <li key={`${event.kind}-${event.date}-${index}`}>
            <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-bx-orange" />
            <div className="text-xs text-gray-500">{event.date || "—"}</div>
            <div className="text-sm text-gray-900">
              <span className="font-semibold">{HISTORY_LABEL[event.kind] || statusLabel(event.kind)}</span>
              {": "}{describe(event.from)} → {describe(event.to)}
            </div>
            {event.reason ? <div className="text-xs text-gray-600">{event.reason}</div> : null}
          </li>
        ))}
      </ol>
    </Section>
  );
}

export default function EmployeeProfileScreen() {
  const { employeeId } = useParams();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [orgOptions, setOrgOptions] = useState({ companies: [], businessUnits: [] });
  const [managers, setManagers] = useState([]);
  const tabKeys = useMemo(() => TABS.map(([key]) => key), []);
  const [tab, setTab] = useTabParam(tabKeys);

  const reload = useCallback(async () => {
    setError("");
    try {
      const loaded = await getEmployeeProfile(employeeId);
      setProfile({ ...loaded, photo_version: Date.now() });
    } catch (err) {
      console.error("[EmployeeProfile] Failed to load:", err);
      setError(err.message);
    }
  }, [employeeId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    Promise.all([apiRequest(COMPANIES_PATH), apiRequest("/rbac/business-units")])
      .then(([c, b]) => setOrgOptions({ companies: c.data?.delivery_centers || [], businessUnits: b.data?.business_units || [] }))
      .catch((err) => setError(`Could not load companies/business units: ${err.message}`));
    getEmployeeImportTemplate()
      .then((template) => setManagers(template?.managers || []))
      .catch((err) => setError(`Could not load managers: ${err.message}`));
  }, []);

  // Personal / job / finance edits share one endpoint; finance amounts are typed in dollars
  const save = async (changes) => {
    const body = { ...changes };
    if ("pay" in body) {
      body.pay_amount_cents = body.pay == null ? null : Math.round(body.pay * 100);
      delete body.pay;
    }
    if ("billing_rate" in body) {
      body.billing_rate_usd_cents = body.billing_rate == null ? null : Math.round(body.billing_rate * 100);
      delete body.billing_rate;
    }
    await updateEmployeeDetails(employeeId, body);
    await reload();
  };

  if (error && !profile) {
    return (
      <div className="space-y-3">
        <Link to="/employees" className="inline-flex items-center gap-1 text-sm text-blue-700 hover:underline">
          <ArrowLeft className="h-4 w-4" /> Employees
        </Link>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">Could not load this employee: {error}</div>
      </div>
    );
  }
  if (!profile) return <div className="py-10 text-center text-gray-500">Loading employee...</div>;

  return (
    <div className="space-y-4">
      <Link to={isPast(profile) ? "/employees?tab=past" : "/employees"}
        className="inline-flex items-center gap-1 text-sm text-blue-700 hover:underline">
        <ArrowLeft className="h-4 w-4" /> {isPast(profile) ? "Past employees" : "Employees"}
      </Link>
      <Header profile={profile} onChanged={reload} />
      {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div> : null}
      <div className="flex flex-wrap gap-1 border-b" role="tablist">
        {TABS.map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
            className={cx("-mb-px border-b-2 px-4 py-2 text-sm font-semibold transition",
              tab === key ? "border-bx-orange text-gray-900" : "border-transparent text-gray-500 hover:text-gray-900")}>
            {label}
          </button>
        ))}
      </div>
      {tab === "about" && <AboutTab profile={profile} />}
      {tab === "profile" && <ProfileTab profile={profile} save={save} />}
      {tab === "job" && <JobTab profile={profile} save={save} reload={reload} orgOptions={orgOptions} managers={managers} />}
      {tab === "documents" && <DocumentsTab profile={profile} />}
      {tab === "finance" && <FinanceTab profile={profile} save={save} reload={reload} />}
      {tab === "performance" && <PerformanceTab profile={profile} />}
      {tab === "timeline" && <TimelineTab profile={profile} />}
    </div>
  );
}
