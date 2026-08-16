import { useEffect, useState, useMemo } from "react";
import { Edit2, Users, CheckCircle, Clock, BarChart3, Send, AlertCircle } from "lucide-react";
import { Button, Input, Select, StatusBadge, TextArea } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../utils/Routes";
import { listClients } from "../services/api/clients";
import { searchUsers } from "../services/api/users";
import { getJobClosureStatus } from "../services/api/autonomousJobs";

const getContactPersonName = (job) => {
  if (!job) return "-";
  // Use the contact_person_name field from API if available
  if (job.contact_person_name) return job.contact_person_name;
  // Fallback to the contactPerson ID if name not available
  return job.contactPerson || "-";
};

export default function JobDetails({ job, onSubmit, onGoApproval, onUpdate, mode = "view", candidates = [], defaultTab = "details" }) {
  const navigate = useNavigate();
  const [editingSection, setEditingSection] = useState(null);
  const [clientList, setClientList] = useState([]);
  const [availableContacts, setAvailableContacts] = useState([]);
  const [title, setTitle] = useState(job.title || "");
  const [positionType, setPositionType] = useState(job.positionType || "");
  const [priority, setPriority] = useState(job.priority || "");
  const [companyClient, setCompanyClient] = useState(job.companyClient || "");
  const [companyType, setCompanyType] = useState(job.companyType || "");
  const [contactPerson, setContactPerson] = useState(job.contactPerson || "");
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
  const [hiringManager, setHiringManager] = useState(job.hiring_manager_name || "");

  // Convert structured skills to edit format: "Skill:Years:Mandatory"
  const convertSkillsToEditFormat = (structuredSkills) => {
    if (!structuredSkills || !Array.isArray(structuredSkills)) {
      return "";
    }
    return structuredSkills
      .map(s => `${s.name}:${s.years}:${s.mandatory ? "yes" : "no"}`)
      .join(", ");
  };

  const [skillsText, setSkillsText] = useState(
    job.required_skills_canonical
      ? convertSkillsToEditFormat(job.required_skills_canonical)
      : (job.skills || []).join(", ")
  );
  const [hmOneLiner, setHmOneLiner] = useState(job.hiringManagerOneLiner || "");
  const [internalJD, setInternalJD] = useState(job.internalJD || job.jobDescription || "");
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [candidateQuery, setCandidateQuery] = useState("");
  const [candidateStageFilter, setCandidateStageFilter] = useState("All");
  const [departmentsList, setDepartmentsList] = useState([]);
  const [locationsList, setLocationsList] = useState([]);
  const [hiringManagers, setHiringManagers] = useState([]);
  const [jobClosureStatus, setJobClosureStatus] = useState(null);

  const CANDIDATE_STAGES = ["All", "Sourced", "Recruiter Screening", "L1 Interview", "Pre-Onboarding", "Hired", "Archived"];
  const EXPERIENCE_LEVELS = ["Entry Level (0-2 yrs)", "Mid-Level (2-5 yrs)", "Senior (5-10 yrs)", "Lead (10+ yrs)"];
  const PAY_AMOUNTS = ["50k", "75k", "100k", "125k", "150k", "175k", "200k", "250k", "300k+"];
  const LOCATIONS = ["USA", "India", "Canada", "UK", "Australia", "Remote"];
  const POSITIONS_OPTIONS = Array.from({ length: 10 }, (_, i) => i + 1).map(String);

  useEffect(() => {
    setActiveTab(defaultTab);
  }, [defaultTab]);

  useEffect(() => {
    const loadClients = async () => {
      try {
        const result = await listClients();
        setClientList(result?.clients || []);
      } catch (err) {
        console.warn("Could not load clients:", err?.message);
      }
    };
    loadClients();
  }, []);

  useEffect(() => {
    const loadContacts = async () => {
      try {
        const response = await searchUsers({ limit: 200 });
        setAvailableContacts(Array.isArray(response?.users) ? response.users : []);
      } catch (err) {
        console.warn("Could not load contact people:", err?.message);
        setAvailableContacts([]);
      }
    };
    loadContacts();
  }, []);

  useEffect(() => {
    const loadClosureStatus = async () => {
      try {
        if (job?.job_id || job?.jobID) {
          const status = await getJobClosureStatus(job.job_id || job.jobID);
          setJobClosureStatus(status);
        }
      } catch (err) {
        console.warn("Could not load closure status:", err?.message);
      }
    };
    loadClosureStatus();
  }, [job?.job_id, job?.jobID]);

  const jobMetrics = useMemo(() => {
    const submitted = candidates.filter(c => c.job_id === job.id)?.length || 0;
    const interviewed = candidates.filter(c => c.job_id === job.id && c.status?.toLowerCase() === 'interviewed')?.length || 0;
    const hired = candidates.filter(c => c.job_id === job.id && c.status?.toLowerCase() === 'hired')?.length || 0;
    return { submitted, interviewed, hired };
  }, [job.id, candidates]);

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
    setHiringManager(job.hiring_manager_name || "");
    setSkillsText(
      job.required_skills_canonical
        ? convertSkillsToEditFormat(job.required_skills_canonical)
        : (job.skills || []).join(", ")
    );
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
      {/* Two-Column Layout: Details + Metrics (header is in JobWorkspaceScreen) */}
      <div className={`grid gap-4 ${activeTab === "candidates" ? "lg:grid-cols-1" : "lg:grid-cols-3"}`}>
        {/* Main Content - 2/3 width, full width for candidates */}
        <div className={`${activeTab === "candidates" ? "lg:col-span-1" : "lg:col-span-2"}`}>
          {/* Tab navigation removed - JobWorkspaceScreen manages tabs */}

          {/* Details Tab */}
          {activeTab === "details" && (
            <div className="space-y-4">
      {/* Basic Information */}
      <CardBlock title="Basic Information" subtitle="Job title, position type, priority, and pay range">
        {editingSection === "basic" ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Job Title *" value={title} onChange={setTitle} />
            <Select label="Position Type" value={positionType} onChange={setPositionType}
              options={["Full time", "Contract"]} />
            <Select label="Priority" value={priority} onChange={setPriority}
              options={["Low", "High"]} />
            <Input label="Department" value={dept} onChange={setDept} />
            <Select label="Currency" value={payCurrency} onChange={(value) => {
              setPayCurrency(value);
              if (value === "INR") setPayFrequency("Annual");
            }} options={["USD", "INR"]} />
            <Select label="Pay Frequency" value={payFrequency} onChange={setPayFrequency}
              options={payCurrency === "USD" ? ["Hourly", "Annual"] : ["Annual"]} />
            <Input label={payFrequency === "Hourly" ? "Pay Amount (Hourly)" : "Pay Amount (Annual)"}
              value={payAmount} onChange={(value) => {
                setPayAmount(value);
                const normalized = value ? String(value).trim() : "";
                const next = normalized ? `${payCurrency} ${payFrequency} ${normalized}` : "";
                setPayRange(next);
              }} type="number" />
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
              <Info label="Pay Range" value={job.payRange} />
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

      {/* Job Closure Status */}
      {jobClosureStatus && (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-base font-semibold text-gray-900">Job Positions</h3>
              <p className="text-sm text-gray-500 mt-1">Hiring progress and job status</p>
            </div>
            {jobClosureStatus.eligible_for_closure && (
              <AlertCircle className="h-5 w-5 text-amber-500" />
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="rounded-lg bg-blue-50 p-3">
              <div className="text-2xl font-bold text-blue-600">{jobClosureStatus.positions_needed}</div>
              <div className="text-xs text-gray-600">Positions Needed</div>
            </div>
            <div className="rounded-lg bg-green-50 p-3">
              <div className="text-2xl font-bold text-green-600">{jobClosureStatus.hired_count}</div>
              <div className="text-xs text-gray-600">Hired</div>
            </div>
            <div className="rounded-lg bg-orange-50 p-3">
              <div className="text-2xl font-bold text-orange-600">{jobClosureStatus.remaining_positions}</div>
              <div className="text-xs text-gray-600">Remaining</div>
            </div>
            <div className="rounded-lg bg-purple-50 p-3">
              <div className="text-2xl font-bold text-purple-600">{jobClosureStatus.fill_percentage}%</div>
              <div className="text-xs text-gray-600">Filled</div>
            </div>
          </div>
          {jobClosureStatus.is_closed ? (
            <div className="mt-4 rounded-lg bg-gray-100 p-3 text-center">
              <StatusBadge status="closed" label="Job Closed" />
            </div>
          ) : jobClosureStatus.eligible_for_closure ? (
            <div className="mt-4">
              <p className="text-sm text-amber-700 mb-3">This job is now eligible for closure — all positions are filled!</p>
              <Button className="w-full" onClick={() => console.log("Close job")}>
                ✓ Close Job & Notify Remaining Candidates
              </Button>
            </div>
          ) : null}
        </div>
      )}

      {/* Company & Contact */}
      <CardBlock title="Company & Contact" subtitle="Client details and point of contact">
        {editingSection === "company" ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Select
              label="Company / Client *"
              value={companyClient}
              onChange={(value) => {
                setCompanyClient(value);
                const selectedClient = clientList.find(c => c.company_name === value);
                if (selectedClient?.line_type) {
                  setCompanyType(selectedClient.line_type);
                }
              }}
              options={[
                { label: "Select client", value: "", disabled: true },
                ...(clientList?.map((client) => ({
                  label: client?.company_name,
                  value: client?.company_name,
                })) || []),
              ]}
            />
            <Input label="Company Type (Line Type)" value={companyType} onChange={setCompanyType} disabled />
            <Select
              label="Contact Person"
              value={contactPerson}
              onChange={setContactPerson}
              options={[
                { label: "Select contact person", value: "", disabled: true },
                ...(availableContacts?.map((user) => ({
                  label: `${user?.user_name ?? ""} (${user?.user_email ?? ""})`,
                  value: user?.user_id ?? "",
                })) || []),
              ]}
            />
            <div className="md:col-span-2 flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("company")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="Company / Client" value={job.companyClient} />
              <Info label="Company Type (Line Type)" value={job.companyType} />
              <Info label="Contact Person" value={getContactPersonName(job)} />
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

      {/* Requirements & Skills */}
      <CardBlock title="Requirements & Skills" subtitle="Experience level, location, skills, and hiring manager">
        {editingSection === "skills" ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Select
              label="Experience Level"
              value={experienceLevel}
              onChange={setExperienceLevel}
              options={[
                { label: "Select experience level", value: "", disabled: true },
                ...EXPERIENCE_LEVELS.map((level) => ({ label: level, value: level }))
              ]}
            />
            <Select
              label="Location"
              value={location}
              onChange={setLocation}
              options={[
                { label: "Select location", value: "", disabled: true },
                ...LOCATIONS.map((loc) => ({ label: loc, value: loc }))
              ]}
            />
            <Input
              label="No. of Positions"
              value={noOfPositions}
              onChange={(val) => setNoOfPositions(Number(val))}
              type="number"
              min="1"
            />
            <Input label="Hiring Manager" value={hiringManager} onChange={setHiringManager} disabled placeholder="Set from Company & Contact section" />
            <div className="md:col-span-2">
              <Input
                label="Skills (Format: Skill:Years:Mandatory)"
                value={skillsText}
                onChange={setSkillsText}
                placeholder="Java:5:yes, Spring:3:yes, Docker:2:no"
                className="w-full"
              />
              <p className="text-xs text-gray-500 mt-1">Format: SkillName:Years:yes/no (e.g., Java:5:yes means 5 years of Java, mandatory)</p>
            </div>
            <div className="md:col-span-2 flex gap-2 justify-end">
              <Button variant="secondary" onClick={cancelSection}>Cancel</Button>
              <Button onClick={() => saveSection("skills")}>Save</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid gap-3 md:grid-cols-2 mb-4">
              <Info label="Experience Level" value={job.experienceLevel} />
              <Info label="Location" value={job.location} />
              <Info label="Hiring Manager" value={job.hiring_manager_name} />
              <Info label="No. of Positions" value={job.noOfPositions || "-"} />
            </div>
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-3">Required Skills</div>
              <div className="flex flex-wrap gap-2">
                {job.required_skills_canonical && Array.isArray(job.required_skills_canonical)
                  ? job.required_skills_canonical.map((s) => (
                    <span key={s.name} className={cx(pill, "border-gray-200 bg-gray-50 text-xs font-medium")}>
                      {s.name} · {s.years}yr{s.years !== 1 ? "s" : ""} {s.mandatory ? "✓ Required" : "○ Optional"}
                    </span>
                  ))
                  : job.skills?.map((s) => (
                    <span key={s} className={cx(pill, "border-gray-200 bg-gray-50")}>{s}</span>
                  ))}
              </div>
            </div>
            {mode !== "view" && (
              <Button variant="ghost" size="sm" onClick={() => setEditingSection("skills")}
                className="mt-4">
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

      {/* Action Buttons - Only for Draft Jobs */}
      {editingSection === null && (!job.jobStatus || job.jobStatus === "Draft") && (
        <div className="flex flex-wrap gap-2 justify-end">
          <Button variant="secondary" onClick={onGoApproval}>
            Send to hiring manager (approval)
          </Button>
          <Button onClick={onSubmit}>Submit to internal hiring team</Button>
        </div>
      )}

      {/* Edit Mode Actions - For Approved/Active Jobs */}
      {editingSection === null && job.jobStatus && job.jobStatus !== "Draft" && (
        <div className="flex flex-wrap gap-2 justify-end">
          <Button variant="secondary" disabled>
            Status: {job.jobStatus}
          </Button>
        </div>
      )}
            </div>
          )}

          {/* Candidates Tab */}
          {activeTab === "candidates" && (
            <div className="space-y-4">
              {/* Stage Filters */}
              <div className="flex gap-2 flex-wrap">
                {CANDIDATE_STAGES.map((stage) => (
                  <button
                    key={stage}
                    onClick={() => setCandidateStageFilter(stage)}
                    className={cx(
                      "px-3 py-2 rounded-lg text-sm font-medium transition",
                      candidateStageFilter === stage
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    {stage}
                  </button>
                ))}
              </div>

              {/* Search Box */}
              <div>
                <Input
                  label="Search candidates"
                  value={candidateQuery}
                  onChange={setCandidateQuery}
                  placeholder="Name, email, or phone..."
                />
              </div>

              {/* Candidates List */}
              <div className="space-y-3">
                {candidates
                  .filter(c => {
                    // Filter by job association: check multiple possible field names
                    const jobMatch = (c.job_id === job.id) ||
                                     (c.jobId === job.id) ||
                                     (c.opportunity_id === job.id) ||
                                     (c.opportunityId === job.id) ||
                                     (job.id && !job.id) || // fallback: if no job.id, show all (shouldn't happen)
                                     false; // strict: must be associated with this job

                    // If candidate is not associated with this job, exclude it
                    if (!jobMatch && job.id) return false;

                    const matchesQuery = !candidateQuery ||
                      (c.candidate_first_name || c.firstName || '').toLowerCase().includes(candidateQuery.toLowerCase()) ||
                      (c.candidate_last_name || c.lastName || '').toLowerCase().includes(candidateQuery.toLowerCase()) ||
                      (c.candidateEmail || c.email || '').toLowerCase().includes(candidateQuery.toLowerCase()) ||
                      (c.phone || '').includes(candidateQuery);

                    const matchesStage = candidateStageFilter === "All" ||
                      (c.status || 'Sourced').toLowerCase().includes(candidateStageFilter.toLowerCase());

                    return matchesQuery && matchesStage;
                  })
                  .length > 0 ? (
                  candidates
                    .filter(c => {
                      // Filter by job association
                      const jobMatch = (c.job_id === job.id) ||
                                       (c.jobId === job.id) ||
                                       (c.opportunity_id === job.id) ||
                                       (c.opportunityId === job.id) ||
                                       false;

                      if (!jobMatch && job.id) return false;

                      const matchesQuery = !candidateQuery ||
                        (c.candidate_first_name || c.firstName || '').toLowerCase().includes(candidateQuery.toLowerCase()) ||
                        (c.candidate_last_name || c.lastName || '').toLowerCase().includes(candidateQuery.toLowerCase()) ||
                        (c.candidateEmail || c.email || '').toLowerCase().includes(candidateQuery.toLowerCase()) ||
                        (c.phone || '').includes(candidateQuery);

                      const matchesStage = candidateStageFilter === "All" ||
                        (c.status || 'Sourced').toLowerCase().includes(candidateStageFilter.toLowerCase());

                      return matchesQuery && matchesStage;
                    })
                    .map((candidate) => (
                      <div key={candidate.id || candidate.candidateID} className="rounded-xl border border-gray-200 bg-white p-4 hover:shadow-sm transition">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1">
                            <h4 className="font-semibold text-gray-900">
                              {candidate.candidate_first_name || candidate.firstName || candidate.candidateFirstName || candidate.name} {candidate.candidate_last_name || candidate.lastName || candidate.candidateLastName || ''}
                            </h4>
                            <p className="text-sm text-gray-500">{candidate.candidateEmail || candidate.email}</p>
                            <p className="text-xs text-gray-400 mt-1">{candidate.phone}</p>
                            <div className="mt-2 flex gap-2 flex-wrap">
                              <span className={cx(pill, "text-xs")} style={{
                                backgroundColor: candidate.status?.toLowerCase() === 'hired' ? '#dcfce7' :
                                                 candidate.status?.toLowerCase().includes('interviewed') ? '#fef3c7' :
                                                 candidate.status?.toLowerCase().includes('screening') ? '#dbeafe' :
                                                 '#e0e7ff',
                                borderColor: candidate.status?.toLowerCase() === 'hired' ? '#86efac' :
                                             candidate.status?.toLowerCase().includes('interviewed') ? '#fcd34d' :
                                             candidate.status?.toLowerCase().includes('screening') ? '#7dd3fc' :
                                             '#a5b4fc',
                                color: candidate.status?.toLowerCase() === 'hired' ? '#166534' :
                                       candidate.status?.toLowerCase().includes('interviewed') ? '#92400e' :
                                       candidate.status?.toLowerCase().includes('screening') ? '#075985' :
                                       '#312e81'
                              }}>
                                {candidate.status || 'Sourced'}
                              </span>
                            </div>
                          </div>
                          <div className="flex gap-2 flex-col">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => navigate(`${ROUTES.CANDIDATES}/${candidate.candidateID || candidate.id}`, { state: { jobId: job.id } })}
                              className="whitespace-nowrap"
                            >
                              View
                            </Button>
                            {candidate.status?.toLowerCase() !== 'hired' && (
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => navigate(`${ROUTES.CANDIDATES}/${candidate.candidateID || candidate.id}?action=submit`, { state: { jobId: job.id } })}
                                className="whitespace-nowrap flex items-center gap-1"
                              >
                                <Send className="h-3 w-3" />
                                Submit
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                ) : (
                  <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
                    <Users className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600">
                      {candidates.length === 0
                        ? "No candidates submitted for this job yet"
                        : "No candidates match your search"}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Sidebar - Pipeline Activity & Timeline Summary (hidden on candidates tab) */}
        {activeTab !== "candidates" && <div className="lg:col-span-1">
          <div className="space-y-3 sticky top-4">
            {/* Pipeline Activity Metrics */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-base font-semibold text-gray-900 mb-4">Pipeline Activity</h3>
              <div className="space-y-3">
                <MetricCard
                  icon={Users}
                  label="Submitted"
                  value={jobMetrics.submitted}
                  color="bg-blue-50 text-blue-600"
                />
                <MetricCard
                  icon={Clock}
                  label="Interviewed"
                  value={jobMetrics.interviewed}
                  color="bg-yellow-50 text-yellow-600"
                />
                <MetricCard
                  icon={CheckCircle}
                  label="Hired"
                  value={jobMetrics.hired}
                  color="bg-green-50 text-green-600"
                />
              </div>
            </div>

            {/* Timeline Quick View */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-base font-semibold text-gray-900 mb-4">Timeline</h3>
              <div className="space-y-3">
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">Start Date</div>
                  <div className="text-sm font-medium text-gray-900 mt-1">{job.startDate || "-"}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">End Date</div>
                  <div className="text-sm font-medium text-gray-900 mt-1">{job.endDate || "-"}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">Status</div>
                  <div className="mt-1">
                    <StatusBadge status={job.status} />
                  </div>
                </div>
              </div>
            </div>

            {/* Hiring Team */}
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-base font-semibold text-gray-900 mb-4">Hiring Team</h3>
              <div className="space-y-4">
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">Recruiters</div>
                  <div className="text-sm font-medium text-gray-900 mt-1">{getContactPersonName(job)}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">Hiring Managers</div>
                  <div className="text-sm font-medium text-gray-900 mt-1">
                    {job.hiring_manager_name || job.hiringManager || "-"}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">Interview Panel</div>
                  <div className="text-sm font-medium text-gray-900 mt-1">-</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        }
      </div>
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

function MetricCard({ icon: Icon, label, value, color }) {
  return (
    <div className={cx("rounded-lg p-3", color)}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-semibold text-gray-600">{label}</div>
          <div className="text-2xl font-bold mt-1">{value}</div>
        </div>
        <Icon className="h-5 w-5 opacity-60" />
      </div>
    </div>
  );
}
