// Job creation form (simple flow).
import { useEffect, useMemo, useState } from "react";
import { Briefcase } from "lucide-react";
import { generateJobDescription, createJob } from "../services/api/jobs";
import { Button, Card, Input, Select, TextArea } from "../components/ui";
import { getAllUsers } from "../services/api/users";

export default function JobCreate({ onSave, mode = "create", initialJob = null }) {
  const isReadOnly = mode === "view";
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
  const [hmInput, setHmInput] = useState("Sanjay");
  const [hmUserId, setHmUserId] = useState("");
  const [rmInput, setRmInput] = useState("");
  const [rmUserId, setRmUserId] = useState("");
  const [users, setUsers] = useState([]);
  const [usersBusy, setUsersBusy] = useState(false);
  const [hmOneLiner, setHmOneLiner] = useState("");
  const internalJdTemplate =
    "Overview:\n\nRoles & Responsibilities:\n- \n\nQualifications:\n- ";
  const [internalJD, setInternalJD] = useState(internalJdTemplate);
  const [externalJD, setExternalJD] = useState("");
  const [actionNotice, setActionNotice] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setUsersBusy(true);
      try {
        const res = await getAllUsers();
        if (!isMounted) return;
        setUsers(Array.isArray(res?.users) ? res.users : []);
      } catch {
        if (!isMounted) return;
        setUsers([]);
      } finally {
        if (!isMounted) return;
        setUsersBusy(false);
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!initialJob || mode !== "view") return;
    const parsePay = (value) => {
      const next = { currency: "USD", frequency: "Annual", amount: "" };
      if (!value) return next;
      const parts = String(value).trim().split(/\s+/);
      if (parts[0] === "USD" || parts[0] === "INR") next.currency = parts[0];
      if (parts[1] === "Hourly" || parts[1] === "Annual") next.frequency = parts[1];
      if (parts.length >= 3) next.amount = parts.slice(2).join(" ");
      return next;
    };
    const parsedPay = parsePay(initialJob.payRange || "");
    setTitle(initialJob.title || "");
    setPositionType(initialJob.positionType || "");
    setPriority(initialJob.priority || "");
    setCompanyClient(initialJob.companyClient || "");
    setCompanyType(initialJob.companyType || "");
    setContactPerson(initialJob.contactPerson || "");
    setDivision(initialJob.division || "");
    setDept(initialJob.dept || "");
    setLocation(initialJob.location || "");
    setExperienceLevel(initialJob.experienceLevel || "");
    setPayRange(initialJob.payRange || "");
    setPayCurrency(parsedPay.currency);
    setPayFrequency(parsedPay.frequency);
    setPayAmount(parsedPay.amount);
    setStartDate(initialJob.startDate || "");
    setEndDate(initialJob.endDate || "");
    setSkills((initialJob.skills || []).join(", "));
    setJobStatus(initialJob.jobStatus || initialJob.status || "Draft");
    setNoOfPositions(initialJob.noOfPositions || 1);
    setHmInput(initialJob.hiringManager || "");
    setRmInput(initialJob.reportingManager || "");
    setHmOneLiner(initialJob.hiringManagerOneLiner || "");
    setInternalJD(initialJob.internalJD || initialJob.jobDescription || "");
  }, [initialJob, mode]);

  const hmSuggestions = useMemo(() => {
    const q = String(hmInput || "").trim().toLowerCase();
    if (!q) return [];
    return (users || [])
      .filter((u) => {
        const name = String(u?.user_name || "").toLowerCase();
        const email = String(u?.user_email || "").toLowerCase();
        return name.includes(q) || email.includes(q);
      })
      .slice(0, 8);
  }, [users, hmInput]);

  const rmSuggestions = useMemo(() => {
    const q = String(rmInput || "").trim().toLowerCase();
    if (!q) return [];
    return (users || [])
      .filter((u) => {
        const name = String(u?.user_name || "").toLowerCase();
        const email = String(u?.user_email || "").toLowerCase();
        return name.includes(q) || email.includes(q);
      })
      .slice(0, 8);
  }, [users, rmInput]);

  const hiringManagerForApi = hmUserId || String(hmInput || "").trim();
  const reportingManagerForApi = rmUserId || String(rmInput || "").trim();

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
        end_date: endDate,
        // Azure AD (best-effort): if we find a matching user, send user_id.
        // If not found, we keep showing the typed text; backend may accept either name or id.
        hiring_manager_id: hiringManagerForApi || null,
        reporting_manager_id: reportingManagerForApi || null
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
        hiringManager: hiringManagerForApi,
        reportingManager: reportingManagerForApi,
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
      <Card title={isReadOnly ? "View Job" : "Create New Job"} icon={<Briefcase className="h-4 w-4" />}>
        <fieldset disabled={isReadOnly}>
        <div className="grid gap-3 md:grid-cols-2">
          <Input label="Job ID" value={isReadOnly ? (initialJob?.id || newId) : newId} onChange={() => {}} />
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
          <Select
            label="Department"
            value={dept}
            onChange={setDept}
            options={["Low", "High"]}
          />
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
          <div className="md:col-span-2 relative">
            <Input
              label="Hiring Manager (Azure AD)"
              value={hmInput}
              onChange={(v) => {
                setHmInput(v);
                setHmUserId("");
              }}
            />
            {hmSuggestions.length ? (
              <div className="absolute left-0 right-0 z-10 mt-1 overflow-hidden rounded-xl border bg-white shadow">
                {hmSuggestions.map((u) => (
                  <button
                    key={u.user_id}
                    type="button"
                    onClick={() => {
                      setHmInput(u.user_name || u.user_email || String(u.user_id));
                      setHmUserId(u.user_id);
                    }}
                    className="block w-full px-3 py-2 text-left hover:bg-gray-50"
                  >
                    <div className="text-sm font-semibold">
                      {u.user_name || u.user_email}
                    </div>
                    <div className="text-xs text-gray-500">
                      {u.user_email || u.user_id}
                    </div>
                  </button>
                ))}
              </div>
            ) : usersBusy ? (
              <div className="absolute left-0 right-0 z-10 mt-1 rounded-xl border bg-white px-3 py-2 text-xs text-gray-500 shadow">
                Searching…
              </div>
            ) : null}
          </div>

          <div className="md:col-span-2 relative">
            <Input
              label="Reporting Manager (Azure AD)"
              value={rmInput}
              onChange={(v) => {
                setRmInput(v);
                setRmUserId("");
              }}
            />
            {rmSuggestions.length ? (
              <div className="absolute left-0 right-0 z-10 mt-1 overflow-hidden rounded-xl border bg-white shadow">
                {rmSuggestions.map((u) => (
                  <button
                    key={u.user_id}
                    type="button"
                    onClick={() => {
                      setRmInput(u.user_name || u.user_email || String(u.user_id));
                      setRmUserId(u.user_id);
                    }}
                    className="block w-full px-3 py-2 text-left hover:bg-gray-50"
                  >
                    <div className="text-sm font-semibold">
                      {u.user_name || u.user_email}
                    </div>
                    <div className="text-xs text-gray-500">
                      {u.user_email || u.user_id}
                    </div>
                  </button>
                ))}
              </div>
            ) : usersBusy ? (
              <div className="absolute left-0 right-0 z-10 mt-1 rounded-xl border bg-white px-3 py-2 text-xs text-gray-500 shadow">
                Searching…
              </div>
            ) : null}
          </div>
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
        </fieldset>

        {!isReadOnly ? (
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
        ) : null}
        {actionNotice ? (
          <div className="mt-2 text-xs text-gray-500">{actionNotice}</div>
        ) : null}
      </Card>
    </div>
  );
}
