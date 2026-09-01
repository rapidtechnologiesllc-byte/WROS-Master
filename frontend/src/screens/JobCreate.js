import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase } from "lucide-react";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import {
  generateJobDescription,
  createJob,
  generateJobWithAgent,
  generateJobComplete,
  updateJob,
} from "../services/api/jobs";
import { Button, Card, Input, Select, TextArea, LocationCascadeSelect, formatLocation, parseLocation } from "../components/ui";
import RateField from "../components/ui/RateField";
import { searchUsers } from "../services/api/users";
import { listClients, getBusinessUnitAssignments } from "../services/api/clients";
import { toast } from "react-toastify";
import ScreenErrorDisplay from "../components/ScreenErrorDisplay";
import {
  listBusinessUnits,
} from "../services/api/rbac";
import { createTask } from "../services/api/tasks";
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
  const canCreateJobDirectly = hasPermission("jobs", "create");

  // Ask Flash Modal state
  const [showAskFlash, setShowAskFlash] = useState(false);
  const [flashQuestions, setFlashQuestions] = useState([]);
  const [flashAnswers, setFlashAnswers] = useState({});
  const [isAnswering, setIsAnswering] = useState(false);
  const [draftJobId, setDraftJobId] = useState(null);
  const [autoSaveStatus, setAutoSaveStatus] = useState(""); // "saving", "saved", or ""
  const [locationValue, setLocationValue] = useState({
    countryCode: "",
    stateCode: "",
    city: "",
  });
  const [isJobLocationRemote, setIsJobLocationRemote] = useState(false);
  const [screenError, setScreenError] = useState(null);
  const [showSkillsModal, setShowSkillsModal] = useState(false);
  const [selectedSkills, setSelectedSkills] = useState([]);

  // Sync skills string to structured format when needed
  useEffect(() => {
    if (initialJob?.skills && mode === "view" && initialJob.skills.length > 0) {
      const structuredSkills = initialJob.skills.map(skill => ({
        name: typeof skill === 'string' ? skill : skill.name,
        yearsOfExperience: typeof skill === 'object' ? skill.yearsOfExperience : null,
        isPrimary: typeof skill === 'object' ? skill.isPrimary : false,
      }));
      setSelectedSkills(structuredSkills);
    }
  }, [initialJob, mode]);

  // Auto-save draft effect
  useEffect(() => {
    if (!draftJobId || mode === "view" || isReadOnly) return;

    const saveTimer = setTimeout(async () => {
      try {
        setAutoSaveStatus("saving");

        // Build location string from cascade select
        let locationLabel = "";
        if (isJobLocationRemote) {
          const countryName = locationValue?.countryCode ?
            (require("country-state-city").Country.getCountryByCode(locationValue.countryCode)?.name || locationValue.countryCode)
            : "Global";
          locationLabel = `Remote - ${countryName}`;
        } else {
          locationLabel = formatLocation(locationValue) || "Location TBD";
        }

        const payload = {
          job_title: title?.trim() || "Draft Job",
          job_description: internalJD?.trim(),
          job_skills: selectedSkills.length > 0 ? selectedSkills.map(s => s.name).join(", ") : skills?.trim(),
          job_experience: String(experienceLevel ?? "1").trim(),
          job_location: locationLabel,
          job_location_country: locationValue?.countryCode || "",
          job_location_state: locationValue?.stateCode || "",
          job_location_city: locationValue?.city || "",
          is_remote: isJobLocationRemote,
          company_type: companyType?.trim() || "",
          company_name: companyClient?.trim() || "",
          contact_person: contactPerson || null,
          job_status: "draft",
          no_of_positions: Number(noOfPositions || 1),
          start_date: startDate || new Date().toISOString().split('T')[0],
          hiring_manager_id: hmUserId || null,
          reporting_manager_id: rmUserId || null,
          salary_range: payAmount ? `${payAmount} ${payRateType}` : null,
          is_internal_role: isInternalRole,
        };

        await updateJob(draftJobId, payload);
        setAutoSaveStatus("saved");
        setTimeout(() => setAutoSaveStatus(""), 2000);
      } catch (err) {
        console.error("Auto-save error:", err);
        setAutoSaveStatus("");
      }
    }, 2000); // Auto-save 2 seconds after last change

    return () => clearTimeout(saveTimer);
  }, [title, internalJD, skills, experienceLevel, locationValue, isJobLocationRemote, companyClient, payAmount, payRateType, startDate, hmUserId, rmUserId, noOfPositions, draftJobId, mode, isReadOnly]);

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
      setScreenError("Add a hiring manager 1-liner to generate roles.");
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
      setScreenError(err?.message || "Failed to generate questions.");
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
      setScreenError(`Please answer: ${missingAnswers.join(", ")}`);
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
      setScreenError(err?.message || "Failed to generate complete job.");
    } finally {
      setIsAnswering(false);
    }
  };

  const handleCreateJob = async () => {
    setIsSaving(true);
    const required = [
      { label: "Job Title", value: title },
      { label: "Internal Job Description", value: internalJD },
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
      setScreenError(err?.message || "Please fill required fields.");
      setIsSaving(false);
      return;
    }

    // Warn if Experience Level is not set (but allow submission)
    if (!experienceLevel || experienceLevel === "") {
      toast.warning("Experience Level not specified - using default value");
    }

    if (!hmUserId?.trim()) {
      setScreenError("Please select a Hiring Manager.");
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
      // Use existing draft job ID or create new one
      let jobId = draftJobId;
      if (!jobId) {
        const data = await createJob(payload);
        jobId = data?.job_id;
      } else {
        // Update existing draft job
        await updateJob(jobId, payload);
      }

      if (jobId) {
        // Get the selected hiring manager's info
        const hiringManager = hiringManagers?.find(hm => hm.user_id === hmUserId);

        // Check if hiring manager == BU head (no approval needed)
        if (hiringManager?.user_id === hiringManager?.bu_head_id) {
          // Hiring manager is also the BU Head - create task for recruiter to start work
          if (rmUserId) {
            try {
              await createTask({
                job_id: jobId,
                assigned_to: rmUserId,
                task_type: "job_recruit",
                status: "active",
                description: `Start candidate search for job "${title}"`,
                priority: "high",
              });
            } catch (taskErr) {
              console.error("Error creating recruiter task:", taskErr);
            }
          }
        } else if (hiringManager?.bu_head_id) {
          // Hiring manager is not BU Head - create approval task for BU Head
          try {
            await createTask({
              job_id: jobId,
              assigned_to: hiringManager.bu_head_id,
              task_type: "job_approval",
              status: "pending",
              description: `Job approval required for "${title}" from ${hiringManager.user_name}`,
              priority: "high",
            });
          } catch (taskErr) {
            console.error("Error creating approval task:", taskErr);
          }
        }
      }

      toast.success(`Created job ${title}`);
      navigate(ROUTES.JOBS);
    } catch (err) {
      console.error("Job creation error:", err);
      const errorMsg = err?.message || err?.response?.data?.detail || "Failed to create job.";
      setScreenError(errorMsg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleNextWithGeneration = async () => {
    setIsGenerating(true);
    try {
      const oneLiner = hmOneLiner.trim();
      if (!oneLiner) {
        setScreenError("Describe the job purpose and requirements to generate details.");
        setIsGenerating(false);
        return;
      }

      if (!payAmount) {
        setScreenError("Please enter a pay rate amount.");
        setIsGenerating(false);
        return;
      }

      // Create draft job if it doesn't exist
      if (!draftJobId) {
        let locationLabel = "";
        if (isJobLocationRemote) {
          const countryName = locationValue?.countryCode ?
            (require("country-state-city").Country.getCountryByCode(locationValue.countryCode)?.name || locationValue.countryCode)
            : "Global";
          locationLabel = `Remote - ${countryName}`;
        } else {
          locationLabel = formatLocation(locationValue) || "Location TBD";
        }

        const draftPayload = {
          job_title: "Draft Job",
          job_description: internalJdTemplate,
          job_skills: "",
          job_experience: "1",
          job_location: locationLabel,
          job_location_country: locationValue?.countryCode || "",
          job_location_state: locationValue?.stateCode || "",
          job_location_city: locationValue?.city || "",
          is_remote: isJobLocationRemote,
          company_type: companyType || "",
          company_name: companyClient || "",
          contact_person: contactPerson || null,
          job_status: "draft",
          no_of_positions: noOfPositions || 1,
          start_date: startDate || new Date().toISOString().split('T')[0],
          hiring_manager_id: hmUserId || null,
          reporting_manager_id: rmUserId || null,
          salary_range: payAmount ? `${payAmount} ${payRateType}` : null,
          is_internal_role: isInternalRole,
        };

        try {
          const draftResponse = await createJob(draftPayload);
          setDraftJobId(draftResponse?.job_id);
        } catch (draftErr) {
          console.error("Error creating draft job:", draftErr);
          toast.warning("Could not create draft - progress may not be saved");
        }
      }

      // Get questions from Flash
      const { questions } = await generateJobWithAgent(oneLiner);

      // Provide default answers from form fields
      const defaultAnswers = {
        job_title: title || "Position",
        position_type: positionType || "Full time",
        pay_range: payAmount ? `${payAmount} ${payRateType}` : "",
        job_location: location || "Remote",
        job_experience: experienceLevel || "1",
      };

      // Generate complete job with defaults
      const data = await generateJobComplete(oneLiner, defaultAnswers);

      // Auto-populate fields from generated data (only update if generated value exists)
      if (data?.job_title) setTitle(data.job_title);
      if (data?.pay_range) {
        const parsedPay = parsePayRangeAnswer(data.pay_range);
        if (parsedPay.amount) setPayAmount(parsedPay.amount);
        if (parsedPay.rateType) setPayRateType(parsedPay.rateType);
      }
      if (data?.job_location) setLocation(data.job_location);
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

      setCurrent(1);
      toast.success("Job details generated! Review and submit.");
    } catch (err) {
      setScreenError(err?.message || "Failed to generate job details.");
      console.error("Generation error:", err);
    } finally {
      setIsGenerating(false);
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
                label="Job Purpose & Requirements"
                value={hmOneLiner}
                onChange={setHmOneLiner}
                rows={4}
                placeholder="Describe what you need: e.g., Senior React developer with AWS experience for 3 years"
              />
            </div>

            {/* Location Section - Uses Country/State/City like candidate form */}
            <div className="md:col-span-2 mt-6">
              <div className="mb-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={isJobLocationRemote}
                    onChange={(e) => setIsJobLocationRemote(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm font-semibold">Remote Role *</span>
                </label>
                <p className="text-xs text-gray-500 mt-1">
                  {isJobLocationRemote
                    ? "Candidates will be filtered by the selected country"
                    : "Specify the office location"}
                </p>
              </div>

              {!isJobLocationRemote && (
                <div className="mb-3 text-xs font-semibold text-gray-700">
                  Job Location *
                </div>
              )}

              {isJobLocationRemote ? (
                <div className="grid gap-3 md:grid-cols-3">
                  <label className="block">
                    <div className="mb-1 text-xs font-semibold text-gray-700">
                      Country
                    </div>
                    <select
                      value={locationValue.countryCode}
                      onChange={(e) =>
                        setLocationValue({ countryCode: e.target.value, stateCode: "", city: "" })
                      }
                      className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
                    >
                      <option value="">Select country</option>
                      {require("country-state-city").Country.getAllCountries().map((c) => (
                        <option key={c.isoCode} value={c.isoCode}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ) : (
                <LocationCascadeSelect value={locationValue} onChange={setLocationValue} />
              )}
            </div>

            {/* Pay Rate Section */}
            <div className="grid gap-3 md:grid-cols-2 mt-6">
              <RateField
                label="Pay Rate *"
                value={payAmount}
                onValueChange={setPayAmount}
                rateType={payRateType}
                onRateTypeChange={setPayRateType}
                rateTypeOptions={["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year", "₹/Hour", "₹/Day", "₹/Week", "₹/Month", "₹/Year"]}
              />
            </div>
          </fieldset>
        );
      case 1:
        return (
          <fieldset disabled={isReadOnly}>
            {/* Internal Job Description */}
            <div className="md:col-span-2 mb-4">
              <TextArea
                label="Internal Job Description *"
                value={internalJD}
                onChange={setInternalJD}
                rows={6}
                placeholder="Editable; can be generated from AI"
              />
            </div>

            {/* Job Details */}
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
                label="Experience Level"
                value={experienceLevel}
                onChange={setExperienceLevel}
                options={Array.from({ length: 20 }, (_, i) => i + 1)}
              />
              <Select
                label="Hiring Manager *"
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
              <Input
                label="Job Open Date (Posted) *"
                value={startDate}
                onChange={setStartDate}
                type="date"
                placeholder="When to post the job"
              />
            </div>

            {/* Skills Section */}
            <div className="md:col-span-2 mt-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <label className="block text-sm font-semibold mb-1">Skills</label>
                  <p className="text-xs text-gray-500">Add required skills for 1-to-1 matching with candidate skills</p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowSkillsModal(true)}
                  className="text-xs text-blue-600 hover:text-blue-700 font-semibold"
                >
                  {selectedSkills.length > 0 ? `Edit (${selectedSkills.length})` : "Add Skills"}
                </button>
              </div>
              {selectedSkills.length > 0 ? (
                <div className="flex flex-wrap gap-2 p-3 border rounded-lg bg-gray-50">
                  {selectedSkills.map((skill, idx) => (
                    <span
                      key={idx}
                      className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium flex items-center gap-2"
                    >
                      {skill.name}
                      {skill.isPrimary && <span className="text-xs font-bold">★</span>}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 p-3 border rounded-lg bg-gray-50">No skills added. Click "Add Skills" to add required skills.</p>
              )}
            </div>
          </fieldset>
        );
    }
  };

  return (
    <div className="grid gap-4">
      <ScreenErrorDisplay
        error={screenError}
        onDismiss={() => setScreenError(null)}
      />
      <Card
        title={isReadOnly ? "View Job" : "Create New Job"}
        icon={<Briefcase className="h-4 w-4" />}
      >
        <div className="flex justify-between items-center mb-4">
          <div>
            <Steps
              current={current}
              items={[{ title: "Step 1" }, { title: "Step 2" }]}
            />
          </div>
          {draftJobId && (
            <div className="text-xs text-gray-500">
              {autoSaveStatus === "saving" && "🔄 Saving..."}
              {autoSaveStatus === "saved" && "✓ Saved"}
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          {renderFormContent()}
        </div>

        {current === 1 ? (
          <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
            <Button onClick={handleCreateJob} disabled={isSaving}>
              {isSaving
                ? "Creating..."
                : canCreateJobDirectly
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
                onClick={handleNextWithGeneration}
                disabled={isGenerating}
              >
                {isGenerating ? "Generating..." : "Next"}
              </Button>
            </div>
          </div>
        )}

        {showSkillsModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <Card className="w-full max-w-2xl mx-auto max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Manage Required Skills</h2>
                <button
                  onClick={() => setShowSkillsModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 mb-6">
                {selectedSkills.length > 0 ? (
                  selectedSkills.map((skill, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="font-semibold text-gray-900">{skill.name}</div>
                          {skill.yearsOfExperience && (
                            <div className="text-sm text-gray-600">Required: {skill.yearsOfExperience} years</div>
                          )}
                          {skill.isPrimary && (
                            <div className="text-xs font-semibold text-blue-600 mt-1">Primary Skill</div>
                          )}
                        </div>
                        <button
                          onClick={() => setSelectedSkills(prev => prev.filter((_, i) => i !== idx))}
                          className="text-red-600 hover:text-red-700 text-sm font-semibold"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500 text-center py-4">No skills added yet</p>
                )}
              </div>

              <div className="border-t pt-4 space-y-3">
                <Input
                  label="Skill Name"
                  placeholder="e.g., Java, React, Project Management"
                  id="job-skill-name-modal"
                />
                <Input
                  label="Years Required"
                  type="number"
                  placeholder="e.g., 5"
                  id="job-years-required-modal"
                />
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="job-is-primary-skill"
                    className="w-4 h-4"
                  />
                  <label htmlFor="job-is-primary-skill" className="text-sm font-medium">
                    Mark as Primary Skill
                  </label>
                </div>
                <Button
                  onClick={() => {
                    const nameInput = document.getElementById('job-skill-name-modal');
                    const yearsInput = document.getElementById('job-years-required-modal');
                    const primaryInput = document.getElementById('job-is-primary-skill');

                    if (nameInput.value.trim()) {
                      const newSkill = {
                        name: nameInput.value.trim(),
                        yearsOfExperience: yearsInput.value ? parseInt(yearsInput.value) : null,
                        isPrimary: primaryInput.checked,
                      };

                      setSelectedSkills(prev => {
                        if (primaryInput.checked) {
                          return [...prev.map(s => ({ ...s, isPrimary: false })), newSkill];
                        }
                        return [...prev, newSkill];
                      });

                      nameInput.value = '';
                      yearsInput.value = '';
                      primaryInput.checked = false;
                    }
                  }}
                  className="w-full"
                >
                  Add Skill
                </Button>
              </div>

              <div className="mt-6 flex items-center justify-end gap-2 border-t pt-4">
                <Button variant="secondary" onClick={() => setShowSkillsModal(false)}>
                  Done
                </Button>
              </div>
            </Card>
          </div>
        )}
      </Card>
    </div>
  );
}
