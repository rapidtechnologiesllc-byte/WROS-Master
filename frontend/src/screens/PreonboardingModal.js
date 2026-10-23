import React, { useCallback, useEffect, useState } from "react";
import { Button, Input, Select } from "../components/ui";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { AlertCircle, CheckCircle, X } from "lucide-react";
import { DatePicker, Form, Steps, Checkbox, Avatar } from "antd";
import {
  BonusButtonDiv,
  CheckBoxesDiv,
  ContactPersonDiv,
  DocumentPaper,
  DocumentViewer,
  EmptyState,
  FormStepContainer,
  IconDiv,
  NameDiv,
  PreviewLayout,
  PreviewTopBar,
  Span,
} from "../styles/Pre-onboardingModal";
import { EyeIcon } from "lucide-react";
import SalaryModal from "./SalaryModal";
import BonusModal from "./BonusModal";
import { getAllJobs } from "../services/api/jobs";
import { departmentList, listBusinessUnits } from "../services/api/rbac";
import {
  approveOfferLetter,
  createOfferLetter,
  generateOfferDoc,
  getOfferById,
  offerLetterById,
  salaryStructure,
} from "../services/api/offerLetters";
import DocxViewer from "../components/ui/DocxViewer";
import SignatureModal from "../components/ui/SignatureModal";
// dayjs only has a default export; the old named import resolved to
// undefined, so pre-filling an existing offer's dates threw at runtime.
import dayjs from "dayjs";
import { mapJobFromApi } from "../utils/jobMappers";

// State for action feedback (replaces toast notifications)
const useActionFeedback = () => {
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const clearError = () => setActionError(null);
  const clearSuccess = () => setActionSuccess(null);

  return { actionError, setActionError, actionSuccess, setActionSuccess, clearError, clearSuccess };
};

const PreonboardingModal = ({
  fullName,
  candidate,
  onClose,
  status,
  offerId,
  onSuccess,
}) => {
  const Locations = ["Hyderabad", "Chennai", "Texas", "Remote"];

  // Action feedback state
  const { actionError, setActionError, actionSuccess, setActionSuccess, clearError, clearSuccess } = useActionFeedback();

  const [selectLocation, setSelectLocation] = useState();
  const [selectDepartment, setSelectDepartment] = useState();
  const [isSaving, setIsSaving] = useState(false);
  const [current, setCurrent] = useState(0);
  const [email, setEmail] = useState(candidate?.email);
  const [number, setNumber] = useState(candidate?.phone);
  const [checkedList, setCheckedList] = useState(["pf"]);
  const [salaryTable, setSalaryTable] = useState(false);
  const [bonus, setBonus] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [worker, setWorkers] = useState("");
  const [businessUnit, setBusinessUnit] = useState([]);
  const [buValue, setBuValue] = useState("");
  const [salaryText, setSalaryText] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [structureType, setStructureType] = useState("");
  const [offerValidDate, setOfferValidDate] = useState("");
  const [docBlob, setDocBlob] = useState(null);
  const [departmentListState, setDepartmentList] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  // job_id of the offer being edited; resolved to a job once jobs have loaded
  const [offerJobId, setOfferJobId] = useState(null);
  const [offerIdData, setOfferIdData] = useState();
  const [salaryData, setSalaryData] = useState();
  const [salaryLoading, setSalaryLoading] = useState(false);
  const [form] = Form.useForm();
  const localName = localStorage.getItem("hrms_user_name");
  const localEmail = localStorage.getItem("hrms_user_email");
  const canProcessOffers = hasPermission("offer-letters", "edit");
  const options = [
    { label: "Eligible for Provident fund (pf)", value: "pf" },
    { label: "Eligible for ESI", value: "esi" },
    { label: "Eligible for LWF", value: "lwf" },
  ];
  const WorkerTypesArray = ["Employee", "Contract", "Interns"];
  const structureTypeArray = [
    "Full time Employee Salary Structure",
    "Intern Salary Structure",
    "Non Guidewire Salary Structure",
  ];

  const fetchOfferDetails = useCallback(async () => {
    try {
      const data = await getOfferById(offerId);
      setSalaryText(data.salary);
      setJoiningDate(data.joining_date);
      setOfferValidDate(data.offer_expire_date);
      setOfferJobId(data.job_id);
      form.setFieldsValue({
        joiningDate: data.joining_date ? dayjs(data.joining_date) : null,
        offerValidUpto: data.offer_expire_date
          ? dayjs(data.offer_expire_date)
          : null,
      });
    } catch (error) {
      console.error("[PreonboardingModal] Failed to load offer details:", error);
      setActionError(
        `Failed to load offer details: ${error?.message || "Unknown error"}`,
      );
    }
  }, [offerId, form, setActionError]);

  useEffect(() => {
    if (offerId) {
      fetchOfferDetails();
    }
  }, [offerId, fetchOfferDetails]);

  // The offer usually arrives before the job list; select its job once both exist.
  useEffect(() => {
    if (!offerJobId || !jobs.length) return;
    const job = jobs.find((item) => item.id === offerJobId);
    if (job) {
      setSelectedJob((prev) => prev || job);
    }
  }, [offerJobId, jobs]);

  useEffect(() => {
    const fetchBusinessUnit = async () => {
      try {
        const result = await listBusinessUnits();
        setBusinessUnit(result);
      } catch (err) {
        console.error("[PreonboardingModal] Failed to load business units:", err);
        setActionError(err?.message || "Failed to load business units");
      }
    };
    fetchBusinessUnit();
  }, [setActionError]);

  useEffect(() => {
    const listingDepartments = async () => {
      try {
        const listResult = await departmentList();
        setDepartmentList(listResult);
      } catch (err) {
        console.error("[PreonboardingModal] Failed to load departments:", err);
        setActionError(err?.message || "Failed to load departments");
      }
    };
    listingDepartments();
  }, [setActionError]);

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        const refreshed = await getAllJobs();
        if (!isMounted) return;
        // No user directory is loaded here; mapJobFromApi only uses it for
        // owner display names.
        const mappedJobs = (refreshed?.jobs || []).map((j) =>
          mapJobFromApi(j, []),
        );
        setJobs(mappedJobs);
      } catch (err) {
        // Throwing here only produced an unhandled promise rejection; surface it.
        console.error("[PreonboardingModal] Failed to load jobs:", err);
        if (isMounted) {
          setActionError(`Failed to load jobs: ${err?.message || "Unknown error"}`);
        }
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, [setActionError]);

  const jobOptions = [
    { label: "Please select job", value: "", disabled: true },
    ...(jobs?.map((job) => ({
      label: job?.title,
      value: job?.id,
    })) || []),
  ];

  const buOptions = [
    { label: "Please select Business Unit", value: "", disabled: true },
    ...(businessUnit?.map((bu) => ({
      label: bu?.name,
      value: bu?.id,
    })) || []),
  ];

  const deptOptions = [
    { label: "Please select department", value: "", disabled: true },
    ...(departmentListState?.map((dept) => ({
      label: dept?.name,
      value: dept?.id,
    })) || []),
  ];

  const onJoiningDateChange = (date, dateString) => {
    setJoiningDate(dateString);
  };

  const onDateChange = (date, dateString) => {
    setOfferValidDate(dateString);
  };

  const next = () => {
    setCurrent((step) => Math.min(step + 1, 1));
  };

  const prev = () => {
    if (current > 0) {
      setCurrent(current - 1);
    }
  };

  const checkboxHandler = (list) => {
    setCheckedList(list);
  };

  const bonusCheckboxHandler = (e) => {
  };

  const salaryTableHandler = async () => {
    try {
      setSalaryTable(true);
      setSalaryLoading(true);
      const payload = {
        employee_name: fullName,
        annual_ctc: parseInt(salaryText),
      };
      const salaryDetails = await salaryStructure(payload);
      setSalaryData(salaryDetails?.salary_structure);
    } catch (error) {
      console.error("[PreonboardingModal] Failed to fetch salary structure:", error);
      setActionError(
        `Failed to fetch salary structure: ${error?.message || "Unknown error"}`,
      );
    } finally {
      setSalaryLoading(false);
    }
  };

  const handleBonusModal = () => {
    setBonus(true);
  };

  const disablePastDates = (current) => {
    if (!current) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return current.toDate() < today;
  };

  const offerLetterHandler = async () => {
    try {
      if (!joiningDate) {
        setActionError("Enter Joining Date");
        return;
      }
      if (!salaryText) {
        setActionError("Enter Salary");
        return;
      }
      clearError();
      setIsSaving(true);
      const payload = {
        candidateId: candidate?.id,
        jobId: selectedJob?.id,
        hiringManagerId: selectedJob?.hiringManager,
        position: selectedJob?.title,
        salary: salaryText,
        joiningDate: joiningDate,
        offer_expire_date: offerValidDate,
      };
      const result = await createOfferLetter(payload);
      if (!result?.id) {
        setActionError("Offer letter was not created");
        return;
      }
      setOfferIdData(result?.id);
      const generateOfferLetter = await generateOfferDoc(result?.id);
      if (generateOfferLetter?.status === "success") {
        const createOfferId = await offerLetterById(result?.id);
        const response = await fetch(createOfferId?.download_url);
        if (!response.ok) {
          throw new Error("Failed to fetch DOCX");
        }
        const blob = await response.blob();
        setDocBlob(blob);
        setActionSuccess(generateOfferLetter?.message);
        next();
      } else {
        setActionError(
          generateOfferLetter?.message || "Failed to generate offer letter document",
        );
      }
    } catch (err) {
      console.error("[PreonboardingModal] Failed to generate offer letter:", err);
      setActionError(err?.message || "Failed to generate offer letter");
    } finally {
      setIsSaving(false);
    }
  };

  const sendEmailHandler = async () => {
    // Generating the letter (step 1, /offer-letter/generate) already set it
    // to AwaitingApproval and emailed the hiring manager; the offer is now
    // in their Pending Approval list. Nothing else to send here.
    setActionSuccess("Offer is with the hiring manager for approval (they were emailed when the letter was generated)");
    onSuccess?.();
    onClose?.();
  };

  const sendEmailOffer = async (signaturePng) => {
    try {
      const formData = new FormData();
      formData.append("offer_id", offerIdData);
      formData.append("signature", signaturePng);
      const offerApproveApi = await approveOfferLetter(offerIdData, formData);
      if (offerApproveApi?.status === "success") {
        setActionSuccess("Offer Approved and released");
      } else {
        setActionError("Failed to approve the offer letter");
      }
    } catch (error) {
      console.error("[PreonboardingModal] Failed to approve offer:", error);
      setActionError(error?.message || "Failed to approve the offer letter");
    }
  };

  const getInitials = (name = "") => {
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) {
      return parts[0][0]?.toUpperCase();
    }
    const first = parts[0][0];
    const last = parts[parts.length - 1][0];

    return (first + last).toUpperCase();
  };

  const handleSignatureSave = async (pngData) => {
    setShowSignatureModal(false);
    await sendEmailOffer(pngData);
  };

  const handleButtonClick = () => {
    if (canProcessOffers) {
      if (current === 0) {
        offerLetterHandler();
      } else if (current === 1) {
        sendEmailHandler();
      }
      return;
    }

    if (current === 1) {
      setShowSignatureModal(true);
    } else {
      offerLetterHandler();
    }
  };

  const renderStepContent = () => {
    switch (current) {
      case 0:
        return (
          <FormStepContainer>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Input label="Personal Email" value={email} onChange={setEmail} />
              <Input
                label="Mobile Number"
                value={number}
                onChange={setNumber}
                disabled={true}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <Span>Job details</Span>
            </div>
            {/* Integrate API for below two dropdowns */}
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Legal Entity"
                value={selectLocation}
                onChange={setSelectLocation}
                options={["BlitzenX Solutions"]}
              />
              <Select
                label="Reporting Manager"
                value={selectDepartment}
                onChange={setSelectDepartment}
                options={[]}
              />
            </div>
            {/* Integrate API for below two dropdowns */}
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Job Title"
                value={selectedJob?.id || ""}
                onChange={(value) => {
                  const job = jobs.find((j) => j.id === value);
                  setSelectedJob(job);
                }}
                options={jobOptions}
              />
              <Select
                label="Worker Type"
                value={worker}
                onChange={(value) => setWorkers(value)}
                options={WorkerTypesArray}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Select Location"
                value={selectLocation}
                onChange={setSelectLocation}
                options={Locations}
              />
              <Select
                label="Select Department"
                value={selectDepartment}
                onChange={(value) => setSelectDepartment(value)}
                options={deptOptions}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Select BU (optional)"
                value={buValue}
                onChange={(value) => setBuValue(value)}
                options={buOptions}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <Span>Offer details</Span>
            </div>
            <Form form={form}>
              <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
                <Form.Item
                  label="Joining Date"
                  name="joiningDate"
                  rules={[
                    {
                      required: true,
                      message: "Please select joining date",
                    },
                  ]}
                >
                  <DatePicker
                    format="YYYY-MM-DD"
                    onChange={onJoiningDateChange}
                    disabledDate={disablePastDates}
                  />
                </Form.Item>
                <Form.Item
                  label="Offer Valid Upto"
                  name="offerValidUpto"
                  rules={[
                    {
                      required: true,
                      message: "Offer valid upto date is required",
                    },
                  ]}
                >
                  <DatePicker onChange={onDateChange} format="YYYY-MM-DD" />
                </Form.Item>
              </div>
            </Form>
            {salaryTable ? (
              <SalaryModal
                onClose={() => setSalaryTable(false)}
                salaryDataProp={salaryData}
                loading={salaryLoading}
              />
            ) : null}
            {bonus ? <BonusModal onClose={() => setBonus(false)} /> : null}
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <Span>Compensation</Span>
            </div>
            <div className="px-4 mt-4">
              <CheckBoxesDiv>
                <Checkbox.Group
                  options={options}
                  onChange={checkboxHandler}
                  value={checkedList}
                />
              </CheckBoxesDiv>
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Pay Group"
                value={selectLocation}
                onChange={setSelectLocation}
                options={["BlitzenX Solution Private Limited"]}
              />
              <Select
                label="Remuneration Type"
                value={selectDepartment}
                onChange={setSelectDepartment}
                options={["Annual"]}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Input
                label="Salary (Annual Basis in INR)"
                value={salaryText}
                onChange={setSalaryText}
              />
              <Select
                label="Select structure type"
                value={structureType}
                onChange={(value) => setStructureType(value)}
                options={structureTypeArray}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <IconDiv onClick={salaryTableHandler}>
                <EyeIcon color="#0b68cb" />
                <span>View salary structure</span>
              </IconDiv>
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <Span>Variable / Bonus components</Span>
              Add bonus types / bonus components to this offer
            </div>
            <div className="px-4 mt-4">
              <CheckBoxesDiv>
                <Checkbox
                  value={"bonus"}
                  name="bonus"
                  onChange={bonusCheckboxHandler}
                >
                  Bonus amount is included in the new salary
                </Checkbox>
              </CheckBoxesDiv>
            </div>
            <div className="px-4 mt-1 grid gap-3 md:grid-cols-1">
              <BonusButtonDiv onClick={handleBonusModal}>
                <div>+</div>
                <div>Add</div>
              </BonusButtonDiv>
            </div>
          </FormStepContainer>
        );
      case 1:
        return (
          <PreviewLayout>
            <PreviewTopBar>
              <div className="grid gap-4 md:grid-cols-2 w-full">
                <span>Contact person for this Offer</span>
                <ContactPersonDiv>
                  <Avatar size={48}>{getInitials(localName)}</Avatar>
                  <NameDiv>
                    <span>{localName}</span>
                    <span>{localEmail}</span>
                  </NameDiv>
                </ContactPersonDiv>
              </div>
            </PreviewTopBar>
            <DocumentViewer>
              {docBlob ? (
                <DocumentPaper>
                  <DocxViewer blob={docBlob} />
                </DocumentPaper>
              ) : (
                <EmptyState>No document available</EmptyState>
              )}
            </DocumentViewer>
          </PreviewLayout>
        );
      default:
        return null;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex justify-center items-center p-4"
      role="dialog"
      aria-modal="true"
    >
      {/* Error Banner */}
      {actionError && (
        <div className="absolute top-4 left-4 right-4 rounded-lg border border-red-200 bg-red-50 p-4 flex items-center justify-between z-50">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <p className="text-sm text-red-700">{actionError}</p>
          </div>
          <button
            onClick={clearError}
            className="text-red-600 hover:text-red-700 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Success Banner */}
      {actionSuccess && (
        <div className="absolute top-4 left-4 right-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-between z-50">
          <div className="flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-emerald-600 flex-shrink-0" />
            <p className="text-sm text-emerald-700">{actionSuccess}</p>
          </div>
          <button
            onClick={clearSuccess}
            className="text-emerald-600 hover:text-emerald-700 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="w-full max-w-6xl h-[95vh] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        <div className="shrink-0 border-b bg-white px-6 py-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                Initial Pre-Onboarding Process
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Preboarding and Offer Process will be initiated for{" "}
                <span className="font-semibold text-black">{fullName}</span>
              </p>
            </div>
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
          <div className="mt-6">
            <Steps
              current={current}
              items={[{ title: "Job Details" }, { title: "Preview & Approve" }]}
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          {renderStepContent()}
        </div>
        <div className="shrink-0 border-t bg-white px-6 py-4 flex justify-end gap-3">
          <Button variant="secondary" onClick={prev} disabled={current === 0}>
            Back
          </Button>
          <Button onClick={handleButtonClick} disabled={isSaving}>
            {isSaving
              ? "Processing..."
              : canProcessOffers
                ? current === 0
                  ? "Next"
                  : "Send Email"
                : current === 1
                  ? "Generate Offer"
                  : "Continue"}
          </Button>
        </div>
      </div>
      <SignatureModal
        isOpen={showSignatureModal}
        onClose={() => setShowSignatureModal(false)}
        onSave={handleSignatureSave}
      />
    </div>
  );
};

export default PreonboardingModal;
