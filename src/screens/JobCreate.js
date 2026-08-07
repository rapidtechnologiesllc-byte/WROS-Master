import { useEffect, useState } from "react";
import { Briefcase } from "lucide-react";
import { generateJobDescription, createJob } from "../services/api/jobs";
import { Button, Card, Input, Select, TextArea } from "../components/ui";
import { searchUsers } from "../services/api/users";
import { listClients, getBusinessUnitAssignments } from "../services/api/clients";
import { toast } from "react-toastify";
import {
  listBusinessUnits,
  getDepartmentsByBusinessUnit,
} from "../services/api/rbac";
import { Steps } from "antd";
import { ROUTES } from "../utils/Routes";

export default function JobCreate({
  onSave,
  mode = "create",
  initialJob = null,
}) {
  const isReadOnly = mode === "view";
  const [title, setTitle] = useState("");
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
  const [payCurrency, setPayCurrency] = useState("INR");
  const [payFrequency, setPayFrequency] = useState("Annual");
  const [payAmount, setPayAmount] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
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
  const [departmentListState, setDepartmentList] = useState([]);
  const [selectedDept, setSelectedDept] = useState("");
  const [businessUnitList, setBusinessUnitList] = useState([]);
  const [selectedBusinessUnit, setSelectedBusinessUnit] = useState("");
  const [clientList, setClientList] = useState([]);
  const [hrUsers, setHrUsers] = useState([]);
  const [resolvedBuHead, setResolvedBuHead] = useState(null);
  const [resolvedHrManager, setResolvedHrManager] = useState(null);
  const [hiringManagers, setHiringManagers] = useState([]);
  const [current, setCurrent] = useState(0);
  const storedRole = localStorage.getItem("permission_role");

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
    const loadDepartments = async () => {
      if (!selectedBusinessUnit) {
        setDepartmentList([]);
        setSelectedDept("");
        return;
      }
      try {
        const departments =
          await getDepartmentsByBusinessUnit(selectedBusinessUnit);
        setDepartmentList(departments);
        setSelectedDept("");
      } catch (err) {
        console.error("Failed to load departments:", err);
        setDepartmentList([]);
      }
    };
    loadDepartments();
  }, [selectedBusinessUnit]);

  useEffect(() => {
    const loadHrUsers = async () => {
      if (!selectedBusinessUnit || !selectedDept) {
        setHrUsers([]);
        return;
      }

      const businessUnitName =
        businessUnitList?.find((bu) => bu?.id === Number(selectedBusinessUnit))
          ?.name ?? "";
      const departmentName =
        departmentListState?.find((dept) => dept?.id === Number(selectedDept))
          ?.name ?? "";
      if (!businessUnitName || !departmentName) {
        setHrUsers([]);
        return;
      }
      try {
        const response = await searchUsers({
          user_role: "HR",
          business_unit: businessUnitName,
          department: departmentName,
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
    selectedDept,
    businessUnitList,
    departmentListState,
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
      const next = { currency: "USD", frequency: "Annual", amount: "" };
      if (!value) return next;
      const parts = String(value).trim().split(/\s+/);
      if (parts[0] === "USD" || parts[0] === "INR") next.currency = parts[0];
      if (parts[1] === "Hourly" || parts[1] === "Annual")
        next.frequency = parts[1];
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

  const clientOptions = [
    { label: "Select client", value: "", disabled: true },
    ...(clientList?.map((client) => ({
      label: client?.company_name,
      value: client?.company_name,
    })) || []),
  ];

  const deptOptions = [
    { label: "Please select department", value: "", disabled: true },
    ...(departmentListState?.map((dept) => ({
      label: dept?.name,
      value: dept?.id,
    })) || []),
  ];

  const buOptions = [
    { label: "Please select Business Unit", value: "", disabled: true },
    ...(businessUnitList?.map((bu) => ({
      label: bu?.name,
      value: bu?.id,
    })) || []),
  ];

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
      const data = await generateJobDescription({
        job_title: title,
        job_description: oneLiner,
        job_experience: experienceLevel,
        job_location: location,
      });
      const generated = (data?.generated_job_description || "").trim();
      if (!generated) {
        throw new Error("AI did not return a job description.");
      }
      setInternalJD(generated);
      if (Array.isArray(data?.job_skills) && data.job_skills.length) {
        setSkills(data.job_skills.join(", "));
      }
      toast.success("Overview + Roles generated.");
    } catch (err) {
      toast.error(err?.message || "Failed to generate job description.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreateJob = async () => {
    setIsSaving(true);
    const required = [
      { label: "Job Title", value: title },
      { label: "Internal Job Description", value: internalJD },
      { label: "Skills", value: skills },
      { label: "Experience Level", value: experienceLevel },
      { label: "Location", value: location },
      { label: "Company / Client", value: companyClient },
      { label: "HR", value: contactPerson },
      { label: "Job Status", value: jobStatus },
      { label: "No. of Positions", value: noOfPositions },
      { label: "Start Date", value: startDate },
      { label: "End Date", value: endDate },
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
    if (!contactPerson?.trim()) {
      toast.error("Please select an HR.");
      setIsSaving(false);
      return;
    }
    try {
      const payload = {
        job_title: title?.trim(),
        job_description: internalJD?.trim(),
        job_skills: skills?.trim(),
        job_experience: experienceLevel?.trim(),
        job_location: location?.trim(),
        company_type: companyType?.trim(),
        company_name: companyClient?.trim(),
        contact_person: contactPerson || null,
        job_status: normalizeJobStatusForApi(jobStatus),
        no_of_positions: Number(noOfPositions || 0),
        start_date: startDate,
        end_date: endDate,
        hiring_manager_id: hmUserId || null,
        reporting_manager_id: rmUserId || null,
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
                label="Hiring Manager 1-Liner "
                value={hmOneLiner}
                onChange={setHmOneLiner}
                rows={2}
                placeholder="Include job_title, job_experience, job_location to generate JD"
              />
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
                label="HR * (auto-assigned from Business Unit, override if needed)"
                value={contactPerson}
                onChange={setContactPerson}
                options={[
                  { label: "Select HR", value: "" },
                  ...(resolvedHrManager?.user_id
                    ? [{
                        label: `${resolvedHrManager.name} (${resolvedHrManager.email})`,
                        value: resolvedHrManager.user_id,
                      }]
                    : []),
                  ...(hrUsers
                    ?.filter((user) => user?.user_id !== resolvedHrManager?.user_id)
                    .map((user) => ({
                      label: `${user?.user_name ?? ""} (${user?.user_email ?? ""})`,
                      value: user?.user_id ?? "",
                    })) ?? []),
                ]}
              />
              <Input
                label="BU Head (auto-resolved, informational)"
                value={
                  resolvedBuHead
                    ? `${resolvedBuHead.name} (${resolvedBuHead.email})`
                    : selectedBusinessUnit
                    ? "Not assigned for this BU"
                    : ""
                }
                onChange={() => {}}
                disabled={true}
              />
              <Select
                label="Company / Client *"
                value={companyClient}
                onChange={setCompanyClient}
                options={clientOptions}
              />
              <Select
                label="Business Unit"
                value={selectedBusinessUnit}
                onChange={(value) => setSelectedBusinessUnit(value)}
                options={buOptions}
              />
              <Select
                label="Department"
                value={selectedDept}
                onChange={(value) => setSelectedDept(value)}
                options={deptOptions}
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
              <div className="md:col-span-2">
                <div className="mb-1 text-xs font-semibold text-gray-700">
                  Pay Range
                </div>
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
                    options={["INR", "USD"]}
                  />
                  <Select
                    label="Frequency"
                    value={payFrequency}
                    onChange={setPayFrequency}
                    options={["Hourly", "Weekly", "Annual"]}
                  />
                  <Input
                    label={
                      payFrequency === "Hourly"
                        ? "Amount (Hourly)"
                        : payFrequency === "Weekly"
                          ? "Amount (Weekly)"
                          : "Amount (Annual)"
                    }
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
              <Input
                label="End Date *"
                value={endDate}
                onChange={setEndDate}
                type="date"
              />
            </div>
          </fieldset>
        );
      case 1:
        return (
          <>
            <div className="md:col-span-2 mt-2">
              <Input
                label="Skills (comma separated) *"
                value={skills}
                onChange={setSkills}
              />
            </div>
            <div className="md:col-span-2">
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
    </div>
  );
}
