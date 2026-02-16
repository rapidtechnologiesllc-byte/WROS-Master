// Job details view with edit/submit flow.
import { useEffect, useState } from "react";
import { Briefcase } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge, TextArea } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export default function JobDetails({ job, onSubmit, onGoApproval, onUpdate }) {
  const [isEditing, setIsEditing] = useState(false);
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
      if (parts[0] === "USD" || parts[0] === "INR") {
        next.currency = parts[0];
      }
      if (parts[1] === "Hourly" || parts[1] === "Annual") {
        next.frequency = parts[1];
      }
      if (parts.length >= 3) {
        next.amount = parts.slice(2).join(" ");
      }
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

  const saveEdits = () => {
    const skills = skillsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    onUpdate({
      title,
      positionType,
      priority,
      companyClient,
      companyType,
      contactPerson,
      division,
      dept,
      location,
      experienceLevel,
      payRange,
      startDate,
      endDate,
      jobStatus,
      noOfPositions,
      hiringManager,
      skills,
      hiringManagerOneLiner: hmOneLiner,
      internalJD,
      jobDescription: internalJD,
      status: jobStatus || "Draft"
    });
    setIsEditing(false);
  };

  const cancelEdits = () => {
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
    setStartDate(job.startDate || "");
    setEndDate(job.endDate || "");
    setJobStatus(job.jobStatus || job.status || "Draft");
    setNoOfPositions(job.noOfPositions || 1);
    setHiringManager(job.hiringManager || "");
    setSkillsText((job.skills || []).join(", "));
    setHmOneLiner(job.hiringManagerOneLiner || "");
    setInternalJD(job.internalJD || job.jobDescription || "");
    setIsEditing(false);
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Update Job Details / Assignment"
        icon={<Briefcase className="h-4 w-4" />}
        right={<StatusBadge status={job.status} />}
      >
        {isEditing ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Job Title" value={title} onChange={setTitle} />
            <Select
              label="Position Type"
              value={positionType}
              onChange={setPositionType}
              options={["Full time", "Contract"]}
            />
            <Select
              label="Priority"
              value={priority}
              onChange={setPriority}
              options={["Low", "High"]}
            />
            <Input label="Department" value={dept} onChange={setDept} />
            <Input
              label="Company / Client"
              value={companyClient}
              onChange={setCompanyClient}
            />
            <Input label="Company Type" value={companyType} onChange={setCompanyType} />
            <Input label="Contact Person" value={contactPerson} onChange={setContactPerson} />
            <Input label="Division" value={division} onChange={setDivision} />
            <Input label="Location" value={location} onChange={setLocation} />
            <Select
              label="Job Status"
              value={jobStatus}
              onChange={setJobStatus}
              options={["Draft", "Submitted", "Open", "Closed"]}
            />
            <Input
              label="No. of Positions"
              value={String(noOfPositions)}
              onChange={(value) => setNoOfPositions(Number(value || 0))}
              type="number"
            />
            <Input
              label="Experience Level"
              value={experienceLevel}
              onChange={setExperienceLevel}
            />
            <div className="md:col-span-2">
              <div className="mb-1 text-xs font-semibold text-gray-700">Pay Range</div>
              <div className="grid gap-3 md:grid-cols-3">
                <Select
                  label="Currency"
                  value={payCurrency}
                  onChange={(value) => {
                    setPayCurrency(value);
                    if (value === "INR") {
                      setPayFrequency("Annual");
                    }
                  }}
                  options={["USD", "INR"]}
                />
                <Select
                  label="Frequency"
                  value={payFrequency}
                  onChange={setPayFrequency}
                  options={payCurrency === "USD" ? ["Hourly", "Annual"] : ["Annual"]}
                />
                <Input
                  label={payFrequency === "Hourly" ? "Amount (Hourly)" : "Amount (Annual)"}
                  value={payAmount}
                  onChange={(value) => {
                    setPayAmount(value);
                    const normalized = value ? String(value).trim() : "";
                    const next = normalized
                      ? `${payCurrency} ${payFrequency} ${normalized}`
                      : "";
                    setPayRange(next);
                  }}
                  type="number"
                />
              </div>
            </div>
            <Input label="Start Date" value={startDate} onChange={setStartDate} type="date" />
            <Input label="End Date" value={endDate} onChange={setEndDate} type="date" />
            <Input
              label="Hiring Manager"
              value={hiringManager}
              onChange={setHiringManager}
            />
            <Input
              label="Skills (comma separated)"
              value={skillsText}
              onChange={setSkillsText}
            />
            <div className="md:col-span-2">
              <TextArea
                label="Hiring Manager 1-Liner"
                value={hmOneLiner}
                onChange={setHmOneLiner}
                rows={2}
              />
            </div>
            <div className="md:col-span-2">
              <TextArea
                label="Internal Job Description"
                value={internalJD}
                onChange={setInternalJD}
                rows={6}
              />
            </div>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <div className="text-xs font-semibold text-gray-500">Job</div>
              <div className="text-lg font-extrabold tracking-tight">{job.title}</div>
              <div className="mt-1 text-sm text-gray-700">
                {job.dept} • {job.location}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold text-gray-500">Hiring Manager</div>
              <div className="text-sm font-semibold">{job.hiringManager}</div>
              <div className="mt-2 flex flex-wrap gap-1">
                {job.skills.map((s) => (
                  <span key={s} className={cx(pill, "border-gray-200 bg-gray-50")}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="mt-4 flex flex-wrap justify-end gap-2">
          {isEditing ? (
            <>
              <Button variant="secondary" onClick={cancelEdits}>
                Cancel
              </Button>
              <Button onClick={saveEdits}>Save Changes</Button>
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setIsEditing(true)}>
                Edit Job
              </Button>
              <Button variant="secondary" onClick={onGoApproval}>
                Send to hiring manager (approval)
              </Button>
              <Button onClick={onSubmit}>Submit to internal hiring team</Button>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
