import { useEffect, useMemo, useState } from "react";
import { FileText, AlertCircle, CheckCircle, X } from "lucide-react";
import { Button, Card } from "../components/ui";
import { assignJob, getAllJobs, submitCandidateToJob } from "../services/api/jobs";
import { getSubmissionReadiness } from "../services/api/submissions";
import { getUserDetails, createHrAssignment } from "../services/api/users";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import {
  createCandidateHistoryEvent,
  HISTORY_EVENT_TYPES,
} from "../services/api/candidateHistory";
import {
  Label,
  SelectWrapper,
  StyledSelect,
} from "../styles/CandidateAssignJobModalStyles";
import { mapJobFromApi } from "../utils/jobMappers";

const getTodayDate = () => {
  const today = new Date();
  return today.toISOString().split("T")[0];
};

const getCurrentTime = () => {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, "0");
  const minutes = String(now.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
};

const INITIAL_FORM_STATE = {
  submitTo: "",
  submittalDate: getTodayDate(),
  submittalTime: getCurrentTime(),
  timeZone: "Asia/Kolkata",
  recruitedBy: "",
  primarySales: "",
  contactPerson: "",
  positionType: "",
  quotedBillRate: "",
  quotedBillRateType: "$/Hour",
  agreedBillRate: "",
  agreedBillRateType: "$/Hour",
  agreedPayRate: "",
  agreedPayRateType: "$/Hour",
  agreedOn: getTodayDate(),
  corpToCorp: "",
  selectedCv: "",
  internalNotes: "",
  notifyCandidate: false,
  notifyPrimarySales: false,
};
const TIME_ZONE_OPTIONS = [
  "Asia/Kolkata",
  "UTC",
  "America/New_York",
  "Europe/London",
  "Asia/Dubai",
  "Asia/Singapore",
];

const POSITION_TYPE_OPTIONS = [
  "Full Time",
  "Contract",
  "Contract To Hire",
  "Corp To Corp",
  "W2",
];
const RATE_TYPE_OPTIONS = [
  { label: "$/Hour", value: "$/Hour" },
  { label: "$/Day", value: "$/Day" },
  { label: "$/Year", value: "$/Year" },
  { label: "$/Monthly", value: "$/Monthly" },
  { label: "INR/Hour", value: "INR/Hour" },
  { label: "INR/Day", value: "INR/Day" },
  { label: "INR/Year", value: "INR/Year" },
  { label: "INR/Monthly", value: "INR/Monthly" },
];
const CV_OPTIONS = ["Default Resume", "Updated Resume", "Client Resume"];
// apiRequest throws an Error whose message already joins every blocker the backend
// returned (client.js formatApiErrorMessage). 409 also means "job not open" or
// "job has no client", so only the duplicate gets the friendly wording.
const getSubmitJobErrorMessage = (error) => {
  const message = error?.message || "";
  if (error?.status === 409 && message.toLowerCase().includes("already submitted")) {
    return "This candidate is already submitted to the selected job.";
  }
  return message || "Unable to submit the candidate to this job.";
};
const CandidateAssignJobModalBody = ({
  onClose,
  candidateDetails,
  selectedJob: preSelectedJob,
  allCandidates = [],
  onAssignSuccess,
}) => {
  const isJobWorkspaceFlow = Boolean(preSelectedJob?.id);
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const candidateId = isJobWorkspaceFlow
    ? selectedCandidateId
    : candidateDetails?.id;
  const candidateOptions = useMemo(() => {
    return allCandidates?.map((candidate) => ({
      label: candidate?.name || "Unknown Candidate",
      value: candidate?.id,
    }));
  }, [allCandidates]);
  useEffect(() => {
    if (preSelectedJob?.id) {
      setSelectedJobId(preSelectedJob.id);
    }
  }, [preSelectedJob]);

  const [formData, setFormData] = useState(INITIAL_FORM_STATE);
  const [isAssigning, setIsAssigning] = useState(false);
  const [selectedHr1Id, setSelectedHr1Id] = useState("");
  const [contactPersonOptions, setContactPersonOptions] = useState([]);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  // What this button does for the candidate now (CEO 2026-10-14): before the bench they are
  // submitted to the job (the hiring pipeline starts); a bench employee is submitted to the
  // client; anyone else sees what blocks them. Re-checked whenever the job or candidate changes.
  const [readiness, setReadiness] = useState(null);
  useEffect(() => {
    let live = true;
    setReadiness(null);
    if (!candidateId || !selectedJobId) return undefined;
    getSubmissionReadiness(candidateId, selectedJobId)
      .then((r) => live && setReadiness(r))
      .catch((err) => live && setActionError(`Could not check the candidate: ${err.message}`));
    return () => {
      live = false;
    };
  }, [candidateId, selectedJobId]);
  const submitsToClient = readiness?.action === "SUBMIT_TO_CLIENT";
  const actionLabel = submitsToClient ? "Submit to Client" : "Submit to Job";

  const jobOptions = useMemo(() => {
    return jobs?.map((job) => {
      // Try multiple sources for company/client name
      const companyName = job?.company_name ||
                         job?.companyName ||
                         job?.client_name ||
                         job?.clientName ||
                         "(No Client Name)";

      return {
        label: `${companyName} | ${
          job?.title || job?.job_title || "Untitled Job"
        } | ${job?.id || job?.job_id}`,
        value: job?.id || job?.job_id,
      };
    });
  }, [jobs]);

  const selectedJob = useMemo(() => {
    return jobs?.find(
      (job) => String(job?.id || job?.job_id) === String(selectedJobId),
    );
  }, [jobs, selectedJobId]);

  // Auto-load all job data when selected job changes
  useEffect(() => {
    if (selectedJob) {
      const clientOwner = selectedJob?.client_owner_name ||
                         selectedJob?.clientOwnerName ||
                         selectedJob?.client_contact_person ||
                         selectedJob?.contact_person_name ||
                         "";

      // Get Contact Person (supports comma-separated multiple values)
      const contactPerson = selectedJob?.contact_person_name ||
                           selectedJob?.contactPerson ||
                           selectedJob?.contact_person ||
                           "";




      // Parse pay information from job
      let payAmount = "";
      let payFrequency = "Annual";
      let payCurrency = "USD";

      const payRange = selectedJob?.payRange ||
                       selectedJob?.pay_range ||
                       selectedJob?.salary_range || "";

      if (payRange) {
        const payParts = String(payRange).trim().split(/\s+/);
        // Try to extract: "USD Annual 150000" or "150000 $/Hour"
        if (payParts[0] === "USD" || payParts[0] === "INR") {
          payCurrency = payParts[0];
        }
        if (payParts.includes("Annual") || payParts.includes("Hourly")) {
          payFrequency = payParts.includes("Annual") ? "Annual" : "Hourly";
        }
        // Extract numeric amount (first number found)
        const numMatch = payRange.match(/\d+/);
        if (numMatch) {
          payAmount = numMatch[0];
        }
      }

      // Determine Submit To based on is_internal_role flag or company name
      let isInternalJob = selectedJob?.is_internal_role;
      if (isInternalJob === null || isInternalJob === undefined) {
        const companyName = selectedJob?.company_name || selectedJob?.companyName || "";
        isInternalJob = companyName?.toLowerCase().includes("blitzenx");
      }
      const submitTo = isInternalJob ? "BU Head" : "L1 Interview → L2 Interview → Client Partner";

      // Get current user for auto-population
      const currentUserName = localStorage?.getItem?.("hrms_user_name") || "";

      setFormData((prev) => ({
        ...prev,
        primarySales: clientOwner,
        submitTo: submitTo,
        recruitedBy: currentUserName, // Auto-populate current user
        agreedPayRate: payAmount,
        agreedPayRateType: payCurrency === "INR" ? "INR/Year" : payFrequency === "Hourly" ? "$/Hour" : "$/Year",
      }));

      // Set contact person options for dropdown (parse comma-separated)
      if (contactPerson) {
        const persons = String(contactPerson)
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean);

        const options = persons.map((person) => ({
          label: person,
          value: person,
        }));
        setContactPersonOptions(options);
      }
    }
  }, [selectedJob]);

  const defaultHrUserId = (preSelectedJob || selectedJob)?.contactPerson;
  useEffect(() => {
    let isMounted = true;

    const fetchDefaultHr = async () => {
      if (!defaultHrUserId) return;
      try {
        const response = await getUserDetails(defaultHrUserId);

        if (!isMounted) return;

        setSelectedHr1Id(response?.user_id ?? "");
      } catch (error) {
        // shown in the modal: a rejection thrown out of an effect reaches no handler
        console.error("Failed to load HR details", error);
        if (isMounted) setActionError(`Failed to fetch HR details: ${error.message}`);
      }
    };
    fetchDefaultHr();
    return () => {
      isMounted = false;
    };
  }, [defaultHrUserId]);

  useEffect(() => {
    let isMounted = true;

    const fetchJobs = async () => {
      try {
        setActionError(null);

        const response = await getAllJobs();
        if (!isMounted) return;

        const mappedJobs = (response?.jobs || [])?.map((job) =>
          mapJobFromApi(job, []),
        );
        setJobs(mappedJobs);
        if (!preSelectedJob?.id) {
          setSelectedJobId("");
        }
      } catch (err) {
        console.error("Failed to fetch jobs", err);
        if (isMounted) {
          setActionError("Failed to load jobs");
        }
      }
    };

    fetchJobs();

    return () => {
      isMounted = false;
    };
  }, [preSelectedJob?.id]);

  const updateFormField = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };
  const isEmptyValue = (value) => !String(value ?? "").trim();

  const parseExperience = (exp) => {
    if (!exp) return 0;
    const match = String(exp).match(/\d+/);
    return match ? parseInt(match[0]) : 0;
  };

  const parsePayAmount = (pay) => {
    if (!pay) return 0;
    // Extract numeric value from formatted strings like "150 $/Year" or "150000 INR Annual"
    const match = String(pay).match(/(\d+(?:\.\d+)?)/);
    return match ? parseFloat(match[0]) : 0;
  };

  const getPayFrequency = (payStr) => {
    if (!payStr) return null;
    const str = String(payStr).toLowerCase();
    if (str.includes("hour") || str.includes("hr") || str.includes("/hr")) return "Hourly";
    if (str.includes("week")) return "Weekly";
    if (str.includes("year") || str.includes("annual") || str.includes("/year")) return "Annual";
    return "Annual"; // default
  };

  const validateForm = () => {
    setActionError(null);

    if (!candidateId) {
      setActionError("Please select a candidate");
      return false;
    }
    if (!selectedJobId) {
      setActionError("Please select a job");
      return false;
    }

    if (!formData?.submittalDate) {
      setActionError("Please select submittal date");
      return false;
    }

    if (!formData?.submittalTime) {
      setActionError("Please select submittal time");
      return false;
    }

    if (!formData?.timeZone) {
      setActionError("Please select time zone");
      return false;
    }
    if (isEmptyValue(formData?.agreedPayRate)) {
      setActionError("Please enter agreed pay rate");
      return false;
    }

    // Validate Experience Level
    if (selectedJob && candidateDetails) {
      const jobRequiredExp = parseExperience(selectedJob?.experienceLevel || selectedJob?.experience_level || "0");
      const candidateExp = parseExperience(candidateDetails?.candidate_experience || candidateDetails?.experience || "0");

      if (jobRequiredExp > 0 && candidateExp < jobRequiredExp) {
        setActionError(`⚠️ Candidate has ${candidateExp} years experience but job requires ${jobRequiredExp} years. Please confirm before proceeding.`);
        // Don't block submission, just warn
      }
    }

    // Validate Pay Range
    if (selectedJob && formData?.agreedPayRate) {
      const jobPayStr = selectedJob?.salaryRange || selectedJob?.pay_range || selectedJob?.salary_range || "0";
      const jobPayAmount = parsePayAmount(jobPayStr);
      const jobPayFreq = getPayFrequency(jobPayStr);

      const candidatePayStr = formData?.agreedPayRate;
      const candidatePayAmount = parsePayAmount(candidatePayStr);
      const candidatePayFreq = getPayFrequency(candidatePayStr);

      // Only compare if both have amounts
      if (jobPayAmount > 0 && candidatePayAmount > 0) {
        // Show comparison info
        const jobDisplay = `${jobPayAmount} ${jobPayFreq}`;
        const candidateDisplay = `${candidatePayAmount} ${candidatePayFreq}`;

        // Simple numeric comparison (ideally should normalize to same frequency, but this is a basic check)
        // For strict validation, if same frequency, can compare directly
        if (jobPayFreq === candidatePayFreq && candidatePayAmount > jobPayAmount) {
          setActionError(
            `⚠️ Budget Alert: Candidate asking ${candidateDisplay}, Job budget ${jobDisplay}. Candidate is OUT OF BUDGET. Proceed with caution.`
          );
          return false;
        } else if (jobPayFreq !== candidatePayFreq) {
          // Different frequencies - just warn, don't block
          setActionError(
            `⚠️ Pay Frequency Mismatch: Candidate ${candidateDisplay}, Job Budget ${jobDisplay}. Please verify the amounts match before proceeding.`
          );
        }
      }
    }

    return true;
  };

  const handleSaveJob = async () => {
    if (!validateForm()) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      setIsAssigning(true);
      // a bench employee goes to the client; anyone before the bench goes onto the job
      const result = submitsToClient
        ? await submitCandidateToJob(candidateId, selectedJobId)
        : { response: await assignJob(selectedJobId, candidateId, {}) };
      if (result?.response?.ok || result?.data?.id) {
        const performedBy =
          localStorage?.getItem?.("hrms_user_name") || "HR User";
        const historyNote = `Candidate submitted to ${submitsToClient ? "the client for " : ""}${
          selectedJob?.title || selectedJob?.job_title || "selected job"
        }.`;
        const appliedDateTime =
          formData?.submittalDate && formData?.submittalTime
            ? `${formData.submittalDate}T${formData.submittalTime}:00`
            : new Date().toISOString();
        await createCandidateHistoryEvent(candidateId, {
          event_type: HISTORY_EVENT_TYPES.APPLIED,
          note: historyNote,
          job_id: selectedJob?.id || selectedJob?.job_id || selectedJobId,
          performed_by_name: performedBy,
          event_at: appliedDateTime,
        });
        // Only create HR assignment if hr1_id is provided
        if (selectedHr1Id) {
          await createHrAssignment({
            candidate_id: candidateId,
            hr1_id: selectedHr1Id,
            hr2_id: "",
          });
        }
        setActionSuccess(submitsToClient ? "Submitted to the client ✅" : "Submitted to the job ✅");
        await onAssignSuccess?.();
        onClose?.();
        return;
      }
      setActionError("Failed to submit job");
    } catch (err) {
      console.error("Error while submitting job", err);
      setActionError(getSubmitJobErrorMessage(err));
    } finally {
      setIsAssigning(false);
    }
  };
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 xl:items-center"
      role="dialog"
      aria-modal="true"
    >
      <div className="my-4 w-full max-w-7xl xl:my-0">
        <Card
          title={actionLabel}
          icon={<FileText className="h-4 w-4" />}
          bodyClassName="p-0"
          right={
            <Button variant="ghost" onClick={onClose} disabled={isAssigning}>
              Close
            </Button>
          }
        >
          {/* Action Error Banner */}
          {actionError && (
            <div className="border-b border-red-200 bg-red-50 px-6 py-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-700">{actionError}</p>
                </div>
                <button
                  onClick={() => setActionError(null)}
                  className="text-red-600 hover:text-red-800 flex-shrink-0"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>
          )}

          {/* Action Success Banner */}
          {actionSuccess && (
            <div className="border-b border-green-200 bg-green-50 px-6 py-4">
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-green-700">{actionSuccess}</p>
                </div>
                <button
                  onClick={() => setActionSuccess(null)}
                  className="text-green-600 hover:text-green-800 flex-shrink-0"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>
          )}

          <div className="overflow-visible">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Candidate
                  </p>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {candidateDetails?.name ||
                      `${candidateDetails?.first_name || ""} ${
                        candidateDetails?.last_name || ""
                      }`.trim() ||
                      "Candidate"}
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    {candidateDetails?.email || "-"}{" "}
                    {candidateDetails?.phone
                      ? `• ${candidateDetails.phone}`
                      : ""}
                  </p>
                </div>

                <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-start">
                  <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm shadow-sm">
                    <p className="text-xs font-medium uppercase text-gray-500">
                      Selected Job
                    </p>
                    <p className="mt-1 font-semibold text-gray-900">
                      {selectedJob?.title ||
                        selectedJob?.job_title ||
                        preSelectedJob?.title ||
                        "No job selected"}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      {selectedJob?.company ||
                        selectedJob?.companyName ||
                        selectedJob?.clientName ||
                        selectedJob?.location ||
                        preSelectedJob?.location ||
                        "-"}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 p-5 xl:grid-cols-3">
              <SectionCard title="Basic Info">
                {!isJobWorkspaceFlow && (
                  <SelectWrapper>
                    <Label>Selected Job</Label>
                    <StyledSelect
                      showSearch={{ optionFilterProp: "label" }}
                      value={selectedJobId}
                      placeholder="Select a Job"
                      onChange={setSelectedJobId}
                      options={jobOptions}
                    />
                  </SelectWrapper>
                )}
                {isJobWorkspaceFlow && (
                  <SelectWrapper>
                    <Label>Select Candidate</Label>
                    <StyledSelect
                      showSearch={{ optionFilterProp: "label" }}
                      value={selectedCandidateId}
                      placeholder="Select a Candidate"
                      onChange={setSelectedCandidateId}
                      options={candidateOptions}
                    />
                  </SelectWrapper>
                )}

                <FormSelect
                  label="Submit To (Person/Role)"
                  required
                  value={formData?.submitTo}
                  onChange={(value) => updateFormField("submitTo", value)}
                  options={[
                    ...(selectedJob?.hiring_manager_name || selectedJob?.hiringManager ? [
                      { label: `Hiring Manager: ${selectedJob?.hiring_manager_name || selectedJob?.hiringManager}`, value: selectedJob?.hiring_manager_name || selectedJob?.hiringManager }
                    ] : []),
                    ...(selectedJob?.client_owner_name || selectedJob?.clientOwnerName ? [
                      { label: `Client Partner: ${selectedJob?.client_owner_name || selectedJob?.clientOwnerName}`, value: selectedJob?.client_owner_name || selectedJob?.clientOwnerName }
                    ] : []),
                    ...(selectedJob?.bu_head_name || selectedJob?.buHeadName ? [
                      { label: `BU Head: ${selectedJob?.bu_head_name || selectedJob?.buHeadName}`, value: selectedJob?.bu_head_name || selectedJob?.buHeadName }
                    ] : []),
                  ]}
                  disabled={isAssigning}
                  placeholder="Select person to submit to"
                />
                {/* Primary HR selection removed - not needed until onboarding stage */}

                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <FormInput
                    label="Submittal Date"
                    type="date"
                    required
                    value={formData?.submittalDate}
                    onChange={(value) =>
                      updateFormField("submittalDate", value)
                    }
                    disabled={isAssigning}
                  />

                  <FormInput
                    label="Submittal Time"
                    type="time"
                    required
                    value={formData?.submittalTime}
                    onChange={(value) =>
                      updateFormField("submittalTime", value)
                    }
                    disabled={isAssigning}
                  />

                  <FormSelect
                    label="Time Zone"
                    required
                    value={formData?.timeZone}
                    onChange={(value) => updateFormField("timeZone", value)}
                    options={TIME_ZONE_OPTIONS?.map((zone) => ({
                      label: zone,
                      value: zone,
                    }))}
                    disabled={isAssigning}
                  />
                </div>

                <FormInput
                  label="Recruited By"
                  value={formData?.recruitedBy}
                  onChange={(value) => updateFormField("recruitedBy", value)}
                  disabled={isAssigning}
                  placeholder="Auto-populated from current user"
                />

                <FormInput
                  label="Client Name"
                  value={selectedJob?.company_name || selectedJob?.companyName || selectedJob?.clientName || ""}
                  disabled={true}
                  placeholder="Auto-populated from selected job"
                />

                <FormInput
                  label="Client Owner / Partner"
                  value={formData?.primarySales}
                  onChange={(value) => updateFormField("primarySales", value)}
                  disabled={isAssigning}
                  placeholder="Auto-populated from selected job"
                />

                <FormInput
                  label="Department"
                  value={selectedJob?.dept || selectedJob?.department_name || ""}
                  disabled={true}
                  placeholder="Auto-populated from selected job"
                />

                <FormSelect
                  label="Contact Person (Multiple)"
                  value={formData?.contactPerson || ""}
                  onChange={(value) => updateFormField("contactPerson", value)}
                  options={contactPersonOptions}
                  disabled={isAssigning}
                  placeholder="Select from available contacts"
                />

                <FormInput
                  label="Hiring Manager"
                  value={selectedJob?.hiring_manager_name || selectedJob?.hiringManager || ""}
                  disabled={true}
                  placeholder="Auto-populated from selected job"
                />

                <FormInput
                  label="Hiring Team"
                  value={selectedJob?.hiring_team || selectedJob?.hiringTeam || ""}
                  disabled={true}
                  placeholder="Auto-populated from selected job"
                />
              </SectionCard>

              <SectionCard title="Pay">
                <FormSelect
                  label="Position Type"
                  value={formData?.positionType}
                  onChange={(value) => updateFormField("positionType", value)}
                  options={POSITION_TYPE_OPTIONS?.map((type) => ({
                    label: type,
                    value: type,
                  }))}
                  disabled={isAssigning}
                />

                <RateField
                  label="Quoted Bill Rate"
                  value={formData?.quotedBillRate}
                  rateType={formData?.quotedBillRateType}
                  onValueChange={(value) =>
                    updateFormField("quotedBillRate", value)
                  }
                  onRateTypeChange={(value) =>
                    updateFormField("quotedBillRateType", value)
                  }
                  disabled={isAssigning}
                />

                <RateField
                  label="Agreed Bill Rate"
                  value={formData?.agreedBillRate}
                  rateType={formData?.agreedBillRateType}
                  onValueChange={(value) =>
                    updateFormField("agreedBillRate", value)
                  }
                  onRateTypeChange={(value) =>
                    updateFormField("agreedBillRateType", value)
                  }
                  disabled={isAssigning}
                />
                <RateField
                  label="Agreed Pay Rate"
                  required
                  value={formData?.agreedPayRate}
                  rateType={formData?.agreedPayRateType}
                  onValueChange={(value) =>
                    updateFormField("agreedPayRate", value)
                  }
                  onRateTypeChange={(value) =>
                    updateFormField("agreedPayRateType", value)
                  }
                  disabled={isAssigning}
                />

                <FormInput
                  label="Agreed On"
                  type="date"
                  value={formData?.agreedOn}
                  onChange={(value) => updateFormField("agreedOn", value)}
                  disabled={isAssigning}
                />

                <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
                  <FormSelect
                    label="Corp To Corp"
                    value={
                      formData?.corpToCorp === true
                        ? "yes"
                        : formData?.corpToCorp === false
                          ? "no"
                          : ""
                    }
                    onChange={(value) =>
                      updateFormField(
                        "corpToCorp",
                        value === "yes" ? true : value === "no" ? false : "",
                      )
                    }
                    options={[
                      { label: "Yes", value: "yes" },
                      { label: "No", value: "no" },
                    ]}
                    disabled={isAssigning}
                    placeholder="Select"
                  />
                </div>
              </SectionCard>

              <SectionCard title="CV">
                <FormSelect
                  label="Select CV"
                  value={formData?.selectedCv}
                  onChange={(value) => updateFormField("selectedCv", value)}
                  options={CV_OPTIONS?.map((cv) => ({
                    label: cv,
                    value: cv,
                  }))}
                  disabled={isAssigning}
                />

                <FormTextarea
                  label="Internal Notes"
                  value={formData?.internalNotes}
                  onChange={(value) => updateFormField("internalNotes", value)}
                  disabled={isAssigning}
                />

                <div className="mt-4 space-y-3 rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <CheckboxField
                    label="Notify Candidate"
                    checked={formData?.notifyCandidate}
                    onChange={(value) =>
                      updateFormField("notifyCandidate", value)
                    }
                    disabled={isAssigning}
                  />

                  <CheckboxField
                    label="Notify Primary Sales"
                    checked={formData?.notifyPrimarySales}
                    onChange={(value) =>
                      updateFormField("notifyPrimarySales", value)
                    }
                    disabled={isAssigning}
                  />
                </div>
              </SectionCard>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-gray-200 bg-white px-6 py-4">
              <Button variant="ghost" onClick={onClose} disabled={isAssigning}>
                Cancel
              </Button>

              {readiness?.blockers?.length ? (
                <div className="mr-auto max-w-xl text-xs text-amber-800">
                  {readiness.blockers.map((b) => b.message).join(" ")}
                </div>
              ) : null}
              <Button
                variant="primary"
                onClick={handleSaveJob}
                disabled={isAssigning || !selectedJobId || !readiness || readiness.action === "NONE"
                  || readiness.blockers.length > 0}
              >
                {isAssigning ? "Saving..." : actionLabel}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

function SectionCard({ title, children }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-700">
        {title}
      </h3>
      {children}
    </section>
  );
}
function RateField({
  label,
  value,
  rateType,
  onValueChange,
  onRateTypeChange,
  required = false,
  disabled = false,
}) {
  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-sm font-medium text-gray-700">
        {label} {required ? <span className="text-red-500">*</span> : null}
      </label>

      <div className="flex overflow-hidden rounded-xl border border-gray-300 bg-white transition focus-within:border-gray-400">
        <input
          type="number"
          min="0"
          step="0.01"
          value={value ?? ""}
          disabled={disabled}
          onChange={(event) => onValueChange?.(event?.target?.value)}
          className="min-w-0 flex-1 border-0 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none placeholder:text-gray-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
        />

        <select
          value={rateType || "$/Hour"}
          disabled={disabled}
          onChange={(event) => onRateTypeChange?.(event?.target?.value)}
          className="w-36 border-l border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
        >
          {RATE_TYPE_OPTIONS?.map((option) => (
            <option key={option?.value} value={option?.value}>
              {option?.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
function FormInput({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  disabled = false,
}) {
  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-sm font-medium text-gray-700">
        {label} {required ? <span className="text-red-500">*</span> : null}
      </label>

      <input
        type={type}
        value={value || ""}
        disabled={disabled}
        onChange={(event) => onChange?.(event?.target?.value)}
        className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-gray-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
      />
    </div>
  );
}

function FormSelect({
  label,
  value,
  onChange,
  options = [],
  required = false,
  disabled = false,
  placeholder = "Select",
}) {
  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-sm font-medium text-gray-700">
        {label} {required ? <span className="text-red-500">*</span> : null}
      </label>

      <select
        value={value || ""}
        disabled={disabled}
        onChange={(event) => onChange?.(event?.target?.value)}
        className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition focus:border-gray-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
      >
        <option value="">{placeholder}</option>

        {options?.map((option) => (
          <option key={option?.value} value={option?.value}>
            {option?.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function FormTextarea({ label, value, onChange, rows = 5, disabled = false }) {
  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-sm font-medium text-gray-700">
        {label}
      </label>

      <textarea
        rows={rows}
        value={value || ""}
        disabled={disabled}
        onChange={(event) => onChange?.(event?.target?.value)}
        className="w-full resize-none rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-gray-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
      />
    </div>
  );
}

function CheckboxField({ label, checked, onChange, disabled = false }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-gray-700">
      <input
        type="checkbox"
        checked={Boolean(checked)}
        disabled={disabled}
        onChange={(event) => onChange?.(event?.target?.checked)}
        className="h-4 w-4 rounded border-gray-300 disabled:cursor-not-allowed"
      />
      {label}
    </label>
  );
}
// The permission gate renders before any hook runs; the hooks live in the body so they
// are called in the same order on every render (react-hooks/rules-of-hooks).
const CandidateAssignJobModal = (props) => {
  const { onClose } = props;
  // Permission Gate: Only users with jobs.edit can assign candidates to jobs
  if (!hasPermission('jobs', 'edit')) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg p-6 max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">You do not have permission to assign candidates to jobs.</p>
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return <CandidateAssignJobModalBody {...props} />;
};

export default CandidateAssignJobModal;
