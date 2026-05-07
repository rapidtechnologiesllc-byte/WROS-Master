import { react, useState } from "react";
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
} from "antd";
import {
  AvatarWrapper,
  BonusButtonDiv,
  CandidateRole,
  CandidateWrapper,
  CheckBoxesDiv,
  Container,
  DetailItem,
  DetailsGrid,
  Header,
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
  Title,
  UserInfo,
  Value,
  Wrapper,
} from "../styles/Pre-onboardingModal";
import { EyeIcon } from "lucide-react";
import SalaryModal from "./SalaryModal";
import BonusModal from "./BonusModal";

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
  const content = "This is a content.";
  const options = [
    { label: "Eligible for Provident fund (pf)", value: "pf" },
    { label: "Eligible for ESI", value: "esi" },
    { label: "Eligible for LWF", value: "lwf" },
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
    if (current < 5) {
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
          <Avatar style={{ backgroundColor: "#f39c12" }}>
            {record.initials}
          </Avatar>
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
        <div
          style={{
            border: "1px solid #d9d9d9",
            padding: "6px 10px",
            borderRadius: "4px",
            background: "#fafafa",
            width: "fit-content",
          }}
        >
          {text}
        </div>
      ),
    },
  ];

  const data = [
    {
      key: "1",
      initials: "GS",
      name: "Gnanagiri Shanmugam",
      role: "Director",
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
                options={[]}
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
                value={selectLocation}
                onChange={setSelectLocation}
                options={[]}
              />
              <Select
                label="Worker Type"
                value={selectDepartment}
                onChange={setSelectDepartment}
                options={[]}
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
                value={selectLocation}
                onChange={setSelectLocation}
                options={[]}
              />
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-1">
              <Span>Offer details</Span>
            </div>
            <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
              <Form.Item label="Joining Date" name="date">
                <DatePicker onChange={onDateChange} />
              </Form.Item>
              <Form.Item label="Offer Valid Upto" name="date">
                <DatePicker onChange={onDateChange} />
              </Form.Item>
            </div>
          </>
        );
      case 1:
        return (
          <>
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
      case 2:
        return (
          <Container>
            <ScrollContainer>
              <Section>
                <Title>Fill in the form data</Title>
                <Table columns={columns} dataSource={data} />
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
                <div className="px-4 mt-4 grid gap-3 md:grid-cols-2">
                  <Select
                    label="Select a contact person for this offer"
                    options={[]}
                    onChange={() => {}}
                  />
                </div>
              </Section>
              <Section>
                <Title>Template preview</Title>
                <PreviewBox>Document Preview Placeholder</PreviewBox>
              </Section>
            </ScrollContainer>
          </Container>
        );
      case 4:
        return (
          <Wrapper>
            <Header>
              <AvatarWrapper>
                <Avatar size={48} style={{ backgroundColor: "#f59e0b" }}>
                  VS
                </Avatar>

                <UserInfo>
                  <Name>Vaibhav Shirur</Name>
                  <CandidateRole>Applied for Guidewire Developer</CandidateRole>
                </UserInfo>
              </AvatarWrapper>
            </Header>

            <Divider style={{ margin: "20px 0" }} />

            <SectionTitle>Basic Details</SectionTitle>

            <DetailsGrid>
              <DetailItem>
                <Label>Email ID</Label>
                <Value>shirurvaibhav@gmail.com</Value>
              </DetailItem>

              <DetailItem>
                <Label>Phone number</Label>
                <Value>+91-9902215623</Value>
              </DetailItem>

              <DetailItem>
                <Label>Recruiter</Label>
                <Value>Onboarding Team</Value>
              </DetailItem>

              <DetailItem>
                <Label>Department</Label>
                <Value>PRISM — Product Integration & Systems Management</Value>
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
        <div className="w-full max-w-4xl max-h-[80vh] flex flex-col">
          <Card
            title="Initia Pre-Onboarding Process"
            bodyClassName="px-2 py-4"
            right={
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            }
          >
            <div>
              <span className="px-4">Preonboarding will be initiated for</span>
              <span style={{ fontSize: "16px", fontWeight: "bold" }}>
                {fullName}
              </span>
            </div>

            <StepperDiv>
              <Steps
                current={current}
                onChange={onChange}
                items={[
                  { title: "Job Details" },
                  { title: "Compensation" },
                  { title: "Offer Details" },
                  { title: "Preview & Send" },
                  { title: "Finalize" },
                ]}
              />
            </StepperDiv>
            <div style={{ marginTop: 24 }}>{renderStepContent()}</div>
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
                  : current === 4
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
