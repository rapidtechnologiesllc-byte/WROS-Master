import { useEffect, useState } from "react";
import { Briefcase, Edit2 } from "lucide-react";
import { Button, Input, Select, StatusBadge, TextArea } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export default function JobDetails({ job, onSubmit, onGoApproval, onUpdate, mode = "view" }) {
  const [editingSection, setEditingSection] = useState(null);
  const [title, setTitle] = useState(job.title || "");
  const [positionType, setPositionType] = useState(job.positionType || "");
  const [priority, setPriority] = useState(job.priority || "");
  const [companyClient, setCompanyClient] = useState(job.companyClient || "");
  const [companyType, setCompanyType] = useState(job.companyType || "");
  const [contactPerson, setContactPerson] = useState(job.contactPerson || "");
  const [division, setDivision] = useState(job.division || "");
  const [dept, setDept] = useState(job.dept || "");
  const [location, setLocation] = useState(job.location || "");
  const [experienceLevel, setExperienceLevel] = useState(job.experienceLevel || "");
  const [payRange, setPayRange] = useState(job.payRange || "");
  const [payCurrency, setPayCurrency] = useState("USD");
  const [payFrequency, setPayFrequency] = useState("Annual");
  const [payAmount, setPayAmount] = useState("");
  const [startDate, setStartDate] = useState(job.startDate || "");
  const [endDate, setEndDate] = useState(job.endDate || "");
  const [jobStatus, setJobStatus] = useState(job.jobStatus || job.status || "Draft");
  const [noOfPositions, setNoOfPositions] = useState(job.noOfPositions || 1);
  const [hiringManager, setHiringManager] = useState(job.hiringManager || "");
  const [skillsText, setSkillsText] = useState((job.skills || []).join(", "));
  const [hmOneLiner, setHmOneLiner] = useState(job.hiringManagerOneLiner || "");
  const [internalJD, setInternalJD] = useState(job.internalJD || job.jobDescription || "");

  useEffect(() => {
    const parsePay = (value) => {
      const next = { currency: "USD", frequency: "Annual", amount: "" };
      if (!value) return next;
      const parts = String(value).trim().split(/\s+/);
      if (parts[0] === "USD" || parts[0] === "INR") next.currency = parts[0];
      if (parts[1] === "Hourly" || parts[1] === "Annual") next.frequency = parts[1];
      if (parts.length >= 3) next.amount = parts.slice(2).join(" ");
      return next;
    };
    const parsedPay = parsePay(job.payRange || "");
    setTitle(job.title || "");
    setPositionType(job.positionType || "");
    setPriority(job.priority || "");
    setCompanyClient(job.companyClient || "");
    setCompanyType(job.companyType || "");
    setContactPerson(job.contactPerson || "");
    setDivision(job.division || "");
    setDept(job.dept || "");
    setLocation(job.location || "");
    setExperienceLevel(job.experienceLevel || "");
    setPayRange(job.payRange || "");
    setPayCurrency(parsedPay.currency);
    setPayFrequency(parsedPay.frequency);
    setPayAmount(parsedPay.amount);
    setStartDate(job.startDate || "");
    setEndDate(job.endDate || "");
    setJobStatus(job.jobStatus || job.status || "Draft");
    setNoOfPositions(job.noOfPositions || 1);
    setHiringManager(job.hiringManager || "");
    setSkillsText((job.skills || []).join(", "));
    setHmOneLiner(job.hiringManagerOneLiner || "");
    setInternalJD(job.internalJD || job.jobDescription || "");
  }, [job]);

  const saveSection = (section) => {
    const skills = skillsText.split(",").map((s) => s.trim()).filter(Boolean);
    onUpdate({
      title, positionType, priority, companyClient, companyType, contactPerson,
      division, dept, location, experienceLevel, payRange, startDate, endDate,
      jobStatus, noOfPositions, hiringManager, skills,
      hiringManagerOneLiner: hmOneLiner, internalJD, jobDescription: internalJD,
      status: jobStatus || "Draft"
    });
    setEditingSection(null);
  };

  const cancelSection = () => {
    setEditingSection(null);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Briefcase className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
            <p className="text-sm text-gray-500">{job.dept} • {job.location}</p>
          </div>
        </div>
        <StatusBadge status={job.status} />
      </div>

      {/* Basic Information */}
      <CardBlock title="Basic Information" subtitle="Job title, position type, and priority">
        {editingSection === "basic" ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Job Title *" value={title} onChange={setTitle} />
            <Select label="Position Type" value={positionType} onChange={setPositionType}
              options={["Full time", "Contract"]} />
            <Select label="Priority" value={priority} onChange={setPriority}
              options={["Low", "High"]} />
            <Input label="Department" value={dept} onChange={setDept} />
            <div className="md:col-span-2 flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("basic")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="Job Title" value={job.title} />
              <Info label="Position Type" value={job.positionType} />
              <Info label="Priority" value={job.priority} />
              <Info label="Department" value={job.dept} />
            </div>
            {mode !== "view" && (
              <Button variant="ghost" size="sm" onClick={() => setEditingSection("basic")}
                className="mt-3">
                <Edit2 className="h-4 w-4 mr-1" /> Edit
              </Button>
            )}
          </div>
        )}
      </CardBlock>

      {/* Company & Contact */}
      <CardBlock title="Company & Contact" subtitle="Client details and point of contact">
        {editingSection === "company" ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Company / Client" value={companyClient} onChange={setCompanyClient} />
            <Input label="Company Type" value={companyType} onChange={setCompanyType} />
            <Input label="Contact Person" value={contactPerson} onChange={setContactPerson} />
            <Input label="Division" value={division} onChange={setDivision} />
            <div className="md:col-span-2 flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("company")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="Company / Client" value={job.companyClient} />
              <Info label="Company Type" value={job.companyType} />
              <Info label="Contact Person" value={job.contactPerson} />
              <Info label="Division" value={job.division} />
            </div>
            {mode !== "view" && (
              <Button variant="ghost" size="sm" onClick={() => setEditingSection("company")}
                className="mt-3">
                <Edit2 className="h-4 w-4 mr-1" /> Edit
              </Button>
            )}
          </div>
        )}
      </CardBlock>

      {/* Compensation */}
      <CardBlock title="Compensation" subtitle="Pay range and salary information">
        {editingSection === "compensation" ? (
          <div className="space-y-3">
            <div className="grid gap-3 md:grid-cols-3">
              <Select label="Currency" value={payCurrency} onChange={(value) => {
                setPayCurrency(value);
                if (value === "INR") setPayFrequency("Annual");
              }} options={["USD", "INR"]} />
              <Select label="Frequency" value={payFrequency} onChange={setPayFrequency}
                options={payCurrency === "USD" ? ["Hourly", "Annual"] : ["Annual"]} />
              <Input label={payFrequency === "Hourly" ? "Amount (Hourly)" : "Amount (Annual)"}
                value={payAmount} onChange={(value) => {
                  setPayAmount(value);
                  const normalized = value ? String(value).trim() : "";
                  const next = normalized ? `${payCurrency} ${payFrequency} ${normalized}` : "";
                  setPayRange(next);
                }} type="number" />
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("compensation")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <Info label="Pay Range" value={job.payRange} />
            {mode !== "view" && (
              <Button variant="ghost" size="sm" onClick={() => setEditingSection("compensation")}
                className="mt-3">
                <Edit2 className="h-4 w-4 mr-1" /> Edit
              </Button>
            )}
          </div>
        )}
      </CardBlock>

      {/* Requirements & Skills */}
      <CardBlock title="Requirements & Skills" subtitle="Experience level and required skills">
        {editingSection === "skills" ? (
          <div className="grid gap-3">
            <Input label="Experience Level" value={experienceLevel} onChange={setExperienceLevel} />
            <Input label="Location" value={location} onChange={setLocation} />
            <Input label="Skills (comma separated)" value={skillsText} onChange={setSkillsText} />
            <Input label="Hiring Manager" value={hiringManager} onChange={setHiringManager} />
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("skills")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid gap-3 md:grid-cols-2 mb-3">
              <Info label="Experience Level" value={job.experienceLevel} />
              <Info label="Location" value={job.location} />
              <Info label="Hiring Manager" value={job.hiringManager} />
            </div>
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-2">Skills</div>
              <div className="flex flex-wrap gap-1">
                {job.skills?.map((s) => (
                  <span key={s} className={cx(pill, "border-gray-200 bg-gray-50")}>{s}</span>
                ))}
              </div>
            </div>
            {mode !== "view" && (
              <Button variant="ghost" size="sm" onClick={() => setEditingSection("skills")}
                className="mt-3">
                <Edit2 className="h-4 w-4 mr-1" /> Edit
              </Button>
            )}
          </div>
        )}
      </CardBlock>

      {/* Timeline & Status */}
      <CardBlock title="Timeline & Status" subtitle="Job dates and current status">
        {editingSection === "timeline" ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Start Date" value={startDate} onChange={setStartDate} type="date" />
            <Input label="End Date" value={endDate} onChange={setEndDate} type="date" />
            <Select label="Job Status" value={jobStatus} onChange={setJobStatus}
              options={["Draft", "Open", "Public", "Submitted", "Closed"]} />
            <Input label="No. of Positions" value={String(noOfPositions)}
              onChange={(value) => setNoOfPositions(Number(value || 0))} type="number" />
            <div className="md:col-span-2 flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("timeline")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="Start Date" value={job.startDate} />
              <Info label="End Date" value={job.endDate} />
              <Info label="Status" value={job.jobStatus || job.status} />
              <Info label="No. of Positions" value={job.noOfPositions} />
            </div>
            {mode !== "view" && (
              <Button variant="ghost" size="sm" onClick={() => setEditingSection("timeline")}
                className="mt-3">
                <Edit2 className="h-4 w-4 mr-1" /> Edit
              </Button>
            )}
          </div>
        )}
      </CardBlock>

      {/* Job Description */}
      <CardBlock title="Job Description" subtitle="Internal job description and hiring manager notes">
        {editingSection === "description" ? (
          <div className="space-y-3">
            <TextArea label="Hiring Manager 1-Liner" value={hmOneLiner}
              onChange={setHmOneLiner} rows={2} />
            <TextArea label="Internal Job Description" value={internalJD}
              onChange={setInternalJD} rows={6} />
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("description")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-500 mb-1">Hiring Manager 1-Liner</div>
              <p className="text-sm text-gray-700">{job.hiringManagerOneLiner || "-"}</p>
            </div>
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-1">Job Description</div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{job.internalJD || job.jobDescription || "-"}</p>
            </div>
            {mode !== "view" && (
              <Button variant="ghost" size="sm" onClick={() => setEditingSection("description")}
                className="mt-3">
                <Edit2 className="h-4 w-4 mr-1" /> Edit
              </Button>
            )}
          </div>
        )}
      </CardBlock>

      {/* Action Buttons */}
      {editingSection === null && (
        <div className="flex flex-wrap gap-2 justify-end">
          <Button variant="secondary" onClick={onGoApproval}>
            Send to hiring manager (approval)
          </Button>
          <Button onClick={onSubmit}>Submit to internal hiring team</Button>
        </div>
      )}
    </div>
  );
}

function CardBlock({ title, subtitle, children }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-5">
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
      <span className="text-xs uppercase tracking-wide text-gray-500">{label}</span>
      <div className="font-medium text-sm text-gray-900 mt-1">{value || "-"}</div>
    </div>
  );
}
