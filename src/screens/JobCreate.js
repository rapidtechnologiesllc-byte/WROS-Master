import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase } from "lucide-react";
import {
  generateJobDescription,
  createJob,
  generateJobWithAgent,
  generateJobComplete,
} from "../services/api/jobs";
import { Button, Card, Input, Select, TextArea } from "../components/ui";
import RateField from "../components/ui/RateField";
import { searchUsers } from "../services/api/users";
import { listClients, getBusinessUnitAssignments } from "../services/api/clients";
import { toast } from "react-toastify";
import {
  listBusinessUnits,
} from "../services/api/rbac";
import { Steps } from "antd";
import { ROUTES } from "../utils/Routes";

export default function JobCreate({
  onSave,
  mode = "create",
  initialJob = null,
}) {
  const navigate = useNavigate();
  const isReadOnly = mode === "view";
  const [title, setTitle] = useState("");
  const [positionType, setPositionType] = useState("");
  const [priority, setPriority] = useState("");
  const [companyClient, setCompanyClient] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [dept, setDept] = useState("Digital");
  const [location, setLocation] = useState("Remote");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [payRateType, setPayRateType] = useState("$/Year");
  const [startDate, setStartDate] = useState("");
  const [skills, setSkills] = useState("");
  const [jobStatus, setJobStatus] = useState("Draft");
  const [noOfPositions, setNoOfPositions] = useState(1);
  const [hmUserId, setHmUserId] = useState("");
  const [rmUserId, setRmUserId] = useState("");
  const [users, setUsers] = useState([]);
  const [usersBusy, setUsersBusy] = useState(false);
  const [hmOneLiner, setHmOneLiner] = useState("");
  const internalJdTemplate =
    "Overview:\n\nRoles & Responsibilities:\n- \n\nQualifications:\n- ";
  const [internalJD, setInternalJD] = useState(internalJdTemplate);
  const [externalJD, setExternalJD] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [businessUnitList, setBusinessUnitList] = useState([]);
  const [selectedBusinessUnit, setSelectedBusinessUnit] = useState("");
  const [clientList, setClientList] = useState([]);
  const [hrUsers, setHrUsers] = useState([]);
  const [resolvedBuHead, setResolvedBuHead] = useState(null);
  const [resolvedHrManager, setResolvedHrManager] = useState(null);
  const [hiringManagers, setHiringManagers] = useState([]);
  const [current, setCurrent] = useState(0);
  const [isInternalRole, setIsInternalRole] = useState(null); // null = auto-detect, true = internal, false = external
  const storedRole = localStorage.getItem("permission_role");

  // Ask Flash Modal state
  const [showAskFlash, setShowAskFlash] = useState(false);
  const [flashQuestions, setFlashQuestions] = useState([]);
  const [flashAnswers, setFlashAnswers] = useState({});
  const [isAnswering, setIsAnswering] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setUsersBusy(true);

      try {
        const [hrManagers, reportingManagers] = await Promise.all([
          searchUsers({
            user_role: "HR",
          }),
          searchUsers({
            permission_role: "Reporting Manager",
          }),
        ]);
        if (!isMounted) return;

        const mergedUsers = [
          ...(hrManagers?.users ?? []),
          ...(reportingManagers?.users ?? []),
        ];
        const uniqueUsers = Array.from(
          new Map(mergedUsers.map((user) => [user?.user_id, user])).values(),
        );
        setUsers(uniqueUsers);
      } catch (error) {
        console.error("Failed to load users:", error);
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
    const loadHrUsers = async () => {
      if (!selectedBusinessUnit) {
        setHrUsers([]);
        return;
      }

      const businessUnitName =
        businessUnitList?.find((bu) => bu?.id === Number(selectedBusinessUnit))
          ?.name ?? "";
      if (!businessUnitName) {
        setHrUsers([]);
        return;
      }
      try {
        const response = await searchUsers({
          user_role: "HR",
          business_unit: businessUnitName,
        });

        setHrUsers(Array.isArray(response?.users) ? response.users : []);
      } catch (error) {
        console.error("Failed to load HR users:", error);
        setHrUsers([]);
      }
    };
    loadHrUsers();
  }, [
    selectedBusinessUnit,
    businessUnitList,
  ]);

  // Selecting a client auto-resolves its Business Unit -- one less
  // manual step, matching the agentic-first "fewer clicks" mandate.
  // Only auto-selects when the user hasn't already picked a BU
  // themselves, so it never silently overrides a manual choice.
  useEffect(() => {
    if (!companyClient) return;
    const matchedClient = clientList?.find(
      (client) => client?.company_name === companyClient
    );
    if (matchedClient?.business_unit_id && !selectedBusinessUnit) {
      setSelectedBusinessUnit(String(matchedClient.business_unit_id));
    }
  }, [companyClient, clientList, selectedBusinessUnit]);

  // Once a Business Unit is resolved (from the client above, or picked
  // manually), auto-fill HR + surface BU Head -- the agent resolves
  // what it already knows rather than requiring a manual lookup.
  useEffect(() => {
    const resolveAssignments = async () => {
      if (!selectedBusinessUnit) {
        setResolvedBuHead(null);
        return;
      }
      try {
        const assignments = await getBusinessUnitAssignments(
          selectedBusinessUnit
        );
        setResolvedBuHead(assignments?.bu_head || null);
        setResolvedHrManager(assignments?.hr_manager || null);
        if (assignments?.hr_manager?.user_id && !contactPerson) {
          setContactPerson(assignments.hr_manager.user_id);
        }
      } catch (error) {
        console.error("Failed to resolve BU assignments:", error);
        setResolvedBuHead(null);
        setResolvedHrManager(null);
      }
    };
    resolveAssignments();
  }, [selectedBusinessUnit, contactPerson]);

  useEffect(() => {
    const loadHiringManagers = async () => {
      try {
        const response = await searchUsers({
          permission_role: "Hiring Manager",
        });

        setHiringManagers(Array.isArray(response?.users) ? response.users : []);
      } catch (error) {
        console.error("Failed to load Hiring Managers:", error);
        setHiringManagers([]);
      }
    };

    loadHiringManagers();
  }, []);

  useEffect(() => {
    if (!initialJob || mode !== "view") return;
    const parsePay = (value) => {
      const next = { rateType: "$/Year", amount: "" };
      if (!value) return next;
      // Parse "150 $/Year" format
      const match = String(value).trim().match(/^(\d+(?:\.\d+)?)\s*([\$₹]\/\w+)$/);
      if (match) {
        next.amount = match[1];
        next.rateType = match[2];
      }
      return next;
    };
    const parsedPay = parsePay(initialJob.salary_range || "");
    setTitle(initialJob.job_title || "");
    setPositionType(initialJob.company_type || "");
    setPriority(initialJob.priority || "");
    setCompanyClient(initialJob.company_name || "");
    setCompanyType(initialJob.company_type || "");
    setContactPerson(initialJob.contact_person || "");
    setDept(initialJob.dept || "");
    setLocation(initialJob.job_location || "");
    setExperienceLevel(initialJob.job_experience || "");
    setPayAmount(parsedPay.amount);
    setPayRateType(parsedPay.rateType);
    setStartDate(initialJob.startDate || "");
    setSkills((initialJob.skills || []).join(", "));
    setJobStatus(initialJob.jobStatus || initialJob.status || "Draft");
    setNoOfPositions(initialJob.noOfPositions || 1);
    setHmOneLiner(initialJob.hiringManagerOneLiner || "");
    setInternalJD(initialJob.internalJD || initialJob.jobDescription || "");
  }, [initialJob, mode]);

  useEffect(() => {
    const listingBusinessUnits = async () => {
      try {
        const listResult = await listBusinessUnits();
        setBusinessUnitList(listResult);
      } catch (err) {
        console.log(err);
      }
    };
    listingBusinessUnits();
  }, []);

  // Flagged by Avinash 2026-08-05: Company/Client was a free-form text
  // box, not backed by the real Client table -- meant a job could name
  // a "company" that isn't a real, tracked client at all. Loads the
  // real active client list (GET /clients, active_only default).
  useEffect(() => {
    const loadClients = async () => {
      try {
        const result = await listClients();
        setClientList(result?.clients || []);
      } catch (err) {
        console.error("Failed to load clients:", err);
        setClientList([]);
      }
    };
    loadClients();
  }, []);

  // Role Type (Internal/External) is no longer picked on this screen --
  // derived automatically from the selected client: blitzenx.com's own
  // website domain (or, failing that, "BlitzenX" in the company name,
  // for the rare client record with no website on file) means Internal;
  // everything else is External.
  useEffect(() => {
    if (!companyClient) return;
    const selectedClient = clientList?.find((c) => c?.company_name === companyClient);
    const domain = String(selectedClient?.website || "")
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/^www\./, "")
      .replace(/\/$/, "");
    const isInternal = domain
      ? domain === "blitzenx.com"
      : String(companyClient).toLowerCase().includes("blitzenx");
    setIsInternalRole(isInternal);
  }, [companyClient, clientList]);

  const clientOptions = [
    { label: "Select client", value: "", disabled: true },
    ...(clientList?.map((client) => ({
      label: client?.company_name,
      value: client?.company_name,
    })) || []),
  ];

  const buOptions = [
    { label: "Please select Business Unit", value: "", disabled: true },
    ...(businessUnitList?.map((bu) => ({
      label: bu?.name,
      value: bu?.id,
    })) || []),
  ];

  // The Pay Range "Amount" field is numeric-only, but the Ask Flash question
  // invites free-text answers like "100k-150k" or "$45-55/hr". Reduce that to
  // a single number (average of a range, "k" expanded) plus a best-guess rate
  // type, instead of silently leaving the field blank on anything non-numeric.
  const parsePayRangeAnswer = (value) => {
    const result = { amount: "", rateType: null };
    if (!value) return result;
    const text = String(value).trim();

    const numbers = [...text.matchAll(/(\d+(?:\.\d+)?)\s*(k)?/gi)]
      .map((m) => Number(m[1]) * (m[2] ? 1000 : 1))
      .filter((n) => !Number.isNaN(n) && n > 0);
    if (!numbers.length) return result;

    const amount = numbers.length > 1
      ? (numbers[0] + numbers[1]) / 2
      : numbers[0];
    result.amount = String(Math.round(amount));

    const isRupee = /₹|inr|rs\.?\b/i.test(text);
    const symbol = isRupee ? "₹" : "$";
    if (/\/\s*hr|hour/i.test(text)) result.rateType = `${symbol}/Hour`;
    else if (/\/\s*day|daily/i.test(text)) result.rateType = `${symbol}/Day`;
    else if (/\/\s*wk|week/i.test(text)) result.rateType = `${symbol}/Week`;
    else if (/\/\s*mo|month/i.test(text)) result.rateType = `${symbol}/Month`;
    else if (/\/\s*yr|year|annual/i.test(text)) result.rateType = `${symbol}/Year`;

    return result;
  };

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

  const generateInternalOverviewAndRolesFromApi = async () => {
    const oneLiner = hmOneLiner.trim();
    if (!oneLiner) {
      toast.error("Add a hiring manager 1-liner to generate roles.");
      return;
    }
    setIsGenerating(true);
    try {
      // Step 1: Call agent to get clarifying questions
      const { questions, job_title, estimated_experience } = await generateJobWithAgent(oneLiner);

      // Store questions and show modal
      setFlashQuestions(questions || []);
      setFlashAnswers({}); // Reset answers
      setShowAskFlash(true);

      toast.info("Answer the questions to generate the complete job details.");
    } catch (err) {
      toast.error(err?.message || "Failed to generate questions.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAnswerSubmit = async () => {
    // Validate all required questions are answered
    const missingAnswers = flashQuestions
      .filter(q => q.required)
      .filter(q => !flashAnswers[q.field])
      .map(q => q.question);

    if (missingAnswers.length > 0) {
      toast.error(`Please answer: ${missingAnswers.join(", ")}`);
      return;
    }

    setIsAnswering(true);
    try {
      // Step 2: Call agent with answers to generate complete job
      const data = await generateJobComplete(hmOneLiner.trim(), flashAnswers);

      // Auto-populate all fields from agent response
      if (data?.job_title) setTitle(data.job_title);
      if (data?.position_type) setPositionType(data.position_type);
      if (data?.pay_range) {
        const parsedPay = parsePayRangeAnswer(data.pay_range);
        if (parsedPay.amount) setPayAmount(parsedPay.amount);
        if (parsedPay.rateType) setPayRateType(parsedPay.rateType);
      }
      if (data?.job_open_date) setStartDate(data.job_open_date);
      if (data?.job_location) setLocation(data.job_location);
      if (data?.role_type) {
        setIsInternalRole(!/external/i.test(data.role_type));
      }
      if (data?.client_name) setCompanyClient(data.client_name);

      if (data?.job_experience) {
        const expMatch = String(data.job_experience).match(/(\d+)/);
        if (expMatch) {
          const years = Math.min(20, Math.max(1, Number(expMatch[1])));
          setExperienceLevel(years);
        }
      }

      if (data?.generated_job_description) {
        setInternalJD(data.generated_job_description);
      }

      if (Array.isArray(data?.job_skills) && data.job_skills.length) {
        setSkills(data.job_skills.join(", "));
      }

      setShowAskFlash(false);
      toast.success("Job details generated and auto-populated!");
    } catch (err) {
      toast.error(err?.message || "Failed to generate complete job.");
    } finally {
      setIsAnswering(false);
    }
  };

  const handleCreateJob = async () => {
    setIsSaving(true);
    const required = [
      { label: "Job Title", value: title },
      { label: "Internal Job Description", value: internalJD },
      { label: "Experience Level", value: experienceLevel },
      { label: "Location", value: location },
      { label: "Company / Client", value: companyClient },
      { label: "Job Status", value: jobStatus },
      { label: "No. of Positions", value: noOfPositions },
      { label: "Start Date", value: startDate },
      { label: "Pay Rate", value: payAmount },
    ];
    const missing = required
      .filter(
        ({ value }) => String(value ?? "").trim() === "" || Number(value) === 0,
      )
      .map(({ label }) => label);
    if (missing.length) {
      const err = `Please fill required fields: ${missing.join(", ")}.`;
      toast.error(err);
      setIsSaving(false);
      return;
    }
    if (!hmUserId?.trim()) {
      toast.error("Please select a Hiring Manager.");
      setIsSaving(false);
      return;
    }
    try {
      // Format: "150 $/Year" for easy comparison with Expected Salary
      const payRangeString = payAmount ? `${payAmount} ${payRateType}` : null;
      const payload = {
        job_title: title?.trim(),
        job_description: internalJD?.trim(),
        job_skills: skills?.trim(),
        job_experience: String(experienceLevel ?? "").trim(),
        job_location: location?.trim(),
        company_type: companyType?.trim(),
        company_name: companyClient?.trim(),
        contact_person: contactPerson || null,
        job_status: normalizeJobStatusForApi(jobStatus),
        no_of_positions: Number(noOfPositions || 0),
        start_date: startDate,
        hiring_manager_id: hmUserId || null,
        reporting_manager_id: rmUserId || null,
        salary_range: payRangeString,
        is_internal_role: isInternalRole, // true = internal (BU Head), false = external (Partner)
      };
      const data = await createJob(payload);
      const createdId = data?.job_id;
      toast.success(`Created job ${title}`);
      navigate(ROUTES.JOBS);
    } catch (err) {
      console.error("Job creation error:", err);
      const errorMsg = err?.message || err?.response?.data?.detail || "Failed to create job.";
      toast.error(errorMsg);
    } finally {
      setIsSaving(false);
    }
  };

  const next = () => {
    if (current < 1) {
      setCurrent(current + 1);
    }
  };

  const prev = () => {
    if (current > 0) {
      setCurrent(current - 1);
    }
  };

  const renderFormContent = () => {
    switch (current) {
      case 0:
        return (
          <fieldset disabled={isReadOnly}>
            <div className="md:col-span-2 mt-2">
              <TextArea
                label="Hiring Manager 1-Liner + Skills"
                value={hmOneLiner}
                onChange={setHmOneLiner}
                rows={3}
                placeholder="Include job_title, job_experience, job_location, and comma-separated skills to generate JD (e.g., React, Node.js, AWS)"
              />
            </div>
            <div className="md:col-span-2">
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={generateInternalOverviewAndRolesFromApi}
                  disabled={isGenerating || !hmOneLiner.trim()}
                >
                  {isGenerating ? "Generating..." : "Generate Overview + Roles"}
                </Button>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
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
                label="Company / Client *"
                value={companyClient}
                onChange={(value) => {
                  setCompanyClient(value);
                  // Auto-populate companyType from selected client's line_type
                  const selectedClient = clientList.find(c => c.company_name === value);
                  if (selectedClient?.line_type) {
                    setCompanyType(selectedClient.line_type);
                  }
                }}
                options={clientOptions}
              />
              <Select
                label="Business Unit"
                value={selectedBusinessUnit}
                onChange={(value) => setSelectedBusinessUnit(value)}
                options={buOptions}
              />
              <Input
                label="Location *"
                value={location}
                onChange={setLocation}
              />
              <Select
                label="Job Status *"
                value={jobStatus}
                onChange={setJobStatus}
                options={["Draft", "Open", "Public", "Submitted", "Closed"]}
                disabled={true}
              />
              <Input
                label="No. of Positions *"
                value={String(noOfPositions)}
                onChange={(value) => setNoOfPositions(Number(value || 0))}
                type="number"
              />
              <Select
                label="Experience Level *"
                value={experienceLevel}
                onChange={setExperienceLevel}
                options={Array.from({ length: 20 }, (_, i) => i + 1)}
              />
              <Select
                label="Hiring Manager (Azure AD) *"
                value={hmUserId}
                onChange={setHmUserId}
                options={[
                  {
                    label: "Select Hiring Manager",
                    value: "",
                  },
                  ...(hiringManagers?.map((user) => ({
                    label: `${user?.user_name ?? ""} (${user?.user_email ?? ""})`,
                    value: user?.user_id ?? "",
                  })) ?? []),
                ]}
              />
            </div>

            {/* Job Timeline & Compensation */}
            <div className="grid gap-3 md:grid-cols-2 mt-4">
              <RateField
                label="Pay Rate *"
                value={payAmount}
                rateType={payRateType}
                onValueChange={setPayAmount}
                onRateTypeChange={setPayRateType}
                required={true}
                rateTypeOptions={["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year", "₹/Hour", "₹/Day", "₹/Week", "₹/Month", "₹/Year"]}
              />
              <Input
                label="Job Open Date (Posted) *"
                value={startDate}
                onChange={setStartDate}
                type="date"
                placeholder="When to post the job"
              />
            </div>
          </fieldset>
        );
      case 1:
        return (
          <>
            <div className="mt-2 md:col-span-2">
              <TextArea
                label="Internal Job Description *"
                value={internalJD}
                onChange={setInternalJD}
                rows={6}
                placeholder="Editable; can be generated from AI"
              />
            </div>
          </>
        );
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title={isReadOnly ? "View Job" : "Create New Job"}
        icon={<Briefcase className="h-4 w-4" />}
      >
        <div>
          <Steps
            current={current}
            items={[{ title: "Step 1" }, { title: "Step 2" }]}
          />
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          {renderFormContent()}
        </div>

        {current === 1 ? (
          <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
            <Button onClick={handleCreateJob} disabled={isSaving}>
              {isSaving
                ? "Creating..."
                : storedRole === "BU Head" || storedRole === "Super User"
                  ? "Create Job"
                  : "Submit For Approval"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setCurrent((prev) => prev - 1)}
            >
              Back
            </Button>
          </div>
        ) : (
          <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => setCurrent((prev) => prev + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Ask Flash Modal */}
      {showAskFlash && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-4">📋 Job Details - Quick Questions</h2>
            <p className="text-sm text-gray-600 mb-6">
              Answer these questions to help us generate the complete job posting:
            </p>

            <div className="space-y-4">
              {flashQuestions
                .filter(
                  (q) =>
                    q.field !== "client_name" ||
                    /external/i.test(flashAnswers.role_type || "")
                )
                .map((question) => (
                <div key={question.field}>
                  <label className="block text-sm font-medium mb-2">
                    {question.question}
                    {question.required && <span className="text-red-500">*</span>}
                  </label>

                  {question.field === "client_name" ? (
                    <select
                      value={flashAnswers[question.field] || ""}
                      onChange={(e) =>
                        setFlashAnswers({
                          ...flashAnswers,
                          [question.field]: e.target.value
                        })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {clientOptions.map((option) => (
                        <option key={option.value} value={option.value} disabled={option.disabled}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  ) : question.type === "select" ? (
                    <select
                      value={flashAnswers[question.field] || ""}
                      onChange={(e) =>
                        setFlashAnswers({
                          ...flashAnswers,
                          [question.field]: e.target.value
                        })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select an option...</option>
                      {question.options?.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  ) : question.type === "date" ? (
                    <input
                      type="date"
                      value={flashAnswers[question.field] || ""}
                      onChange={(e) =>
                        setFlashAnswers({
                          ...flashAnswers,
                          [question.field]: e.target.value
                        })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  ) : question.type === "pay_rate" ? (
                    (() => {
                      // Matches the same "<amount> <symbol>/<unit>" format the
                      // real Pay Rate field on the form uses (parsePay above),
                      // so the answer needs no extra parsing on submit.
                      const current = flashAnswers[question.field] || "";
                      const match = current.match(/^(\d+(?:\.\d+)?)?\s*([\$₹]\/\w+)?$/);
                      const currentAmount = match?.[1] || "";
                      const currentRateType = match?.[2] || "$/Year";
                      const updateComposite = (amount, rateType) => {
                        const composite = amount ? `${amount} ${rateType}` : "";
                        setFlashAnswers({ ...flashAnswers, [question.field]: composite });
                      };
                      return (
                        <div className="flex gap-2">
                          <input
                            type="number"
                            value={currentAmount}
                            onChange={(e) => updateComposite(e.target.value, currentRateType)}
                            placeholder="Amount"
                            className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <select
                            value={currentRateType}
                            onChange={(e) => updateComposite(currentAmount, e.target.value)}
                            className="px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            {["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year", "₹/Hour", "₹/Day", "₹/Week", "₹/Month", "₹/Year"].map((rt) => (
                              <option key={rt} value={rt}>{rt}</option>
                            ))}
                          </select>
                        </div>
                      );
                    })()
                  ) : (
                    <input
                      type="text"
                      value={flashAnswers[question.field] || ""}
                      onChange={(e) =>
                        setFlashAnswers({
                          ...flashAnswers,
                          [question.field]: e.target.value
                        })
                      }
                      placeholder="Enter your answer..."
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>
              ))}
            </div>

            <div className="mt-6 flex gap-2 justify-end">
              <Button
                variant="secondary"
                onClick={() => setShowAskFlash(false)}
                disabled={isAnswering}
              >
                Cancel
              </Button>
              <Button
                onClick={handleAnswerSubmit}
                disabled={isAnswering}
              >
                {isAnswering ? "Generating..." : "Generate Job"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
