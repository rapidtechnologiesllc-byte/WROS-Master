import { react, useEffect, useRef, useState, useLayoutEffect } from "react";
import { Button, Card, Input, Select, TextArea } from "../components/ui";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { toast } from "react-toastify";
import { updateCandidateStatus } from "../services/api/candidates";
import {
  DatePicker,
  Divider,
  Form,
  Steps,
  Checkbox,
  Table,
  Avatar,
  Collapse,
} from "antd";
import {
  AvatarWrapper,
  BonusButtonDiv,
  CandidateRole,
  CandidateWrapper,
  CheckBoxesDiv,
  ContactPersonDiv,
  Content,
  DateText,
  DetailItem,
  DetailsGrid,
  DocumentPaper,
  DocumentViewer,
  EmptyState,
  FormStepContainer,
  Header,
  HeaderRow,
  IconDiv,
  Label,
  Name,
  NameDiv,
  PreviewLayout,
  PreviewTopBar,
  Role,
  SectionTitle,
  Span,
  StepperDiv,
  Title,
  UserInfo,
  Value,
  Wrapper,
} from "../styles/Pre-onboardingModal";
import { EyeIcon, FileText } from "lucide-react";
import SalaryModal from "./SalaryModal";
import BonusModal from "./BonusModal";
import { DownOutlined } from "@ant-design/icons";
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
import { renderAsync } from "docx-preview";
import { viewDocument } from "../services/api/documents";
import DocxViewer from "../components/ui/DocxViewer";
import { sendMailAttachments } from "../services/api/email";
import OfferConfirmationEmail from "../utils/offerLetterTemplate";
import SignatureModal from "../components/ui/SignatureModal";
import { dayjs } from "dayjs";
import { mapJobFromApi } from "../routes/Approutes";

const PreonboardingModal = ({
  fullName,
  candidate,
  onClose,
  status,
  offerId,
  onSuccess,
}) => {
  const Locations = ["Hyderabad", "Chennai", "Texas", "Remote"];
  const Department = ["PRISM", "Sales", "HR"];
  const [selectLocation, setSelectLocation] = useState();
  const [selectDepartment, setSelectDepartment] = useState();
  const [note, setNote] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [current, setCurrent] = useState(0);
  const [email, setEmail] = useState(candidate?.email);
  const [number, setNumber] = useState(candidate?.phone);
  const [checkedList, setCheckedList] = useState(["pf"]);
  const [salaryTable, setSalaryTable] = useState(false);
  const [bonus, setBonus] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [users, setUsers] = useState([]);
  const [worker, setWorkers] = useState("");
  const [businessUnit, setBusinessUnit] = useState([]);
  const [buValue, setBuValue] = useState("");
  const [salaryText, setSalaryText] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [structureType, setStructureType] = useState("");
  const [offerValidDate, setOfferValidDate] = useState("");
  const [docUrl, setDocUrl] = useState("");
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [offerDocData, setOfferDocData] = useState(null);
  const [docBlob, setDocBlob] = useState(null);
  const [departmentListState, setDepartmentList] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [signaturePng, setSignaturePng] = useState(null);
  const [offerIdData, setOfferIdData] = useState();
  const [salaryData, setSalaryData] = useState();
  const [salaryLoading, setSalaryLoading] = useState(false);
  const previewRef = useRef(null);
  const isRendering = useRef(false);
  const { Panel } = Collapse;
  const [form] = Form.useForm();
  const localName = localStorage.getItem("hrms_user_name");
  const localEmail = localStorage.getItem("hrms_user_email");
  const canProcessOffers = hasPermission("offers", "edit");
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
  const offers = [
    {
      id: 1,
      file: "Vaibhav Shirur.pdf.pdf",
      date: "17 Apr 2026",
      content: "Offer letter details or preview content here",
    },
    {
      id: 2,
      file: "Vaibhav Shirur.pdf.pdf",
      date: "19 Feb 2026",
      content: "Another offer letter details here",
    },
  ];

  useEffect(() => {
    if (offerId) {
      fetchOfferDetails();
    }
  }, [offerId]);

  useEffect(() => {
    const fetchBusinessUnit = async () => {
      try {
        const result = await listBusinessUnits();
        setBusinessUnit(result);
      } catch (err) {
        toast.error(err);
      }
    };
    fetchBusinessUnit();
  }, []);

  useEffect(() => {
    const listingDepartments = async () => {
      try {
        const listResult = await departmentList();
        setDepartmentList(listResult);
      } catch (err) {
        console.log(err);
      }
    };
    listingDepartments();
  }, []);

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      try {
        const refreshed = await getAllJobs();
        if (!isMounted) return;
        const mappedJobs = (refreshed?.jobs || []).map((j) =>
          mapJobFromApi(j, users),
        );
        setJobs(mappedJobs);
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();
    return () => {
      isMounted = false;
    };
  }, []);

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

  const onChange = (value) => {
    setCurrent(value);
  };

  const onDateChange = (date, dateString) => {
    setOfferValidDate(dateString);
  };

  const next = () => {
    if (current < 1) {
      setCurrent(current + 1);
    } else {
      handleGenerateOffer();
    }
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
    console.log(e?.target?.checked);
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
      toast.error("Failed to fetch salary structure:", error);
    } finally {
      setSalaryLoading(false);
    }
  };

  const handleBonusModal = () => {
    setBonus(true);
  };

  const columns = [
    {
      title: "NAME OF CANDIDATE",
      dataIndex: "candidate",
      key: "candidate",
      render: (_, record) => (
        <CandidateWrapper>
          <Avatar style={{ backgroundColor: "#f39c12" }}>{record.name}</Avatar>
          <div>
            <Name>{record.name}</Name>
            <Role>{record.role}</Role>
          </div>
        </CandidateWrapper>
      ),
    },
    {
      title: "ANNUAL SALARY IN WORDS",
      dataIndex: "salary",
      key: "salary",
      render: (text) => (
        <input
          type="text"
          value={salaryText}
          onChange={(e) => {
            setSalaryText(e.target.value);
          }}
          style={{
            border: "1px solid #d9d9d9",
            padding: "6px 10px",
            borderRadius: "4px",
            background: "#fafafa",
            width: "fit-content",
          }}
        />
      ),
    },
  ];

  const data = [
    {
      key: "1",
      initials: "GS",
      name: `${candidate?.name}`,
      role: `${candidate?.jobTitle}`,
      salary: "(INR Thirty Lakhs Only)",
    },
  ];

  const disablePastDates = (current) => {
    if (!current) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return current.toDate() < today;
  };

  const offerLetterHandler = async () => {
    try {
      if (!joiningDate) {
        toast.error("Enter Joining Date");
        return;
      }
      if (!salaryText) {
        toast.error("Enter Salary");
        return;
      }
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
      if (!result) return;
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
        toast.success(generateOfferLetter?.message);
        next();
      }
    } catch (err) {
      toast.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const sendEmailHandler = async () => {
    toast.info("Email will be send to HR Manager for Approval");
    // try {
    //   setIsSaving(true);

    //   const payload = {
    //     offer_id: offerIdData,
    //     candidate_id: candidate?.id,
    //     job_id: selectedJob?.id,
    //   };

    //   const response = await sendOfferApprovalEmail(payload);

    //   if (response?.success) {
    //     toast.success("Email sent successfully to HR Head");
    //     onSuccess?.();
    //     onClose?.();
    //   }
    // } catch (error) {
    //   toast.error(error?.message || "Failed to send email");
    // } finally {
    //   setIsSaving(false);
    // }
  };

  const sendEmailOffer = async (signaturePng) => {
    try {
      const formData = new FormData();
      formData.append("offer_id", offerIdData);
      formData.append("signature", signaturePng);
      const offerApproveApi = await approveOfferLetter(offerIdData, formData);
      if (offerApproveApi?.status === "success") {
        toast.success("Offer Approved and released");
      }
    } catch (error) {
      toast.error("Offer Already Approved");
    }
    //  const emailResult = sendMailAttachments({
    //    email,
    //    subject: `BlitzenX-Employment Offer ${fullName} | ${candidate?.jobTitle} `,
    //    bodyContent: OfferConfirmationEmail(fullName,candidate?.jobTitle,"BlitzenX",selectedJobId,worker,)
    //  });
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
    setSignaturePng(pngData);
    setShowSignatureModal(false);
    await sendEmailOffer(pngData);
  };

  const handleGenerateOfferClick = () => {
    if (current === 1) {
      setShowSignatureModal(true);
    } else {
      offerLetterHandler();
    }
  };

  const fetchOfferDetails = async () => {
    try {
      const data = await getOfferById(offerId);
      setSalaryText(data.salary);
      setJoiningDate(data.joining_date);
      setOfferValidDate(data.offer_expire_date);
      const job = jobs.find((item) => item.id === data.job_id);
      if (job) {
        setSelectedJob(job);
      }
      form.setFieldsValue({
        joiningDate: data.joining_date ? dayjs(data.joining_date) : null,
        offerValidUpto: data.offer_expire_date
          ? dayjs(data.offer_expire_date)
          : null,
      });
    } catch (error) {
      console.error(error);
    }
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
