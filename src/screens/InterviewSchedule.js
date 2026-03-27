// Interview scheduling flow with Microsoft meeting creation.
import { useEffect, useMemo, useState } from "react";
import { Calendar } from "lucide-react";
import { Button, Card, Input, Select } from "../components/ui";
import {
  assignPanelMember,
  createInterview,
  createInterviewPanel
} from "../services/api/interviews";
import {
  getGraphMe,
  getMicrosoftSigninUrl,
  scheduleUserMeeting
} from "../services/api/msgraph";
import { getAllUsers } from "../services/api/users";

export default function InterviewSchedule({
  candidate,
  job,
  candidates = [],
  jobs = [],
  selectedCandidateId = "",
  selectedJobId = "",
  onChangeCandidate,
  onChangeJob,
  onSchedule,
  onViewStatus
}) {
  const normalizeText = (value) =>
    String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

  const findMatchingJobForCandidate = (candidateJobTitle) => {
    const normalizedCandidateJob = normalizeText(candidateJobTitle);
    if (!normalizedCandidateJob || !Array.isArray(jobs) || !jobs.length) return null;
    const exact = jobs.find(
      (j) => normalizeText(j?.title) === normalizedCandidateJob
    );
    if (exact) return exact;
    const contains = jobs.find((j) => {
      const normalizedJobTitle = normalizeText(j?.title);
      return (
        normalizedJobTitle.includes(normalizedCandidateJob) ||
        normalizedCandidateJob.includes(normalizedJobTitle)
      );
    });
    return contains || null;
  };

  const [roundName, setRoundName] = useState("HR");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [attendeeEmails, setAttendeeEmails] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [interviewerOptions, setInterviewerOptions] = useState([]);
  const [selectedInterviewers, setSelectedInterviewers] = useState([]);
  const [statusNotice, setStatusNotice] = useState("");
  const [isScheduling, setIsScheduling] = useState(false);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [msConnected, setMsConnected] = useState(false);
  const [msUserEmail, setMsUserEmail] = useState("");

  const newId = useMemo(() => {
    const n = Math.floor(3000 + Math.random() * 7000);
    return `I-${n}`;
  }, []);

  const activeCandidate = useMemo(() => {
    return (
      candidates.find((c) => String(c.id) === String(selectedCandidateId || candidate?.id)) ||
      candidate
    );
  }, [candidates, selectedCandidateId, candidate]);

  const activeJob = useMemo(() => {
    return jobs.find((j) => String(j.id) === String(selectedJobId || job?.id)) || job;
  }, [jobs, selectedJobId, job]);

  useEffect(() => {
    if (!attendeeEmails && activeCandidate?.email) {
      setAttendeeEmails(activeCandidate.email);
    }
  }, [attendeeEmails, activeCandidate?.email]);

  useEffect(() => {
    if (!activeCandidate?.jobTitle || !Array.isArray(jobs) || !jobs.length) return;
    const matchedJob = findMatchingJobForCandidate(activeCandidate.jobTitle);
    if (matchedJob && String(matchedJob.id) !== String(activeJob?.id || "")) {
      onChangeJob?.(matchedJob.id);
      setStatusNotice(`Auto-selected job "${matchedJob.title}" for ${activeCandidate.name}.`);
    }
  }, [activeCandidate?.id, activeCandidate?.jobTitle, jobs, activeJob?.id, onChangeJob]);

  useEffect(() => {
    let isMounted = true;
    const checkMicrosoft = async () => {
      try {
        // Check if a Microsoft account is connected for scheduling.
        const me = await getGraphMe();
        if (!isMounted) return;
        const email =
          me?.user?.email || me?.user?.userPrincipalName || me?.user?.mail || "";
        setMsConnected(true);
        setMsUserEmail(email);
      } catch (err) {
        if (!isMounted) return;
        setMsConnected(false);
        setMsUserEmail("");
      }
    };
    checkMicrosoft();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const loadUsers = async () => {
      setIsLoadingUsers(true);
      try {
        const res = await getAllUsers();
        if (!isMounted) return;
        const users = (res?.users || []).map((u) => ({
          id: u.user_id,
          name: u.user_name || u.user_email,
          email: u.user_email
        }));
        setInterviewerOptions(users);
      } catch (err) {
        if (!isMounted) return;
        setStatusNotice(err.message || "Failed to load interviewer list.");
      } finally {
        if (isMounted) {
          setIsLoadingUsers(false);
        }
      }
    };
    loadUsers();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="grid gap-4">
      <Card
        title="Interview Request / Scheduling"
        icon={<Calendar className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={onViewStatus}>
            View status
          </Button>
        }
      >
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Candidate</div>
            <div className="text-sm font-extrabold tracking-tight">
              {activeCandidate?.name}
            </div>
            <div className="mt-1 text-xs text-gray-600">{activeCandidate?.id}</div>
          </div>
          <div className="rounded-2xl border bg-gray-50 p-4">
            <div className="text-xs font-semibold text-gray-500">Job</div>
            <div className="text-sm font-extrabold tracking-tight">{activeJob?.title}</div>
            <div className="mt-1 text-xs text-gray-600">{activeJob?.id}</div>
          </div>
          <label className="block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Candidate</div>
            <select
              value={activeCandidate?.id || ""}
              onChange={(event) => {
                const value = event.target.value;
                onChangeCandidate?.(value);
                const nextCandidate = candidates.find((c) => String(c.id) === String(value));
                if (nextCandidate?.email) {
                  setAttendeeEmails(nextCandidate.email);
                }
                const matchedJob = findMatchingJobForCandidate(nextCandidate?.jobTitle);
                if (matchedJob) {
                  onChangeJob?.(matchedJob.id);
                  setStatusNotice(`Auto-selected job "${matchedJob.title}" for ${nextCandidate?.name}.`);
                } else if (nextCandidate?.jobTitle) {
                  setStatusNotice(
                    `No matching job found for candidate job title "${nextCandidate.jobTitle}".`
                  );
                }
              }}
              className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.id})
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <div className="mb-1 text-xs font-semibold text-gray-700">Job</div>
            <select
              value={activeJob?.id || ""}
              onChange={(event) => onChangeJob?.(event.target.value)}
              className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
            >
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} ({j.id})
                </option>
              ))}
            </select>
          </label>

          <Select
            label="Round"
            value={roundName}
            onChange={(value) => setRoundName(value)}
            options={["HR", "Technical", "Manager"]}
          />
          <Input
            label="Start Time"
            value={startTime}
            onChange={setStartTime}
            type="datetime-local"
          />
          <Input
            label="End Time"
            value={endTime}
            onChange={setEndTime}
            type="datetime-local"
          />
          <div className="md:col-span-2">
            <div className="mb-1 text-xs font-semibold text-gray-700">
              Interviewers {isLoadingUsers ? "(loading...)" : ""}
            </div>
            <div className="max-h-40 space-y-2 overflow-y-auto rounded-xl border bg-white px-3 py-2 text-sm">
              {interviewerOptions.length === 0 ? (
                <div className="text-gray-500">No interviewers available.</div>
              ) : (
                interviewerOptions.map((user) => {
                  const checked = selectedInterviewers.includes(user.id);
                  return (
                    <label key={user.id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          if (event.target.checked) {
                            setSelectedInterviewers((prev) => [...prev, user.id]);
                          } else {
                            setSelectedInterviewers((prev) =>
                              prev.filter((id) => id !== user.id)
                            );
                          }
                        }}
                      />
                      <span>
                        {user.name} ({user.id})
                      </span>
                    </label>
                  );
                })
              )}
            </div>
          </div>
          <div className="md:col-span-2">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold text-gray-700">
                Microsoft account connection
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => window.open(getMicrosoftSigninUrl(), "_blank")}
              >
                {msConnected ? "Re-connect Microsoft" : "Connect Microsoft"}
              </Button>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Status: {msConnected ? `Connected${msUserEmail ? ` (${msUserEmail})` : ""}` : "Not connected"}
            </div>
          </div>
          <div className="md:col-span-2">
            <Input
              label="Attendee Emails (comma separated)"
              value={attendeeEmails}
              onChange={setAttendeeEmails}
            />
          </div>
          <Input label="Timezone" value={timezone} onChange={setTimezone} />
        </div>

        <div className="mt-4 flex justify-end">
          <Button
            onClick={async () => {
              if (!startTime || !endTime) {
                setStatusNotice("Start and end time are required.");
                return;
              }
              const interviewerList = selectedInterviewers;
              if (!interviewerList.length) {
                setStatusNotice("At least one interviewer ID is required.");
                return;
              }
              const attendeeList = attendeeEmails
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean);
              setStatusNotice("");
              if (!msConnected) {
                setStatusNotice("Microsoft sign-in required. Please connect first.");
                window.open(getMicrosoftSigninUrl(), "_blank");
                return;
              }
              setIsScheduling(true);
              try {
                const panel = await createInterviewPanel({
                  candidateId: activeCandidate.id,
                  roundName
                });
                const panelId = panel?.id;
                for (const interviewerId of interviewerList) {
                  await assignPanelMember({ panelId, interviewerId });
                }
                const startIso = new Date(startTime).toISOString();
                const endIso = new Date(endTime).toISOString();
                const meeting = await scheduleUserMeeting({
                  subject: `Interview - ${activeCandidate.name} (${roundName})`,
                  startIso,
                  endIso,
                  attendees: attendeeList,
                  timezone: timezone || "UTC",
                  teamsOnline: true
                });
                const interview = await createInterview({
                  panelId,
                  candidateId: activeCandidate.id,
                  startTime: startIso,
                  endTime: endIso,
                  meetingLink: meeting?.joinUrl || null,
                  outlookEventId: meeting?.eventId || null,
                  status: "Scheduled"
                });
                onSchedule({
                  id: interview.id || newId,
                  panelId,
                  panelRoundName: roundName,
                  candidateId: activeCandidate.id,
                  startTime: interview.start_time,
                  endTime: interview.end_time,
                  meetingLink: interview.meeting_link || meeting?.joinUrl || "",
                  outlookEventId: interview.outlook_event_id || meeting?.eventId || "",
                  status: interview.status || "Scheduled"
                });
                setStatusNotice("Interview scheduled.");
              } catch (err) {
                const message = err.message || "Failed to schedule interview.";
                if (message.toLowerCase().includes("sign in first")) {
                  window.open(getMicrosoftSigninUrl(), "_blank");
                }
                setStatusNotice(message);
              } finally {
                setIsScheduling(false);
              }
            }}
            disabled={isScheduling}
          >
            {isScheduling ? "Scheduling..." : "Schedule"}
          </Button>
        </div>
        {statusNotice ? (
          <div className="mt-2 text-xs text-gray-500">{statusNotice}</div>
        ) : null}
      </Card>
    </div>
  );
}
