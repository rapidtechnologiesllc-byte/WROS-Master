import { useEffect, useMemo, useState } from "react";
import { FileText } from "lucide-react";
import { Button, Card } from "../components/ui";
import { assignMultipleJobs, getAllJobs, submitCandidateToJob } from "../services/api/jobs";
import { getUserDetails, createHrAssignment } from "../services/api/users";
import {
  createCandidateHistoryEvent,
  HISTORY_EVENT_TYPES,
} from "../services/api/candidateHistory";
import { toast } from "react-toastify";
import { Select } from "antd";
import {
  Label,
  SelectWrapper,
  StyledSelect,
} from "../styles/CandidateAssignJobModalStyles";
import { mapJobFromApi } from "../routes/Approutes";

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
const INITIAL_UDF_STATE = {
  govtIdType: "",
  govtIdNumber: "",
  previousOrganization: "",
  relevantExperience: "",
  noticePeriod: "",
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
const getSubmitJobErrorMessage = (error) => {
  const statusCode = error?.response?.status;

  const backendMessage =
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    "";

  const isAlreadyAssigned =
    statusCode === 409 ||
    backendMessage?.toLowerCase()?.includes("already assigned");

  if (isAlreadyAssigned) {
    return "This candidate is already submitted to the selected job.";
  }

  return backendMessage || "Unable to submit the candidate to this job.";
};
const CandidateAssignJobModal = ({
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
  const [showUdfModal, setShowUdfModal] = useState(false);
  const [udfData, setUdfData] = useState(INITIAL_UDF_STATE);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [hrOptions, setHrOptions] = useState([]);
  const [selectedHr1Id, setSelectedHr1Id] = useState("");
  const [selectedHr2Id, setSelectedHr2Id] = useState("");

  // Auto-load unique UDF fields with candidate information (non-overlapping fields only)
  useEffect(() => {
    if (candidateDetails && showUdfModal) {
      setUdfData((prev) => ({
        ...prev,
        relevantExperience: candidateDetails?.candidate_relevant_experience || "",
        govtIdType: candidateDetails?.candidate_govt_id_type || "",
        govtIdNumber: candidateDetails?.candidate_govt_id_number || "",
        previousOrganization: candidateDetails?.candidate_previous_organization || "",
        noticePeriod: candidateDetails?.candidate_notice_period || "",
      }));
    }
  }, [candidateDetails, showUdfModal]);

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

  // Auto-load Client Owner and Submit To based on selected job
  useEffect(() => {
    if (selectedJob) {
      const clientOwner = selectedJob?.client_owner_name ||
                         selectedJob?.clientOwnerName ||
                         selectedJob?.client_contact_person ||
                         selectedJob?.contact_person_name ||
                         "";

      // Determine Submit To based on is_internal_role flag or company name
      let isInternalJob = selectedJob?.is_internal_role;

      // Fallback to company name if is_internal_role not set
      if (isInternalJob === null || isInternalJob === undefined) {
        const companyName = selectedJob?.company_name || selectedJob?.companyName || "";
        isInternalJob = companyName?.toLowerCase().includes("blitzenx");
      }

      const submitTo = isInternalJob ? "BU Head" : "L1 Interview → L2 Interview → Client Partner";

      setFormData((prev) => ({
        ...prev,
        primarySales: clientOwner,
        submitTo: submitTo,
      }));
    }
  }, [selectedJob]);

  useEffect(() => {
    let isMounted = true;

    const fetchDefaultHr = async () => {
      const activeJob = preSelectedJob || selectedJob;
      const hrUserId = activeJob?.contactPerson;
      if (!hrUserId) return;
      try {
        const response = await getUserDetails(hrUserId);

        if (!isMounted) return;

        const option = {
          label: response?.user_name || response?.user_email || "Assigned HR",
          value: response?.user_id,
        };

        setHrOptions([option]);
        setSelectedHr1Id(response?.user_id ?? "");
      } catch (error) {
        console.error("Failed to load HR details", error);
      }
    };
    fetchDefaultHr();
    return () => {
      isMounted = false;
    };
  }, [preSelectedJob?.contactPerson, selectedJob?.contactPerson]);

  useEffect(() => {
    let isMounted = true;

    const fetchJobs = async () => {
      try {
        setIsLoadingJobs(true);

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
        toast.error("Failed to load jobs");
      } finally {
        if (isMounted) {
          setIsLoadingJobs(false);
        }
      }
    };

    fetchJobs();

    return () => {
      isMounted = false;
    };
  }, []);

  const updateFormField = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };
  const updateUdfField = (field, value) => {
    setUdfData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };
  const buildUdfPayload = () => ({
    govt_id_type: udfData?.govtIdType || null,
    govt_id_number: udfData?.govtIdNumber?.trim() || null,
    previous_organization: udfData?.previousOrganization?.trim() || null,
    relevant_experience: udfData?.relevantExperience?.trim() || null,
    notice_period: udfData?.noticePeriod?.trim() || null,
  });
  const buildSubmitActivityPayload = () => {
    return {
      candidate_id: candidateDetails?.id,
      candidate_name:
        candidateDetails?.name ||
        `${candidateDetails?.first_name || ""} ${
          candidateDetails?.last_name || ""
        }`.trim(),
      job_id: selectedJob?.id || selectedJob?.job_id || selectedJobId,
      job_title: selectedJob?.title || selectedJob?.job_title || "",
      submit_to: formData?.submitTo,
      submittal_date: formData?.submittalDate,
      submittal_time: formData?.submittalTime,
      timezone: formData?.timeZone,
      recruited_by: formData?.recruitedBy,
      primary_sales: formData?.primarySales,
      position_type: formData?.positionType,
      quoted_bill_rate: formData?.quotedBillRate,
      agreed_bill_rate: formData?.agreedBillRate,
      agreed_pay_rate: formData?.agreedPayRate,
      agreed_on: formData?.agreedOn,
      corp_to_corp: formData?.corpToCorp,
      selected_cv: formData?.selectedCv,
      internal_notes: formData?.internalNotes,
      notify_candidate: formData?.notifyCandidate,
      notify_primary_sales: formData?.notifyPrimarySales,
    };
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
    if (!candidateId) {
      toast.error("Please select a candidate");
      return false;
    }
    if (!selectedJobId) {
      toast.error("Please select a job");
      return false;
    }

    if (!formData?.submittalDate) {
      toast.error("Please select submittal date");
      return false;
    }

    if (!formData?.submittalTime) {
      toast.error("Please select submittal time");
      return false;
    }

    if (!formData?.timeZone) {
      toast.error("Please select time zone");
      return false;
    }
    if (isEmptyValue(formData?.agreedPayRate)) {
      toast.error("Please enter agreed pay rate");
      return false;
    }

    // Validate Experience Level
    if (selectedJob && candidateDetails) {
      const jobRequiredExp = parseExperience(selectedJob?.experienceLevel || selectedJob?.experience_level || "0");
      const candidateExp = parseExperience(candidateDetails?.candidate_experience || candidateDetails?.experience || "0");

      if (jobRequiredExp > 0 && candidateExp < jobRequiredExp) {
        toast.warning(`⚠️ Candidate has ${candidateExp} years experience but job requires ${jobRequiredExp} years. Please confirm before proceeding.`);
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
          toast.error(
            `⚠️ Budget Alert:\n` +
            `Candidate asking: ${candidateDisplay}\n` +
            `Job budget: ${jobDisplay}\n` +
            `Candidate is OUT OF BUDGET. Proceed with caution.`
          );
          return false;
        } else if (jobPayFreq !== candidatePayFreq) {
          // Different frequencies - just warn, don't block
          toast.warning(
            `⚠️ Pay Frequency Mismatch:\n` +
            `Candidate: ${candidateDisplay}\n` +
            `Job Budget: ${jobDisplay}\n` +
            `Please verify the amounts match before proceeding.`
          );
        }
      }
    }

    return true;
  };

  const handleSaveJob = async () => {
    if (!validateForm()) return;
    try {
      setIsAssigning(true);
      // Call the correct /submissions endpoint
      const result = await submitCandidateToJob(
        candidateId,
        selectedJobId,
      );
      if (result?.response?.status === 200 || result?.data?.id) {
        const performedBy =
          localStorage?.getItem?.("hrms_user_name") || "HR User";
        const historyNote = `Candidate submitted to ${
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
            hr2_id: selectedHr2Id || "",
          });
        }
        toast.success("Job submitted successfully ✅");
        await onAssignSuccess?.();
        onClose?.();
        return;
      }
      toast.error("Failed to submit job");
    } catch (err) {
      console.error("Error while submitting job", err);
      toast.error(getSubmitJobErrorMessage(err));
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
          title="Submit Job"
          icon={<FileText className="h-4 w-4" />}
          bodyClassName="p-0"
          right={
            <Button variant="ghost" onClick={onClose} disabled={isAssigning}>
              Close
            </Button>
          }
        >
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

                <FormInput
                  label="Submit To"
                  value={formData?.submitTo}
                  onChange={(value) => updateFormField("submitTo", value)}
                  disabled={isAssigning}
                />
                {/* Primary HR selection removed - not needed until onboarding stage */}

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
                </div>

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

                <FormInput
                  label="Recruited By"
                  value={formData?.recruitedBy}
                  onChange={(value) => updateFormField("recruitedBy", value)}
                  disabled={isAssigning}
                />

                <FormInput
                  label="Client Owner"
                  value={formData?.primarySales}
                  onChange={(value) => updateFormField("primarySales", value)}
                  disabled={isAssigning}
                  placeholder="Auto-populated from selected job's client"
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

              <Button
                variant="primary"
                onClick={handleSaveJob}
                disabled={isAssigning || !selectedJobId}
              >
                {isAssigning ? "Saving..." : "Save"}
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
function UdfModal({ udfData, onChange, onClose }) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">UDFs</h3>
            <p className="mt-1 text-sm text-gray-500">
              User defined fields for candidate submission.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1 text-2xl leading-none text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close UDF modal"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto p-6">
          <div className="grid grid-cols-1 gap-x-8 gap-y-5 lg:grid-cols-3">
            <UdfSelect
              label="Type of Govt ID used for adding Name"
              value={udfData?.govtIdType}
              onChange={(value) => onChange?.("govtIdType", value)}
              options={[
                "PAN",
                "Aadhar",
                "Passport",
                "Driving License",
                "Voter ID",
              ]}
            />

            <UdfInput
              label="Govt ID - ID number as per Govt ID"
              value={udfData?.govtIdNumber}
              onChange={(value) => onChange?.("govtIdNumber", value)}
            />

            <UdfInput
              label="Name of previous organization"
              value={udfData?.previousOrganization}
              onChange={(value) => onChange?.("previousOrganization", value)}
            />

            <UdfInput
              label="Relevant experience e.g 10Y 5M"
              value={udfData?.relevantExperience}
              onChange={(value) => onChange?.("relevantExperience", value)}
            />

            <UdfInput
              label="Notice Period"
              value={udfData?.noticePeriod}
              onChange={(value) => onChange?.("noticePeriod", value)}
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-200 bg-gray-50 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-gray-300 bg-white px-5 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100"
          >
            Close
          </button>

          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
          >
            Save UDFs
          </button>
        </div>
      </div>
    </div>
  );
}

function UdfInput({ label, value, onChange, type = "text" }) {
  return (
    <div>
      <label className="mb-1.5 flex min-h-[40px] items-end text-sm font-semibold leading-5 text-gray-700">
        {label}
      </label>

      <input
        type={type}
        value={value || ""}
        onChange={(event) => onChange?.(event?.target?.value)}
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-gray-400"
      />
    </div>
  );
}

function UdfSelect({ label, value, onChange, options = [] }) {
  return (
    <div>
      <label className="mb-1.5 flex min-h-[40px] items-end text-sm font-semibold leading-5 text-gray-700">
        {label}
      </label>

      <select
        value={value || ""}
        onChange={(event) => onChange?.(event?.target?.value)}
        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-gray-400"
      >
        <option value="">Select</option>

        {options?.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
export default CandidateAssignJobModal;
