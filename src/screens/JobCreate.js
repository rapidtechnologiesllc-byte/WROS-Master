// Job creation form (simple flow).
import { useMemo, useState } from "react";
import { Briefcase } from "lucide-react";
import { generateJobDescription, createJob } from "../services/api/jobs";
import { Button, Card, Input, Select, TextArea } from "../components/ui";

export default function JobCreate({ onSave }) {
  const [title, setTitle] = useState("Frontend Engineer");
  const [positionType, setPositionType] = useState("");
  const [priority, setPriority] = useState("");
  const [companyClient, setCompanyClient] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [division, setDivision] = useState("");
  const [dept, setDept] = useState("Digital");
  const [location, setLocation] = useState("Remote");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [payRange, setPayRange] = useState("");
  const [payCurrency, setPayCurrency] = useState("USD");
  const [payFrequency, setPayFrequency] = useState("Annual");
  const [payAmount, setPayAmount] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [skills, setSkills] = useState("React, TypeScript");
  const [jobStatus, setJobStatus] = useState("Draft");
  const [noOfPositions, setNoOfPositions] = useState(1);
  const [hm, setHm] = useState("Sanjay");
  const [hmOneLiner, setHmOneLiner] = useState("");
  const internalJdTemplate =
    "Overview:\n\nRoles & Responsibilities:\n- \n\nQualifications:\n- ";
  const [internalJD, setInternalJD] = useState(internalJdTemplate);
  const [externalJD, setExternalJD] = useState("");
  const [actionNotice, setActionNotice] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const normalizeJobStatusForApi = (uiStatus) => {
    const raw = String(uiStatus || "").trim();
    const lower = raw.toLowerCase();
    if (lower === "open") return "active";
    if (lower === "public") return "public";
    if (lower === "draft") return "draft";
    if (lower === "submitted") return "submitted";
    if (lower === "closed") return "closed";
    return lower;
  };

  const newId = useMemo(() => {
    const n = Math.floor(2000 + Math.random() * 8000);
    return `J-${n}`;
  }, []);

  const generateInternalOverviewAndRolesFromApi = async () => {
    const oneLiner = hmOneLiner.trim();
    if (!oneLiner) {
      setActionNotice("Add a hiring manager 1-liner to generate roles.");
      return;
    }
    setActionNotice("");
    setIsGenerating(true);
    try {
      const data = await generateJobDescription({
        job_title: title,
        job_description: oneLiner,
        job_experience: experienceLevel,
        job_location: location
      });
      const generated = (data?.generated_job_description || "").trim();
      if (!generated) {
        throw new Error("AI did not return a job description.");
      }
      setInternalJD(generated);
      if (Array.isArray(data?.job_skills) && data.job_skills.length) {
        setSkills(data.job_skills.join(", "));
      }
      setActionNotice("Overview + Roles generated.");
    } catch (err) {
      setActionNotice(err.message || "Failed to generate job description.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreateJob = async () => {
    const required = [
      { label: "Job Title", value: title },
      { label: "Hiring Manager 1-Liner", value: hmOneLiner },
      { label: "Internal Job Description", value: internalJD },
      { label: "Skills", value: skills },
      { label: "Experience Level", value: experienceLevel },
      { label: "Location", value: location },
      { label: "Company Type", value: companyType },
      { label: "Company / Client", value: companyClient },
      { label: "Contact Person", value: contactPerson },
      { label: "Job Status", value: jobStatus },
      { label: "No. of Positions", value: noOfPositions },
      { label: "Start Date", value: startDate },
      { label: "End Date", value: endDate }
    ];
    const missing = required
      .filter(({ value }) => String(value ?? "").trim() === "" || Number(value) === 0)
      .map(({ label }) => label);
    if (missing.length) {
      setActionNotice(`Please fill required fields: ${missing.join(", ")}.`);
      return;
    }

    setActionNotice("");
    setIsSaving(true);
    try {
      const data = await createJob({
        job_title: title,
        job_description: internalJD,
        job_skills: skills,
        job_experience: experienceLevel,
        job_location: location,
        company_type: companyType,
        company_name: companyClient,
        contact_person: contactPerson,
        job_status: normalizeJobStatusForApi(jobStatus),
        no_of_positions: Number(noOfPositions || 0),
        start_date: startDate,
        end_date: endDate
      });
      const createdId = data?.job_id || newId;
      onSave({
        id: createdId,
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
        jobDescription: internalJD,
        jobSkillsText: skills,
        skills: skills
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        hiringManager: hm,
        hiringManagerOneLiner: hmOneLiner,
        internalJD,
        externalJD,
        status: jobStatus || "Draft"
      });
      setActionNotice("Job created successfully.");
    } catch (err) {
      setActionNotice(err.message || "Failed to create job.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid gap-4">
      <Card title="Create New Job" icon={<Briefcase className="h-4 w-4" />}>
        <div className="grid gap-3 md:grid-cols-2">
          <Input label="Job ID" value={newId} onChange={() => {}} />
          <Input label="Job Title *" value={title} onChange={setTitle} />
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
            label="Company / Client *"
            value={companyClient}
            onChange={setCompanyClient}
          />
          <Input label="Company Type *" value={companyType} onChange={setCompanyType} />
          <Input
            label="Contact Person *"
            value={contactPerson}
            onChange={setContactPerson}
          />
          <Input label="Division" value={division} onChange={setDivision} />
          <Input label="Location *" value={location} onChange={setLocation} />
          <Select
            label="Job Status *"
            value={jobStatus}
            onChange={setJobStatus}
            options={["Draft", "Open", "Public", "Submitted", "Closed"]}
          />
          <Input
            label="No. of Positions *"
            value={String(noOfPositions)}
            onChange={(value) => setNoOfPositions(Number(value || 0))}
            type="number"
          />
          <Input
            label="Experience Level *"
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
          <Input
            label="Start Date *"
            value={startDate}
            onChange={setStartDate}
            type="date"
          />
          <Input label="End Date *" value={endDate} onChange={setEndDate} type="date" />
          <Input label="Hiring Manager (Azure AD)" value={hm} onChange={setHm} />
          <div className="md:col-span-2">
            <Input
              label="Skills (comma separated) *"
              value={skills}
              onChange={setSkills}
            />
          </div>
          <div className="md:col-span-2">
            <TextArea
              label="Hiring Manager 1-Liner *"
              value={hmOneLiner}
              onChange={setHmOneLiner}
              rows={2}
              placeholder="Include job_title, job_experience, job_location to generate JD"
            />
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={generateInternalOverviewAndRolesFromApi}
                disabled={isGenerating}
              >
                {isGenerating ? "Generating..." : "Generate Overview + Roles"}
              </Button>
            </div>
          </div>
          <div className="md:col-span-2">
            <TextArea
              label="Internal Job Description *"
              value={internalJD}
              onChange={setInternalJD}
              rows={6}
              placeholder="Editable; can be generated from AI"
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setActionNotice("Draft saved (mock).")}>
              Save Draft
            </Button>
            <Button onClick={() => setActionNotice("Submitted for approval (mock).")}>
              Submit for Approval
            </Button>
          </div>
          <Button onClick={handleCreateJob} disabled={isSaving}>
            {isSaving ? "Creating..." : "Create Job"}
          </Button>
        </div>
        {actionNotice ? (
          <div className="mt-2 text-xs text-gray-500">{actionNotice}</div>
        ) : null}
      </Card>
    </div>
  );
}
