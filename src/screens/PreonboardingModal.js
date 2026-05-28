import { react, useEffect, useRef, useState, useLayoutEffect } from "react";
import { Button, Card, Input, Select, TextArea } from "../components/ui";
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
  PreviewLayout,
  PreviewTopBar,
  Role,
  SectionTitle,
  Span,
  StepperDiv,
  StyledCollapse,
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
import { mapJobFromApi } from "../App";
import { listBusinessUnits } from "../services/api/rbac";
import {
  createOfferLetter,
  generateOfferDoc,
  offerLetterById,
} from "../services/api/offerLetters";
import { renderAsync } from "docx-preview";
import { viewDocument } from "../services/api/documents";
import DocxViewer from "../components/ui/DocxViewer";
import { sendMailAttachments } from "../services/api/email";
import OfferConfirmationEmail from "../utils/offerLetterTemplate";

const PreonboardingModal = ({
  fullName,
  candidate,
  onClose,
  status,
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
  const previewRef = useRef(null);
  const isRendering = useRef(false);
  const { Panel } = Collapse;
  const [form] = Form.useForm();
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

  const onJoiningDateChange = (date, dateString) => {
    setJoiningDate(dateString);
    if (date) {
      const validDate = date.add(7, "day");
      setOfferValidDate(validDate.format("YYYY-MM-DD"));
      form.setFieldsValue({
        joiningDate: date,
        offerValidUpto: validDate,
      });
    }
  };

  const onChange = (value) => {
    setCurrent(value);
  };

  const onDateChange = (date, dateString) => {
    setJoiningDate(dateString);
  };
  //REQUIRE THIS FOR IMPLEMENTING OFFER FLOW
  // const handleSaveOnly = async () => {
  //   try {
  //     const updateStatus = await updateCandidateStatus(candidate?.id, {
  //       status: "Active",
  //       pipeline_status: status,
  //     });
  //     if (updateStatus?.status === "success") {
  //       toast.success(
  //         `Candidate ${updateStatus?.data?.candidate_name} moved to ${status}`,
  //       );
  //       onSuccess?.(status);
  //     }
  //   } catch (err) {
  //     toast.error("Error", err.message);
  //   } finally {
  //     onClose();
  //   }
  // };

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

  const salaryTableHandler = () => {
    setSalaryTable(true);
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

  const offerLetterHandler = async () => {
    try {
      const payload = {
        candidateId: candidate?.id,
        jobId: selectedJobId,
        hiringManagerId: "adae1bd3-4118-46ea-a20e-604cd90fe982",
        reportingManagerId: "USER-e4521331-313d-4c1c-a299-f55f41ff2187",
        position: "Guidewire Developer",
        salary: salaryText,
        joiningDate: joiningDate,
        offer_expire_date: offerValidDate,
      };
      const result = await createOfferLetter(payload);
      if (result) {
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
      }
    } catch (err) {
      toast.error(err);
    }
  };

  const disablePastDates = (current) => {
    if (!current) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return current.toDate() < today;
  };

  const sendEmailOffer = async () => {
    console.log("function trigger");
    //  const emailResult = sendMailAttachments({
    //    email,
    //    subject: `BlitzenX-Employment Offer ${fullName} | ${candidate?.jobTitle} `,
    //    bodyContent: OfferConfirmationEmail(fullName,candidate?.jobTitle,"BlitzenX",selectedJobId,worker,)
    //  });
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
                value={selectedJobId}
                onChange={(value) => setSelectedJobId(value)}
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
                onChange={setSelectDepartment}
                options={Department}
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
                  <DatePicker
                    onChange={onDateChange}
                    format="YYYY-MM-DD"
                    inputReadOnly
                    open={false}
                  />
                </Form.Item>
              </div>
            </Form>
            {salaryTable ? (
              <SalaryModal onClose={() => setSalaryTable(false)} />
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
                <Select
                  label="Select a contact person for this offer"
                  options={[]}
                  onChange={() => {}}
                />
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
              onChange={onChange}
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
          <Button
            onClick={current === 1 ? sendEmailOffer : offerLetterHandler}
            disabled={isSaving}
          >
            {isSaving
              ? "Saving..."
              : current === 1
                ? "Generate Offer"
                : "Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default PreonboardingModal;
