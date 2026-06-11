// Job creation form (simple flow).
import { useEffect, useState } from "react";
import { Briefcase } from "lucide-react";
import { generateJobDescription, createJob } from "../services/api/jobs";
import { Button, Card, Input, Select, TextArea } from "../components/ui";
import { searchUsers } from "../services/api/users";
import { toast } from "react-toastify";
import {
  listBusinessUnits,
  getDepartmentsByBusinessUnit,
} from "../services/api/rbac";

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
  const [payCurrency, setPayCurrency] = useState("USD");
  const [payFrequency, setPayFrequency] = useState("Annual");
  const [payAmount, setPayAmount] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [skills, setSkills] = useState("React, TypeScript");
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
  const [hrUsers, setHrUsers] = useState([]);
  const [hiringManagers, setHiringManagers] = useState([]);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setUsersBusy(true);

      try {
        const [hrManagers, reportingManagers] = await Promise.all([
          searchUsers({
            // permission_role: "HR Manager",
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
          // permission_role: "HR Manager",
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
  useEffect(() => {
    const loadHiringManagers = async () => {
      if (!selectedBusinessUnit || !selectedDept) {
        setHiringManagers([]);
        return;
      }
      const businessUnitName =
        businessUnitList?.find((bu) => bu?.id === Number(selectedBusinessUnit))
          ?.name ?? "";
      const departmentName =
        departmentListState?.find((dept) => dept?.id === Number(selectedDept))
          ?.name ?? "";
      if (!businessUnitName || !departmentName) {
        setHiringManagers([]);
        return;
      }
      try {
        const response = await searchUsers({
          permission_role: "Hiring Manager",
          business_unit: businessUnitName,
          department: departmentName,
        });
        setHiringManagers(Array.isArray(response?.users) ? response.users : []);
      } catch (error) {
        console.error("Failed to load Hiring Managers:", error);
        setHiringManagers([]);
      }
    };

    loadHiringManagers();
  }, [
    selectedBusinessUnit,
    selectedDept,
    businessUnitList,
    departmentListState,
  ]);

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
    const required = [
      { label: "Job Title", value: title },
      { label: "Hiring Manager 1-Liner", value: hmOneLiner },
      { label: "Internal Job Description", value: internalJD },
      { label: "Skills", value: skills },
      { label: "Experience Level", value: experienceLevel },
      { label: "Location", value: location },
      { label: "Company Type", value: companyType },
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
      toast.error(`Please fill required fields: ${missing.join(", ")}.`);
      return;
    }
    if (!hmUserId?.trim()) {
      toast.error("Please select a Hiring Manager.");
      return;
    }
    if (!contactPerson?.trim()) {
      toast.error("Please select an HR.");
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
        hiringManager:
          users.find((user) => user?.user_id === hmUserId)?.user_name ?? "",
        reportingManager:
          users.find((user) => user?.user_id === rmUserId)?.user_name ?? "",
        hiringManagerOneLiner: hmOneLiner,
        internalJD,
        externalJD,
        status: jobStatus || "Draft",
      });
      toast.success("Job created successfully.");
    } catch (err) {
      toast.error(err?.message || "Failed to create job.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title={isReadOnly ? "View Job" : "Create New Job"}
        icon={<Briefcase className="h-4 w-4" />}
      >
        <fieldset disabled={isReadOnly}>
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
              label="HR *"
              value={contactPerson}
              onChange={setContactPerson}
              options={[
                {
                  label: "Select HR",
                  value: "",
                },
                ...(hrUsers?.map((user) => ({
                  label: `${user?.user_name ?? ""} (${user?.user_email ?? ""})`,
                  value: user?.user_id ?? "",
                })) ?? []),
              ]}
            />
            <Input
              label="Company / Client *"
              value={companyClient}
              onChange={setCompanyClient}
            />
            <Input
              label="Company Type *"
              value={companyType}
              onChange={setCompanyType}
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
                  options={["USD", "INR"]}
                />
                <Select
                  label="Frequency"
                  value={payFrequency}
                  onChange={setPayFrequency}
                  options={
                    payCurrency === "USD" ? ["Hourly", "Annual"] : ["Annual"]
                  }
                />
                <Input
                  label={
                    payFrequency === "Hourly"
                      ? "Amount (Hourly)"
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
            <Select
              label="Reporting Manager (Azure AD)"
              value={rmUserId}
              onChange={setRmUserId}
              options={[
                {
                  label: "Select Reporting Manager",
                  value: "",
                },
                ...users.map((user) => ({
                  label: `${user?.user_name ?? ""} (${user?.user_email ?? ""})`,
                  value: user?.user_id ?? "",
                })),
              ]}
            />
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
              <Button
                variant="secondary"
                onClick={() => toast.success("Draft saved (mock).")}
              >
                Save Draft
              </Button>
              <Button
                onClick={() => toast.success("Submitted for approval (mock).")}
              >
                Submit for Approval
              </Button>
            </div>
            <Button onClick={handleCreateJob} disabled={isSaving}>
              {isSaving ? "Creating..." : "Create Job"}
            </Button>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
