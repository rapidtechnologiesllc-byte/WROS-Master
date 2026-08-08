import { useEffect, useState, useMemo } from "react";
import { Briefcase, Edit2, Users, CheckCircle, Clock, BarChart3 } from "lucide-react";
import { Button, Input, Select, StatusBadge, TextArea } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";

export default function JobDetails({ job, onSubmit, onGoApproval, onUpdate, mode = "view", candidates = [] }) {
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
  const [activeTab, setActiveTab] = useState("details");
  const [candidateQuery, setCandidateQuery] = useState("");
  const [candidateStageFilter, setCandidateStageFilter] = useState("All");

  const CANDIDATE_STAGES = ["All", "Sourced", "Recruiter Screening", "L1 Interview", "Pre-Onboarding", "Hired", "Archived"];

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
      {/* Header with Status & Metrics */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Briefcase className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
            <p className="text-sm text-gray-500">{job.dept} • {job.location}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={job.status} />
          {job.noOfPositions && (
            <div className="px-3 py-1 bg-gray-100 rounded-full text-sm font-medium text-gray-700">
              {job.noOfPositions} Opening{job.noOfPositions > 1 ? 's' : ''}
            </div>
          )}
        </div>
      </div>

      {/* Two-Column Layout: Details + Metrics */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Main Content - 2/3 width */}
        <div className="lg:col-span-2">
          {/* Tab Navigation */}
          <div className="flex gap-0 border-b border-gray-200 mb-4">
            <button
              onClick={() => setActiveTab("details")}
              className={cx(
                "px-4 py-3 text-sm font-semibold border-b-2 transition",
                activeTab === "details"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              )}
            >
              Job Details
            </button>
            <button
              onClick={() => setActiveTab("candidates")}
              className={cx(
                "px-4 py-3 text-sm font-semibold border-b-2 transition flex items-center gap-2",
                activeTab === "candidates"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              )}
            >
              <Users className="h-4 w-4" />
              Candidates ({jobMetrics.submitted})
            </button>
          </div>

          {/* Details Tab */}
          {activeTab === "details" && (
            <div className="space-y-4">
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

        {/* Right Sidebar - Pipeline Activity & Timeline Summary */}
        <div className="lg:col-span-1">
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
                  <div className="text-sm font-medium text-gray-900 mt-1">{job.contactPerson || "-"}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">Hiring Managers</div>
                  <div className="text-sm font-medium text-gray-900 mt-1">{job.hiringManager || "-"}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase">Interview Panel</div>
                  <div className="text-sm font-medium text-gray-900 mt-1">-</div>
                </div>
              </div>
            </div>
          </div>
        </div>
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
