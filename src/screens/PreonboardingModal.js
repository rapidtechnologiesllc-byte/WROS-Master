import { react, useEffect, useState } from "react";
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
  Container,
  Content,
  DateText,
  DetailItem,
  DetailsGrid,
  Header,
  HeaderRow,
  IconDiv,
  Label,
  Name,
  PreviewBox,
  Role,
  ScrollContainer,
  Section,
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
  const [checkedList, setCheckedList] = useState([]);
  const [salaryTable, setSalaryTable] = useState(false);
  const [bonus, setBonus] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [users, setUsers] = useState([]);
  const [worker, setWorkers] = useState("");
  const [businessUnit, setBusinessUnit] = useState([]);
  const [buValue, setBuValue] = useState("");
  const [salaryText, setSalaryText] = useState("");
  const { Panel } = Collapse;
  const options = [
    { label: "Eligible for Provident fund (pf)", value: "pf" },
    { label: "Eligible for ESI", value: "esi" },
    { label: "Eligible for LWF", value: "lwf" },
  ];
  const WorkerTypesArray = ["Employee", "Contract", "Interns"];
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

  const onChange = (value) => {
    setCurrent(value);
  };

  const onDateChange = (date, dateString) => {
    console.log(date, dateString);
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

  const renderStepContent = () => {
    switch (current) {
      case 0:
        return (
          <>
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
                <DatePicker onChange={onDateChange} />
              </Form.Item>
              <Form.Item
                label="Offer Valid Upto"
                name="offerValidUpto"
                dependencies={["joiningDate"]}
                rules={[
                  {
                    required: true,
                    message: "Please select offer valid upto date",
                  },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      const joiningDate = getFieldValue("joiningDate");
                      if (!value || !joiningDate) {
                        return Promise.resolve();
                      }
                      if (value.isBefore(joiningDate, "day")) {
                        return Promise.resolve();
                      }
                      return Promise.reject(
                        new Error(
                          "Offer Valid Upto must be before Joining Date",
                        ),
                      );
                    },
                  }),
                ]}
              >
                <DatePicker onChange={onDateChange} />
              </Form.Item>
            </div>
            {salaryTable ? (
              <SalaryModal onClose={() => setSalaryTable(false)} />
            ) : null}
            {bonus ? <BonusModal onClose={() => setBonus(false)} /> : null}
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <Span>Compensation</Span>
            </div>
            <div className="px-4 mt-4">
              <CheckBoxesDiv>
                <Checkbox.Group options={options} onChange={checkboxHandler} />
              </CheckBoxesDiv>
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Pay Group"
                value={selectLocation}
                onChange={setSelectLocation}
                options={[]}
              />
              <Select
                label="Remuneration Type"
                value={selectDepartment}
                onChange={setSelectDepartment}
                options={[]}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Select
                label="Salary (Annual Basis)"
                value={selectLocation}
                onChange={setSelectLocation}
                options={[]}
              />
              <Select
                label="Select structure type"
                value={selectDepartment}
                onChange={setSelectDepartment}
                options={[]}
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
          </>
        );
      case 1:
        return (
          <Container>
            <ScrollContainer>
              <Section>
                <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
                  <Select
                    label="Select a contact person for this offer"
                    options={[]}
                    onChange={() => {}}
                  />
                  <div>Varun</div>
                </div>
              </Section>
              <Section>
                <Title>Template preview</Title>
                <PreviewBox>Document Preview Placeholder</PreviewBox>
              </Section>
            </ScrollContainer>
          </Container>
        );
      case 3:
        return (
          <Container>
            <ScrollContainer>
              
              <Section>
                <Title>Template preview</Title>
                <PreviewBox>Document Preview Placeholder</PreviewBox>
              </Section>
            </ScrollContainer>
          </Container>
        );
      case 4:
        return (
          <>
            <Wrapper>
              <Header>
                <AvatarWrapper>
                  <Avatar size={48} style={{ backgroundColor: "#f59e0b" }}>
                    VS
                  </Avatar>

                  <UserInfo>
                    <Name>{candidate?.name}</Name>
                    <CandidateRole>
                      Applied for {candidate?.jobTitle}
                    </CandidateRole>
                  </UserInfo>
                </AvatarWrapper>
              </Header>

              <Divider style={{ margin: "20px 0" }} />

              <SectionTitle>Basic Details</SectionTitle>

              <DetailsGrid>
                <DetailItem>
                  <Label>Email ID</Label>
                  <Value title={"shirurvaibhav@gmail.com"}>
                    {candidate?.email}
                  </Value>
                </DetailItem>

                <DetailItem>
                  <Label>Phone number</Label>
                  <Value>{candidate?.phone}</Value>
                </DetailItem>

                <DetailItem>
                  <Label>Recruiter</Label>
                  <Value>Onboarding Team</Value>
                </DetailItem>

                <DetailItem>
                  <Label>Department</Label>
                  <Value>
                    PRISM — Product Integration & Systems Management
                  </Value>
                </DetailItem>

                <DetailItem>
                  <Label>Location</Label>
                  <Value>Remote</Value>
                </DetailItem>

                <DetailItem>
                  <Label>Offer template</Label>
                  <Value>Default Offer Letter</Value>
                </DetailItem>

                <DetailItem>
                  <Label>Joining date</Label>
                  <Value>15 Jun 2026</Value>
                </DetailItem>

                <DetailItem>
                  <Label>Valid upto</Label>
                  <Value>09 May 2026</Value>
                </DetailItem>
              </DetailsGrid>
            </Wrapper>
            <Wrapper>
              <Title>Previous Offer Letter</Title>
              <StyledCollapse
                accordion
                bordered={false}
                expandIcon={({ isActive }) => (
                  <DownOutlined rotate={isActive ? 180 : 0} />
                )}
              >
                {offers?.map((offer) => (
                  <Panel
                    key={offer?.id}
                    header={
                      <HeaderRow>
                        <FileText title={offer?.file}>{offer?.file}</FileText>
                        <DateText>On {offer?.date}</DateText>
                      </HeaderRow>
                    }
                  >
                    <Content>{offer?.content}</Content>
                  </Panel>
                ))}
              </StyledCollapse>
            </Wrapper>
          </>
        );
      default:
        return null;
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex justify-center bg-black/40 p-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <div className="w-full max-w-4xl max-h-[75vh] flex flex-col">
          <Card
            title="Initia Pre-Onboarding Process"
            bodyClassName="px-2 py-4 flex flex-col overflow-hidden max-h-[75vh]"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div>
              <span className="px-4">
                Preonboarding and Offer Process will be initiated for{" "}
                <span style={{ fontSize: "16px", fontWeight: "bold" }}>
                  {fullName}
                </span>
              </span>
            </div>

            <StepperDiv>
              <Steps
                current={current}
                onChange={onChange}
                items={[
                  { title: "Job Details" },
                  { title: "Preview & Approve" },
                ]}
              />
            </StepperDiv>
            <div
              className="mt-6 flex-1 overflow-y-auto pr-2"
              style={{ marginTop: 24 }}
            >
              {renderStepContent()}
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button
                variant="secondary"
                onClick={prev}
                disabled={current === 0}
              >
                Back
              </Button>
              <Button onClick={next} disabled={isSaving}>
                {isSaving
                  ? "Saving..."
                  : current === 1
                    ? "Generate Offer"
                    : "Continue"}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
};

export default PreonboardingModal;
