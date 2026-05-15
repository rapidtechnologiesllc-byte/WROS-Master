import { useEffect, useMemo, useState } from "react";
import { FileText } from "lucide-react";
import { Button, Card } from "../components/ui";
import { assignMultipleJobs, getAllJobs } from "../services/api/jobs";
import { mapJobFromApi } from "../App";
import { toast } from "react-toastify";

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
  agreedBillRate: "",
  agreedPayRate: "",
  agreedOn: getTodayDate(),
  corpToCorp: false,
  selectedCv: "",
  internalNotes: "",
  notifyCandidate: false,
  notifyPrimarySales: false,
};
const INITIAL_UDF_STATE = {
  govtIdType: "",
  govtIdNumber: "",
  dateOfBirth: "",
  previousOrganization: "",
  totalExperience: "",
  relevantExperience: "",
  educationalQualification: "",
  collegeOrUniversity: "",
  reviewForSubmission: "",
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

const CandidateAssignJobModal = ({ onClose, candidateDetails }) => {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [formData, setFormData] = useState(INITIAL_FORM_STATE);
  const [showUdfModal, setShowUdfModal] = useState(false);
  const [udfData, setUdfData] = useState(INITIAL_UDF_STATE);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);

  const jobOptions = useMemo(() => {
    return jobs?.map((job) => ({
      label: job?.title || job?.job_title || "Untitled Job",
      value: job?.id || job?.job_id,
    }));
  }, [jobs]);

  const selectedJob = useMemo(() => {
    return jobs?.find(
      (job) => String(job?.id || job?.job_id) === String(selectedJobId),
    );
  }, [jobs, selectedJobId]);

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
        setSelectedJobId("");
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

  const validateForm = () => {
    if (!candidateDetails?.id) {
      toast.error("Candidate details are missing");
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

    return true;
  };

  const handleSaveJob = async () => {
    if (!validateForm()) return;

    const payload = buildSubmitActivityPayload();

    try {
      setIsAssigning(true);
      const submitJobPayload = {
        application_status: "Applied",
        submit_to: formData?.submitTo || null,
        submittal_date: formData?.submittalDate || null,
        submittal_time: formData?.submittalTime || null,
        timezone: formData?.timeZone || null,
        recruited_by: formData?.recruitedBy || null,
        primary_sales: formData?.primarySales || null,
        position_type: formData?.positionType || null,
        quoted_bill_rate: formData?.quotedBillRate || null,
        agreed_bill_rate: formData?.agreedBillRate || null,
        agreed_pay_rate: formData?.agreedPayRate || null,
        agreed_on: formData?.agreedOn || null,
        corp_to_corp: Boolean(formData?.corpToCorp),
        selected_cv_id: formData?.selectedCv || null,
        internal_notes: formData?.internalNotes?.trim() || null,
        notify_candidate: Boolean(formData?.notifyCandidate),
        notify_primary_sales: Boolean(formData?.notifyPrimarySales),
      };

      const result = await assignMultipleJobs(
        selectedJobId,
        candidateDetails?.id,
        submitJobPayload,
      );
      if (result?.status === 201) {
        toast.success("Job submitted successfully ✅");
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
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-7xl">
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
          <div className="max-h-[82vh] overflow-y-auto">
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
                {/* 
                <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm shadow-sm">
                  <p className="text-xs font-medium uppercase text-gray-500">
                    Selected Job
                  </p>
                  <p className="mt-1 font-semibold text-gray-900">
                    {selectedJob?.title ||
                      selectedJob?.job_title ||
                      "No job selected"}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">
                    {selectedJob?.company ||
                      selectedJob?.companyName ||
                      selectedJob?.clientName ||
                      selectedJob?.location ||
                      "-"}
                  </p>
                </div> */}
                <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-start">
                  <button
                    type="button"
                    onClick={() => setShowUdfModal(true)}
                    disabled={isAssigning}
                    className="rounded-lg px-2 py-1 text-sm font-semibold text-blue-600 transition hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    UDFs
                  </button>

                  <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm shadow-sm">
                    <p className="text-xs font-medium uppercase text-gray-500">
                      Selected Job
                    </p>

                    <p className="mt-1 font-semibold text-gray-900">
                      {selectedJob?.title ||
                        selectedJob?.job_title ||
                        "No job selected"}
                    </p>

                    <p className="mt-1 text-xs text-gray-500">
                      {selectedJob?.company ||
                        selectedJob?.companyName ||
                        selectedJob?.clientName ||
                        selectedJob?.location ||
                        "-"}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 p-6 xl:grid-cols-3">
              <SectionCard title="Basic Info">
                <FormSelect
                  label="Selected Job"
                  required
                  value={selectedJobId}
                  onChange={setSelectedJobId}
                  options={jobOptions}
                  disabled={isLoadingJobs || isAssigning}
                  placeholder={isLoadingJobs ? "Loading jobs..." : "Select job"}
                />

                <FormInput
                  label="Submit To"
                  value={formData?.submitTo}
                  onChange={(value) => updateFormField("submitTo", value)}
                  disabled={isAssigning}
                />

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
                  label="Primary Sales"
                  value={formData?.primarySales}
                  onChange={(value) => updateFormField("primarySales", value)}
                  disabled={isAssigning}
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

                <FormInput
                  label="Quoted Bill Rate"
                  value={formData?.quotedBillRate}
                  onChange={(value) => updateFormField("quotedBillRate", value)}
                  disabled={isAssigning}
                />

                <FormInput
                  label="Agreed Bill Rate"
                  value={formData?.agreedBillRate}
                  onChange={(value) => updateFormField("agreedBillRate", value)}
                  disabled={isAssigning}
                />

                <FormInput
                  label="Agreed Pay Rate"
                  value={formData?.agreedPayRate}
                  onChange={(value) => updateFormField("agreedPayRate", value)}
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
                  <CheckboxField
                    label="Corp To Corp"
                    checked={formData?.corpToCorp}
                    onChange={(value) => updateFormField("corpToCorp", value)}
                    disabled={isAssigning}
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
        {showUdfModal && (
          <UdfModal
            udfData={udfData}
            onChange={updateUdfField}
            onClose={() => setShowUdfModal(false)}
          />
        )}
      </div>
    </div>
  );
};

function SectionCard({ title, children }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-5 text-sm font-semibold uppercase tracking-wide text-gray-700">
        {title}
      </h3>
      {children}
    </section>
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

function FormTextarea({ label, value, onChange, rows = 8, disabled = false }) {
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
              label="Type of Govt ID used for adding Name (PAN/Aadhar etc)"
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
              label="Date of Birth"
              type="date"
              value={udfData?.dateOfBirth}
              onChange={(value) => onChange?.("dateOfBirth", value)}
            />

            <UdfInput
              label="Name of previous organization"
              value={udfData?.previousOrganization}
              onChange={(value) => onChange?.("previousOrganization", value)}
            />

            <UdfInput
              label="Total experience e.g 10Y5M"
              value={udfData?.totalExperience}
              onChange={(value) => onChange?.("totalExperience", value)}
            />

            <UdfInput
              label="Relevant experience e.g 10Y5M"
              value={udfData?.relevantExperience}
              onChange={(value) => onChange?.("relevantExperience", value)}
            />

            <UdfSelect
              label="Educational qualification"
              value={udfData?.educationalQualification}
              onChange={(value) =>
                onChange?.("educationalQualification", value)
              }
              options={[
                "B.Tech",
                "B.E",
                "B.Sc",
                "M.Tech",
                "MCA",
                "MBA",
                "Diploma",
                "Other",
              ]}
            />

            <UdfInput
              label="Name of college / University"
              value={udfData?.collegeOrUniversity}
              onChange={(value) => onChange?.("collegeOrUniversity", value)}
            />

            <UdfSelect
              label="Review the details for submission"
              value={udfData?.reviewForSubmission}
              onChange={(value) => onChange?.("reviewForSubmission", value)}
              options={["Yes", "No", "Pending"]}
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
      <label className="mb-1.5 block text-sm font-semibold text-red-600">
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
      <label className="mb-1.5 block text-sm font-semibold text-red-600">
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
