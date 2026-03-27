// Interview status, panels, feedback, and Microsoft tools view.
import { useEffect, useMemo, useState } from "react";
import { ClipboardCheck } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge, Table, TextArea } from "../components/ui";
import {
  deleteInterviewFeedback,
  deleteInterview,
  deletePanelMember,
  deleteInterviewPanel,
  getFeedbackById,
  getInterviewById,
  getInterviewPanel,
  getInterviewPanels,
  getPanelMembers,
  submitInterviewFeedback,
  updateInterviewFeedback
} from "../services/api/interviews";
import { getAllUsers } from "../services/api/users";
import {
  getMicrosoftSigninUrl,
  getMyMeetings,
  getServiceCalendarEvents,
  listSharepointDrives,
  sendGraphMail,
  testSharepointConnection
} from "../services/api/msgraph";

export default function InterviewStatus({
  interviews,
  candidates,
  onMarkCompleted,
  onRefreshInterviews,
  onGoApproval
}) {
  // Map candidate IDs to detail objects for fast lookup in table rows.
  const cMap = useMemo(
    () => Object.fromEntries(candidates.map((c) => [c.id, c])),
    [candidates]
  );
  const formatDate = (value) => {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString();
  };
  const [panelList, setPanelList] = useState([]);
  const [activePanelId, setActivePanelId] = useState(null);
  const [panelDetails, setPanelDetails] = useState(null);
  const [panelMembers, setPanelMembers] = useState([]);
  const [panelNotice, setPanelNotice] = useState("");
  const [isLoadingPanels, setIsLoadingPanels] = useState(false);
  const [interviewerOptions, setInterviewerOptions] = useState([]);
  const [feedbackForm, setFeedbackForm] = useState({
    interviewId: null,
    feedbackId: "",
    interviewerId: "",
    technicalScore: "",
    communicationScore: "",
    problemSolvingScore: "",
    cultureFitScore: "",
    recommendation: "Hire",
    comments: ""
  });

  const UPDATE_RECOMMENDATION_OPTIONS = ["Hire", "Hold", "Reject"]; // backend: update feedback
  const SUBMIT_RECOMMENDATION_OPTIONS = [
    "No Hire",
    "Not sure",
    "Average",
    "Hire",
    "Must Hire"
  ]; // backend: submit feedback

  const isUpdatingFeedback = Boolean(feedbackForm.feedbackId);
  const recommendationOptions = isUpdatingFeedback
    ? UPDATE_RECOMMENDATION_OPTIONS
    : SUBMIT_RECOMMENDATION_OPTIONS;

  useEffect(() => {
    const options = isUpdatingFeedback
      ? UPDATE_RECOMMENDATION_OPTIONS
      : SUBMIT_RECOMMENDATION_OPTIONS;
    setFeedbackForm((prev) => {
      if (options.includes(prev.recommendation)) return prev;
      return { ...prev, recommendation: options[0] };
    });
  }, [isUpdatingFeedback]);
  const [feedbackNotice, setFeedbackNotice] = useState("");
  const [interviewDetail, setInterviewDetail] = useState(null);
  const [feedbackDetail, setFeedbackDetail] = useState(null);
  const [meetings, setMeetings] = useState([]);
  const [serviceMeetings, setServiceMeetings] = useState([]);
  const [serviceEmail, setServiceEmail] = useState("");
  const [serviceStart, setServiceStart] = useState("");
  const [serviceEnd, setServiceEnd] = useState("");
  const [meetingsNotice, setMeetingsNotice] = useState("");
  const [mailForm, setMailForm] = useState({
    to: "",
    subject: "",
    bodyText: ""
  });
  const [mailNotice, setMailNotice] = useState("");
  const [sharepointStatus, setSharepointStatus] = useState(null);
  const [sharepointDrives, setSharepointDrives] = useState([]);
  const [sharepointNotice, setSharepointNotice] = useState("");

  useEffect(() => {
    let isMounted = true;
    const loadUsers = async () => {
      try {
        // Load interviewer list for feedback form.
        const res = await getAllUsers();
        if (!isMounted) return;
        const users = (res?.users || []).map((u) => ({
          id: u.user_id,
          name: u.user_name || u.user_email,
          email: u.user_email
        }));
        setInterviewerOptions(users);
        if (!feedbackForm.interviewerId && users.length) {
          setFeedbackForm((prev) => ({ ...prev, interviewerId: users[0].id }));
        }
      } catch (err) {
        if (!isMounted) return;
        setFeedbackNotice(err.message || "Failed to load interviewer list.");
      }
    };
    loadUsers();
    return () => {
      isMounted = false;
    };
  }, [feedbackForm.interviewerId]);

  const loadPanels = async () => {
    setPanelNotice("");
    setIsLoadingPanels(true);
    try {
      const res = await getInterviewPanels();
      setPanelList(res || []);
    } catch (err) {
      setPanelNotice(err.message || "Failed to load panels.");
    } finally {
      setIsLoadingPanels(false);
    }
  };

  const openPanel = async (panelId) => {
    setPanelNotice("");
    setActivePanelId(panelId);
    try {
      const [panel, members] = await Promise.all([
        getInterviewPanel(panelId),
        getPanelMembers(panelId)
      ]);
      setPanelDetails(panel);
      setPanelMembers(members || []);
    } catch (err) {
      setPanelNotice(err.message || "Failed to load panel details.");
    }
  };

  const resetFeedback = () => {
    setFeedbackForm({
      interviewId: null,
      feedbackId: "",
      interviewerId: interviewerOptions[0]?.id || "",
      technicalScore: "",
      communicationScore: "",
      problemSolvingScore: "",
      cultureFitScore: "",
      recommendation: "Hire",
      comments: ""
    });
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Interview Panels"
        icon={<ClipboardCheck className="h-4 w-4" />}
        right={
          <Button variant="secondary" onClick={loadPanels} disabled={isLoadingPanels}>
            {isLoadingPanels ? "Loading..." : "Load Panels"}
          </Button>
        }
      >
        <div className="grid gap-4 md:grid-cols-[1fr,2fr]">
          <div className="space-y-2">
            {panelList.length === 0 ? (
              <div className="text-sm text-gray-500">No panels loaded.</div>
            ) : (
              panelList.map((panel) => (
                <button
                  key={panel.id}
                  onClick={() => openPanel(panel.id)}
                  className="w-full rounded-xl border bg-white px-3 py-2 text-left text-sm hover:bg-gray-50"
                >
                  <div className="font-semibold">{panel.round_name}</div>
                  <div className="text-xs text-gray-500">
                    Candidate: {panel.candidate_name}
                  </div>
                </button>
              ))
            )}
          </div>
          <div className="rounded-xl border bg-white p-3 text-sm">
            {panelDetails ? (
              <>
                <div className="font-semibold">Panel {panelDetails.id}</div>
                <div className="text-xs text-gray-500">
                  Round: {panelDetails.round_name}
                </div>
                <div className="text-xs text-gray-500">
                  Candidate: {panelDetails.candidate_name}
                </div>
                <div className="mt-2 text-xs font-semibold text-gray-600">Members</div>
                {panelMembers.length === 0 ? (
                  <div className="text-xs text-gray-500">No members found.</div>
                ) : (
                  <ul className="mt-1 space-y-1">
                    {panelMembers.map((m) => (
                      <li key={m.id} className="flex items-center justify-between gap-2">
                        <span>
                          {m.interviewer_name} ({m.interviewer_id})
                        </span>
                        <Button
                          variant="danger"
                          onClick={async () => {
                            const ok = window.confirm(
                              `Remove member ${m.interviewer_name || m.interviewer_id}?`
                            );
                            if (!ok) return;
                            try {
                              await deletePanelMember(m.id);
                              const members = await getPanelMembers(panelDetails.id);
                              setPanelMembers(members || []);
                              setPanelNotice("Panel member removed.");
                            } catch (err) {
                              setPanelNotice(err.message || "Failed to remove panel member.");
                            }
                          }}
                        >
                          Remove
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-3">
                  <Button
                    variant="danger"
                    onClick={async () => {
                      const ok = window.confirm(
                        `Delete panel ${panelDetails.id}? This removes interviews and feedback.`
                      );
                      if (!ok) return;
                      try {
                        await deleteInterviewPanel(panelDetails.id);
                        setPanelDetails(null);
                        setPanelMembers([]);
                        setActivePanelId(null);
                        await loadPanels();
                        if (onRefreshInterviews) {
                          await onRefreshInterviews();
                        }
                      } catch (err) {
                        setPanelNotice(err.message || "Failed to delete panel.");
                      }
                    }}
                  >
                    Delete Panel
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-gray-500">Select a panel to view details.</div>
            )}
          </div>
        </div>
        {panelNotice ? (
          <div className="mt-2 text-xs text-gray-500">{panelNotice}</div>
        ) : null}
      </Card>

      <Card
        title="Interview Status"
        icon={<ClipboardCheck className="h-4 w-4" />}
        right={
          <Button variant="secondary" onClick={onGoApproval}>
            Go to approval
          </Button>
        }
      >
        <Table
          columns={[
            { key: "id", header: "Interview" },
            { key: "candidate", header: "Candidate" },
            { key: "panel", header: "Panel" },
            { key: "start", header: "Start" },
            { key: "end", header: "End" },
            { key: "meeting", header: "Meeting" },
            { key: "status", header: "Status" },
            { key: "actions", header: "Actions" }
          ]}
          rows={interviews.map((i) => ({
            id: <span className="font-semibold">{i.id}</span>,
            candidate: cMap[i.candidateId]?.name || "Unknown",
            panel: i.panelRoundName
              ? `${i.panelRoundName} (${i.panelId || "N/A"})`
              : i.panelId || "N/A",
            start: formatDate(i.startTime),
            end: formatDate(i.endTime),
            meeting: i.meetingLink ? (
              <a href={i.meetingLink} target="_blank" rel="noreferrer">
                Open link
              </a>
            ) : (
              "-"
            ),
            status: <StatusBadge status={i.status} />,
            actions: (
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  onClick={() => onMarkCompleted(i)}
                  disabled={i.status === "Completed"}
                >
                  Mark completed
                </Button>
                <Button
                  variant="secondary"
                  onClick={() =>
                    setFeedbackForm((prev) => ({
                      ...prev,
                      interviewId: i.id
                    }))
                  }
                >
                  Feedback
                </Button>
                <Button
                  variant="secondary"
                  onClick={async () => {
                    try {
                      const detail = await getInterviewById(i.id);
                      setInterviewDetail(detail || null);
                      setFeedbackNotice("");
                    } catch (err) {
                      setFeedbackNotice(err.message || "Failed to load interview details.");
                    }
                  }}
                >
                  View Details
                </Button>
                <Button
                  variant="danger"
                  onClick={async () => {
                    const ok = window.confirm(`Delete interview ${i.id}?`);
                    if (!ok) return;
                    try {
                      await deleteInterview(i.id);
                      if (onRefreshInterviews) {
                        await onRefreshInterviews();
                      }
                    } catch (err) {
                      setFeedbackNotice(err.message || "Failed to delete interview.");
                    }
                  }}
                >
                  Delete
                </Button>
              </div>
            )
          }))}
        />
        {interviewDetail ? (
          <div className="mt-3 rounded-xl border bg-slate-50 p-3 text-xs text-gray-700">
            <div className="mb-1 font-semibold">Interview Detail</div>
            <div>ID: {interviewDetail.id}</div>
            <div>Panel ID: {interviewDetail.panel_id}</div>
            <div>Candidate ID: {interviewDetail.candidate_id}</div>
            <div>Start: {formatDate(interviewDetail.start_time)}</div>
            <div>End: {formatDate(interviewDetail.end_time)}</div>
            <div>Status: {interviewDetail.status || "-"}</div>
            <div>
              Meeting: {interviewDetail.meeting_link ? String(interviewDetail.meeting_link) : "-"}
            </div>
          </div>
        ) : null}
      </Card>

      <Card title="Interview Feedback" icon={<ClipboardCheck className="h-4 w-4" />}>
        <div className="grid gap-3 md:grid-cols-2">
          <Input
            label="Interview ID"
            value={feedbackForm.interviewId || ""}
            onChange={(value) =>
              setFeedbackForm((prev) => ({
                ...prev,
                interviewId: value ? Number(value) : null
              }))
            }
          />
          <Input
            label="Feedback ID (for update)"
            value={feedbackForm.feedbackId}
            onChange={(value) =>
              setFeedbackForm((prev) => ({ ...prev, feedbackId: value }))
            }
          />
          <Select
            label="Interviewer"
            value={feedbackForm.interviewerId}
            onChange={(value) =>
              setFeedbackForm((prev) => ({ ...prev, interviewerId: value }))
            }
            options={["", ...interviewerOptions.map((u) => u.id)]}
          />
          <Select
            label="Recommendation"
            value={feedbackForm.recommendation}
            onChange={(value) =>
              setFeedbackForm((prev) => ({ ...prev, recommendation: value }))
            }
            options={recommendationOptions}
          />
          <Input
            label="Technical Score (0-10)"
            value={feedbackForm.technicalScore}
            onChange={(value) =>
              setFeedbackForm((prev) => ({ ...prev, technicalScore: value }))
            }
          />
          <Input
            label="Communication Score (0-10)"
            value={feedbackForm.communicationScore}
            onChange={(value) =>
              setFeedbackForm((prev) => ({ ...prev, communicationScore: value }))
            }
          />
          <Input
            label="Problem Solving Score (0-10)"
            value={feedbackForm.problemSolvingScore}
            onChange={(value) =>
              setFeedbackForm((prev) => ({ ...prev, problemSolvingScore: value }))
            }
          />
          <Input
            label="Culture Fit Score (0-10)"
            value={feedbackForm.cultureFitScore}
            onChange={(value) =>
              setFeedbackForm((prev) => ({ ...prev, cultureFitScore: value }))
            }
          />
          <div className="md:col-span-2">
            <Input
              label="Comments"
              value={feedbackForm.comments}
              onChange={(value) =>
                setFeedbackForm((prev) => ({ ...prev, comments: value }))
              }
            />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            onClick={async () => {
              if (!feedbackForm.interviewId) {
                setFeedbackNotice("Interview ID is required.");
                return;
              }
              if (!feedbackForm.interviewerId) {
                setFeedbackNotice("Interviewer ID is required.");
                return;
              }
              if (!interviewerOptions.some((u) => u.id === feedbackForm.interviewerId)) {
                setFeedbackNotice("Selected interviewer is not in backend user list.");
                return;
              }
              try {
                if (feedbackForm.feedbackId) {
                  await updateInterviewFeedback({
                    feedbackId: feedbackForm.feedbackId,
                    technicalScore: Number(feedbackForm.technicalScore),
                    communicationScore: Number(feedbackForm.communicationScore),
                    problemSolvingScore: Number(feedbackForm.problemSolvingScore),
                    cultureFitScore: Number(feedbackForm.cultureFitScore),
                    comments: feedbackForm.comments,
                    recommendation: feedbackForm.recommendation
                  });
                  setFeedbackNotice("Feedback updated.");
                } else {
                  await submitInterviewFeedback({
                    interviewId: Number(feedbackForm.interviewId),
                    interviewerId: feedbackForm.interviewerId,
                    technicalScore: Number(feedbackForm.technicalScore),
                    communicationScore: Number(feedbackForm.communicationScore),
                    problemSolvingScore: Number(feedbackForm.problemSolvingScore),
                    cultureFitScore: Number(feedbackForm.cultureFitScore),
                    comments: feedbackForm.comments,
                    recommendation: feedbackForm.recommendation
                  });
                  setFeedbackNotice("Feedback submitted.");
                }
                if (onRefreshInterviews) {
                  await onRefreshInterviews();
                }
                resetFeedback();
              } catch (err) {
                setFeedbackNotice(err.message || "Failed to submit feedback.");
              }
            }}
          >
            Save Feedback
          </Button>
          <Button variant="secondary" onClick={resetFeedback}>
            Clear
          </Button>
          <Button
            variant="secondary"
            onClick={async () => {
              if (!feedbackForm.feedbackId) {
                setFeedbackNotice("Feedback ID is required.");
                return;
              }
              try {
                const detail = await getFeedbackById(feedbackForm.feedbackId);
                setFeedbackDetail(detail || null);
                setFeedbackNotice("Feedback loaded.");
              } catch (err) {
                setFeedbackNotice(err.message || "Failed to load feedback detail.");
              }
            }}
          >
            Load Feedback By ID
          </Button>
          <Button
            variant="danger"
            onClick={async () => {
              if (!feedbackForm.feedbackId) {
                setFeedbackNotice("Feedback ID is required.");
                return;
              }
              const ok = window.confirm(`Delete feedback ${feedbackForm.feedbackId}?`);
              if (!ok) return;
              try {
                await deleteInterviewFeedback(feedbackForm.feedbackId);
                setFeedbackDetail(null);
                setFeedbackNotice("Feedback deleted.");
                setFeedbackForm((prev) => ({ ...prev, feedbackId: "" }));
                if (onRefreshInterviews) {
                  await onRefreshInterviews();
                }
              } catch (err) {
                setFeedbackNotice(err.message || "Failed to delete feedback.");
              }
            }}
          >
            Delete Feedback By ID
          </Button>
        </div>
        {feedbackDetail ? (
          <div className="mt-3 rounded-xl border bg-slate-50 p-3 text-xs text-gray-700">
            <div className="mb-1 font-semibold">Feedback Detail</div>
            <div>ID: {feedbackDetail.id}</div>
            <div>Interview ID: {feedbackDetail.interview_id}</div>
            <div>Interviewer ID: {feedbackDetail.interviewer_id}</div>
            <div>Technical: {feedbackDetail.technical_score}</div>
            <div>Communication: {feedbackDetail.communication_score}</div>
            <div>Problem Solving: {feedbackDetail.problem_solving_score}</div>
            <div>Culture Fit: {feedbackDetail.culture_fit_score}</div>
            <div>Recommendation: {feedbackDetail.recommendation || "-"}</div>
            <div>Comments: {feedbackDetail.comments || "-"}</div>
          </div>
        ) : null}
        {feedbackNotice ? (
          <div className="mt-2 text-xs text-gray-500">{feedbackNotice}</div>
        ) : null}
      </Card>

      <Card title="Microsoft Meetings" icon={<ClipboardCheck className="h-4 w-4" />}>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={async () => {
              setMeetingsNotice("");
              try {
                const res = await getMyMeetings({ top: 10, skip: 0 });
                setMeetings(res?.events || []);
              } catch (err) {
                setMeetingsNotice(err.message || "Failed to load meetings.");
              }
            }}
          >
            Load My Meetings
          </Button>
        </div>
        {meetings.length === 0 ? (
          <div className="mt-2 text-xs text-gray-500">No meetings loaded.</div>
        ) : (
          <ul className="mt-2 list-disc pl-4 text-sm">
            {meetings.map((m) => (
              <li key={m.id}>
                {m.subject} — {formatDate(m.start)} to {formatDate(m.end)}
              </li>
            ))}
          </ul>
        )}

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Input
            label="Service Calendar User Email"
            value={serviceEmail}
            onChange={setServiceEmail}
          />
          <Input
            label="Start Time (optional)"
            value={serviceStart}
            onChange={setServiceStart}
            type="datetime-local"
          />
          <Input
            label="End Time (optional)"
            value={serviceEnd}
            onChange={setServiceEnd}
            type="datetime-local"
          />
          <div className="md:col-span-2">
            <Button
              variant="secondary"
              onClick={async () => {
                setMeetingsNotice("");
                try {
                  const res = await getServiceCalendarEvents({
                    userEmail: serviceEmail,
                    startTime: serviceStart
                      ? new Date(serviceStart).toISOString()
                      : undefined,
                    endTime: serviceEnd ? new Date(serviceEnd).toISOString() : undefined
                  });
                  setServiceMeetings(res?.events || []);
                } catch (err) {
                  setMeetingsNotice(err.message || "Failed to load service calendar.");
                }
              }}
            >
              Load Service Calendar
            </Button>
          </div>
        </div>
        {serviceMeetings.length === 0 ? null : (
          <ul className="mt-2 list-disc pl-4 text-sm">
            {serviceMeetings.map((m) => (
              <li key={m.id}>
                {m.subject || m.id} — {formatDate(m.start)} to {formatDate(m.end)}
              </li>
            ))}
          </ul>
        )}
        {meetingsNotice ? (
          <div className="mt-2 text-xs text-gray-500">{meetingsNotice}</div>
        ) : null}
      </Card>

      <Card title="Microsoft Graph Tools" icon={<ClipboardCheck className="h-4 w-4" />}>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => window.open(getMicrosoftSigninUrl(), "_blank")}
          >
            Connect Microsoft
          </Button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Input
            label="Send Mail To"
            value={mailForm.to}
            onChange={(value) => setMailForm((prev) => ({ ...prev, to: value }))}
          />
          <Input
            label="Subject"
            value={mailForm.subject}
            onChange={(value) => setMailForm((prev) => ({ ...prev, subject: value }))}
          />
          <div className="md:col-span-2">
            <TextArea
              label="Body"
              value={mailForm.bodyText}
              onChange={(value) => setMailForm((prev) => ({ ...prev, bodyText: value }))}
              rows={3}
            />
          </div>
          <div className="md:col-span-2">
            <Button
              onClick={async () => {
                setMailNotice("");
                try {
                  const res = await sendGraphMail({
                    to: mailForm.to,
                    subject: mailForm.subject,
                    bodyText: mailForm.bodyText
                  });
                  setMailNotice(res?.status || "Mail sent.");
                  setMailForm({ to: "", subject: "", bodyText: "" });
                } catch (err) {
                  setMailNotice(err.message || "Failed to send mail.");
                }
              }}
            >
              Send Mail
            </Button>
          </div>
        </div>
        {mailNotice ? <div className="mt-2 text-xs text-gray-500">{mailNotice}</div> : null}

        <div className="mt-6 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={async () => {
              setSharepointNotice("");
              try {
                const res = await testSharepointConnection();
                setSharepointStatus(res);
              } catch (err) {
                setSharepointNotice(err.message || "SharePoint test failed.");
              }
            }}
          >
            Test SharePoint Connection
          </Button>
          <Button
            variant="secondary"
            onClick={async () => {
              setSharepointNotice("");
              try {
                const res = await listSharepointDrives();
                setSharepointDrives(res?.drives || res?.value || []);
                if (!res?.drives?.length && !res?.value?.length) {
                  setSharepointNotice(res?.message || "No drives returned.");
                }
              } catch (err) {
                setSharepointNotice(err.message || "Failed to list drives.");
              }
            }}
          >
            List SharePoint Drives
          </Button>
        </div>
        {sharepointStatus ? (
          <div className="mt-3 rounded-lg border bg-slate-50 px-3 py-2 text-xs">
            <div className="font-semibold">SharePoint Status</div>
            <div>Status: {sharepointStatus.status || "-"}</div>
            {sharepointStatus.message ? <div>Message: {sharepointStatus.message}</div> : null}
            {sharepointStatus.details ? <div>Details: {sharepointStatus.details}</div> : null}
          </div>
        ) : null}
        {sharepointDrives.length ? (
          <ul className="mt-3 list-disc pl-4 text-sm">
            {sharepointDrives.map((drive) => (
              <li key={drive.id || drive.name}>
                {drive.name || drive.id} {drive.id ? `(${drive.id})` : ""}
              </li>
            ))}
          </ul>
        ) : null}
        {sharepointNotice ? (
          <div className="mt-2 text-xs text-gray-500">{sharepointNotice}</div>
        ) : null}
      </Card>
    </div>
  );
}
