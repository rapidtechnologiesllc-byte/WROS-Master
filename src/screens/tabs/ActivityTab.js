import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getCandidateInterviewHistory,
  getPanelMembers,
  getInterviewById,
  updateInterview,
  deleteInterview
} from "../../services/api/interviews";

export default function ActivityTab({ candidateId }) {
  const [historySummary, setHistorySummary] = useState(null);
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [panelMembersMap, setPanelMembersMap] = useState({});

  const [selectedInterviewId, setSelectedInterviewId] = useState(null);
  const [selectedInterviewDetails, setSelectedInterviewDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");

  const [showRescheduleModal, setShowRescheduleModal] = useState(false);
  const [selectedInterview, setSelectedInterview] = useState(null);
  const [selectedInterviewIdForEdit, setSelectedInterviewIdForEdit] = useState(null);
  const [rescheduleForm, setRescheduleForm] = useState({
    interviewDate: "",
    startTime: "",
    endTime: "",
    status: "Scheduled"
  });
  const [rescheduleErrors, setRescheduleErrors] = useState({});
  const [rescheduling, setRescheduling] = useState(false);
  const [rescheduleNotice, setRescheduleNotice] = useState("");
  const [rescheduleNoticeType, setRescheduleNoticeType] = useState("success");

  const [showCancelModal, setShowCancelModal] = useState(false);
  const [selectedInterviewForCancel, setSelectedInterviewForCancel] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelNotice, setCancelNotice] = useState("");
  const [cancelNoticeType, setCancelNoticeType] = useState("success");

  const fetchInterviewHistory = useCallback(async () => {
    if (!candidateId) return;

    try {
      setLoading(true);
      setError("");
      setPanelMembersMap({});

      const res = await getCandidateInterviewHistory(candidateId);

      const list = Array.isArray(res)
        ? res
        : Array.isArray(res?.interviews)
          ? res.interviews
          : Array.isArray(res?.data)
            ? res.data
            : [];

      const sorted = [...list].sort((a, b) => {
        const aTime = new Date(a?.start_time || 0).getTime();
        const bTime = new Date(b?.start_time || 0).getTime();
        return bTime - aTime;
      });

      setHistorySummary(
        Array.isArray(res)
          ? {
              total_interviews: sorted.length,
              scheduled_interviews: sorted.filter(
                (item) => String(item?.status || "").toLowerCase() === "scheduled"
              ).length,
              completed_interviews: sorted.filter(
                (item) => String(item?.status || "").toLowerCase() === "completed"
              ).length,
              cancelled_interviews: sorted.filter(
                (item) => String(item?.status || "").toLowerCase().includes("cancel")
              ).length
            }
          : res
      );

      setInterviews(sorted);
    } catch (err) {
      console.error("Failed to fetch candidate interview history", err);
      setError("Failed to load interview activity");
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchInterviewHistory();
  }, [fetchInterviewHistory]);

  useEffect(() => {
    if (!interviews.length) return;

    let isMounted = true;

    const fetchPanelMembersForInterviews = async () => {
      try {
        const uniquePanelIds = [
          ...new Set(interviews.map((item) => item?.panel_id).filter(Boolean))
        ];

        const results = await Promise.all(
          uniquePanelIds.map(async (panelId) => {
            const res = await getPanelMembers(panelId);

            const members = Array.isArray(res)
              ? res
              : Array.isArray(res?.members)
                ? res.members
                : Array.isArray(res?.panel_members)
                  ? res.panel_members
                  : [];

            return { panelId, members };
          })
        );

        if (!isMounted) return;

        const nextMap = {};
        results.forEach(({ panelId, members }) => {
          nextMap[panelId] = members;
        });

        setPanelMembersMap(nextMap);
      } catch (err) {
        console.error("Failed to fetch panel members", err);
      }
    };

    fetchPanelMembersForInterviews();

    return () => {
      isMounted = false;
    };
  }, [interviews]);

  useEffect(() => {
    if (!selectedInterviewId) return;

    let isMounted = true;

    const fetchInterviewDetails = async () => {
      try {
        setDetailsLoading(true);
        setDetailsError("");
        setSelectedInterviewDetails(null);

        const res = await getInterviewById(selectedInterviewId);

        if (!isMounted) return;
        setSelectedInterviewDetails(res);
      } catch (err) {
        console.error("Failed to fetch interview details", err);
        if (!isMounted) return;
        setDetailsError("Failed to load interview details");
      } finally {
        if (isMounted) {
          setDetailsLoading(false);
        }
      }
    };

    fetchInterviewDetails();

    return () => {
      isMounted = false;
    };
  }, [selectedInterviewId]);

  const groupedData = useMemo(() => {
    const upcoming = [];
    const past = [];
    const now = Date.now();

    interviews.forEach((interview) => {
      const start = new Date(interview?.start_time || 0).getTime();
      if (start >= now) {
        upcoming.push(interview);
      } else {
        past.push(interview);
      }
    });

    return { upcoming, past };
  }, [interviews]);

  const openDetailsModal = (interviewId) => {
    setSelectedInterviewId(interviewId);
    setDetailsError("");
  };

  const closeDetailsModal = () => {
    setSelectedInterviewId(null);
    setSelectedInterviewDetails(null);
    setDetailsError("");
  };

  const openRescheduleModal = (interview) => {
    const start = safeDate(interview?.start_time);
    const end = safeDate(interview?.end_time);

    setSelectedInterview(interview);
    setSelectedInterviewIdForEdit(interview?.id ?? null);
    setRescheduleErrors({});
    setRescheduleNotice("");
    setRescheduleNoticeType("success");
    setRescheduleForm({
      interviewDate: start ? formatDateInput(start) : "",
      startTime: start ? formatTimeInput(start) : "",
      endTime: end ? formatTimeInput(end) : "",
      status: interview?.status || "Scheduled"
    });
    setShowRescheduleModal(true);
  };

  const closeRescheduleModal = () => {
    if (rescheduling) return;

    setShowRescheduleModal(false);
    setSelectedInterview(null);
    setSelectedInterviewIdForEdit(null);
    setRescheduleForm({
      interviewDate: "",
      startTime: "",
      endTime: "",
      status: "Scheduled"
    });
    setRescheduleErrors({});
    setRescheduleNotice("");
    setRescheduleNoticeType("success");
  };

  const handleRescheduleInputChange = (field, value) => {
    setRescheduleForm((prev) => ({
      ...prev,
      [field]: value
    }));

    if (rescheduleErrors[field]) {
      setRescheduleErrors((prev) => ({
        ...prev,
        [field]: ""
      }));
    }
  };

  const validateRescheduleForm = () => {
    const errors = {};

    if (!rescheduleForm.interviewDate) {
      errors.interviewDate = "Interview date is required";
    }

    if (!rescheduleForm.startTime) {
      errors.startTime = "Start time is required";
    }

    if (!rescheduleForm.endTime) {
      errors.endTime = "End time is required";
    }

    if (!rescheduleForm.status) {
      errors.status = "Status is required";
    }

    const start = buildLocalDateTime(
      rescheduleForm.interviewDate,
      rescheduleForm.startTime
    );
    const end = buildLocalDateTime(
      rescheduleForm.interviewDate,
      rescheduleForm.endTime
    );

    if (!start) {
      errors.startTime = "Invalid start time";
    }

    if (!end) {
      errors.endTime = "Invalid end time";
    }

    if (start && end && end <= start) {
      errors.endTime = "End time must be after start time";
    }

    setRescheduleErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleRescheduleInterview = async () => {
    if (!selectedInterviewIdForEdit) {
      setRescheduleNotice("Interview ID is missing");
      setRescheduleNoticeType("error");
      return;
    }

    if (!selectedInterview?.panel_id || !selectedInterview?.candidate_id) {
      setRescheduleNotice("Interview data is incomplete");
      setRescheduleNoticeType("error");
      return;
    }

    if (!validateRescheduleForm()) return;

    try {
      setRescheduling(true);
      setRescheduleNotice("");
      setRescheduleNoticeType("success");

      const updatedStart = buildLocalDateTime(
        rescheduleForm.interviewDate,
        rescheduleForm.startTime
      );
      const updatedEnd = buildLocalDateTime(
        rescheduleForm.interviewDate,
        rescheduleForm.endTime
      );

      const payload = {
        panel_id: selectedInterview.panel_id,
        candidate_id: selectedInterview.candidate_id,
        start_time: updatedStart,
        end_time: updatedEnd,
        meeting_link: selectedInterview.meeting_link || "",
        outlook_event_id: selectedInterview.outlook_event_id || "",
        status: rescheduleForm.status
      };

      console.log("Updating interview:", selectedInterviewIdForEdit, payload);

      await updateInterview(selectedInterviewIdForEdit, payload);
      await fetchInterviewHistory();

      setRescheduleNotice("Interview rescheduled successfully");
      setRescheduleNoticeType("success");

      window.setTimeout(() => {
        closeRescheduleModal();
      }, 700);
    } catch (err) {
      console.error("Failed to reschedule interview", err);
      setRescheduleNotice("Failed to reschedule interview");
      setRescheduleNoticeType("error");
    } finally {
      setRescheduling(false);
    }
  };

  const openCancelModal = (interview) => {
    setSelectedInterviewForCancel(interview);
    setCancelNotice("");
    setCancelNoticeType("success");
    setShowCancelModal(true);
  };

  const closeCancelModal = () => {
    if (cancelling) return;
    setShowCancelModal(false);
    setSelectedInterviewForCancel(null);
    setCancelNotice("");
    setCancelNoticeType("success");
  };

  const handleCancelInterview = async () => {
    if (!selectedInterviewForCancel?.id) {
      setCancelNotice("Interview ID is missing");
      setCancelNoticeType("error");
      return;
    }

    try {
      setCancelling(true);
      setCancelNotice("");
      setCancelNoticeType("success");

      await deleteInterview(selectedInterviewForCancel.id);
      await fetchInterviewHistory();

      setCancelNotice("Interview cancelled successfully");
      setCancelNoticeType("success");

      window.setTimeout(() => {
        closeCancelModal();
      }, 700);
    } catch (err) {
      console.error("Failed to cancel interview", err);
      setCancelNotice("Failed to cancel interview");
      setCancelNoticeType("error");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <SectionHeader
          title="Interview Activity"
          subtitle="Loading scheduled interviews..."
        />
        <SkeletonSummary />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <SectionHeader
          title="Interview Activity"
          subtitle="Could not load interview history."
        />
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  if (!interviews.length) {
    return (
      <div className="space-y-4">
        <SectionHeader
          title="Interview Activity"
          subtitle="Scheduled interviews for this candidate will appear here."
        />
        <EmptyState />
      </div>
    );
  }

  return (
    <>
      <div className="space-y-8">
        <SectionHeader
          title="Interview Activity"
          subtitle="Track scheduled, upcoming, completed, and cancelled interviews for this candidate."
        />

        <SummaryCards summary={historySummary} />

        {!!groupedData.upcoming.length && (
          <div className="space-y-4">
            <SubHeader title="Upcoming Interviews" count={groupedData.upcoming.length} />
            <div className="grid gap-4">
              {groupedData.upcoming.map((interview) => (
                <InterviewCard
                  key={interview.id}
                  interview={interview}
                  panelMembers={panelMembersMap[interview.panel_id] || []}
                  onViewDetails={() => openDetailsModal(interview.id)}
                  onReschedule={() => openRescheduleModal(interview)}
                  onCancel={() => openCancelModal(interview)}
                />
              ))}
            </div>
          </div>
        )}

        {!!groupedData.past.length && (
          <div className="space-y-4">
            <SubHeader title="Past Interviews" count={groupedData.past.length} />
            <div className="grid gap-4">
              {groupedData.past.map((interview) => (
                <InterviewCard
                  key={interview.id}
                  interview={interview}
                  panelMembers={panelMembersMap[interview.panel_id] || []}
                  onViewDetails={() => openDetailsModal(interview.id)}
                  onReschedule={() => openRescheduleModal(interview)}
                  onCancel={() => openCancelModal(interview)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {selectedInterviewId && (
        <InterviewDetailsModal
          open={!!selectedInterviewId}
          onClose={closeDetailsModal}
          loading={detailsLoading}
          error={detailsError}
          interview={selectedInterviewDetails}
          panelMembers={
            panelMembersMap[selectedInterviewDetails?.panel_id] ||
            panelMembersMap[
              interviews.find((item) => item.id === selectedInterviewId)?.panel_id
            ] ||
            []
          }
        />
      )}

      {showRescheduleModal && (
        <RescheduleModal
          interview={selectedInterview}
          form={rescheduleForm}
          errors={rescheduleErrors}
          notice={rescheduleNotice}
          noticeType={rescheduleNoticeType}
          loading={rescheduling}
          onChange={handleRescheduleInputChange}
          onClose={closeRescheduleModal}
          onSubmit={handleRescheduleInterview}
        />
      )}

      {showCancelModal && (
        <CancelInterviewModal
          interview={selectedInterviewForCancel}
          notice={cancelNotice}
          noticeType={cancelNoticeType}
          loading={cancelling}
          onClose={closeCancelModal}
          onConfirm={handleCancelInterview}
        />
      )}
    </>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <p className="text-sm text-gray-500">{subtitle}</p>
    </div>
  );
}

function SubHeader({ title, count }) {
  return (
    <div className="flex items-center justify-between">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
        {count}
      </span>
    </div>
  );
}

function SummaryCards({ summary }) {
  const cards = [
    { label: "Total Interviews", value: summary?.total_interviews ?? 0 },
    { label: "Scheduled", value: summary?.scheduled_interviews ?? 0 },
    { label: "Completed", value: summary?.completed_interviews ?? 0 },
    { label: "Cancelled", value: summary?.cancelled_interviews ?? 0 }
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"
        >
          <div className="text-sm font-medium text-gray-500">{card.label}</div>
          <div className="mt-2 text-2xl font-semibold text-gray-900">{card.value}</div>
        </div>
      ))}
    </div>
  );
}

function InterviewCard({
  interview,
  panelMembers,
  onViewDetails,
  onReschedule,
  onCancel
}) {
  const dateLabel = formatDate(interview?.start_time);
  const startLabel = formatTime(interview?.start_time);
  const endLabel = formatTime(interview?.end_time);
  const status = interview?.status || "Scheduled";
  const roundName = interview?.panel_round_name || "Interview Round";
  const meetingLink = interview?.meeting_link || "";
  const isOnline = Boolean(meetingLink);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-base font-semibold text-gray-900">{roundName}</h4>
            <StatusBadge value={status} />
          </div>

          <div className="grid gap-2 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-800">Date:</span>
              <span>{dateLabel}</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-800">Time:</span>
              <span>
                {startLabel} - {endLabel}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-800">Mode:</span>
              <span>{isOnline ? "Online Interview" : "Offline / TBD"}</span>
            </div>

            {interview?.feedback_count != null && (
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-800">Feedback:</span>
                <span>{interview.feedback_count}</span>
              </div>
            )}

            {interview?.panel_id != null && (
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-800">Panel ID:</span>
                <span>{interview.panel_id}</span>
              </div>
            )}
          </div>

          <PanelMembers members={panelMembers} />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onViewDetails}
            className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            View Details
          </button>

          <button
            type="button"
            onClick={onReschedule}
            className="inline-flex items-center rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100"
          >
            Reschedule
          </button>

          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100"
          >
            Cancel
          </button>

          {meetingLink ? (
            <a
              href={meetingLink}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100"
            >
              Join Meeting
            </a>
          ) : (
            <span className="inline-flex items-center rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm font-medium text-gray-500">
              Meeting link not available
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function PanelMembers({ members }) {
  if (!members?.length) {
    return (
      <div className="mt-3">
        <div className="text-xs font-semibold text-gray-500 mb-2">
          Panel Members
        </div>
        <div className="text-sm text-gray-500">No panel members available</div>
      </div>
    );
  }

  return (
    <div className="mt-3">
      <div className="text-xs font-semibold text-gray-500 mb-2">
        Panel Members
      </div>
      <div className="flex flex-wrap gap-2">
        {members.map((member, index) => {
          const label =
            member?.interviewer_name ||
            member?.user_name ||
            member?.name ||
            `Member ${index + 1}`;

          return (
            <span
              key={member?.id || member?.interviewer_id || `${label}-${index}`}
              className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700"
            >
              {label}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function InterviewDetailsModal({ open, onClose, loading, error, interview, panelMembers }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-3xl rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Interview Details</h3>
            <p className="mt-1 text-sm text-gray-500">
              View complete interview information for this candidate.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="max-h-[75vh] overflow-y-auto px-6 py-6">
          {loading && (
            <div className="space-y-4">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          )}

          {!loading && error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && interview && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-lg font-semibold text-gray-900">
                    {interview?.panel_round_name || "Interview"}
                  </h4>
                  <StatusBadge value={interview?.status || "Scheduled"} />
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <DetailRow label="Interview ID" value={interview?.id} />
                  <DetailRow label="Panel ID" value={interview?.panel_id} />
                  <DetailRow label="Candidate Name" value={interview?.candidate_name} />
                  <DetailRow label="Candidate Email" value={interview?.candidate_email} />
                  <DetailRow label="Date" value={formatDate(interview?.start_time)} />
                  <DetailRow
                    label="Time"
                    value={`${formatTime(interview?.start_time)} - ${formatTime(
                      interview?.end_time
                    )}`}
                  />
                  <DetailRow label="Feedback Count" value={interview?.feedback_count ?? 0} />
                  <DetailRow
                    label="Mode"
                    value={interview?.meeting_link ? "Online Interview" : "Offline / TBD"}
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <div className="text-sm font-semibold text-gray-900 mb-3">
                  Panel Members
                </div>
                <PanelMembers members={panelMembers} />
              </div>

              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
                <div className="text-sm font-semibold text-gray-900">
                  Meeting Information
                </div>

                <DetailRow
                  label="Meeting Link"
                  value={
                    interview?.meeting_link ? (
                      <a
                        href={interview.meeting_link}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 underline break-all"
                      >
                        {interview.meeting_link}
                      </a>
                    ) : (
                      "Not available"
                    )
                  }
                />

                <DetailRow
                  label="Outlook Event ID"
                  value={interview?.outlook_event_id || "Not available"}
                />
              </div>
            </div>
          )}
        </div>

        <div className="border-t bg-white px-6 py-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function RescheduleModal({
  interview,
  form,
  errors,
  notice,
  noticeType,
  loading,
  onChange,
  onClose,
  onSubmit
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-2xl rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Reschedule Interview</h3>
            <p className="mt-1 text-sm text-gray-500">
              Update interview timing for {interview?.panel_round_name || "this interview"}.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-6 space-y-5">
          {notice && (
            <div
              className={`rounded-2xl border px-4 py-3 text-sm ${
                noticeType === "error"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-green-200 bg-green-50 text-green-700"
              }`}
            >
              {notice}
            </div>
          )}

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <ReadOnlyField label="Interview ID" value={interview?.id || "-"} />

            <ReadOnlyField label="Round Name" value={interview?.panel_round_name || "-"} />

            <FormField
              label="Interview Date"
              type="date"
              value={form.interviewDate}
              onChange={(e) => onChange("interviewDate", e.target.value)}
              error={errors.interviewDate}
            />

            <FormField
              label="Status"
              value={form.status}
              onChange={(e) => onChange("status", e.target.value)}
              error={errors.status}
            />

            <FormField
              label="Start Time"
              type="time"
              value={form.startTime}
              onChange={(e) => onChange("startTime", e.target.value)}
              error={errors.startTime}
            />

            <FormField
              label="End Time"
              type="time"
              value={form.endTime}
              onChange={(e) => onChange("endTime", e.target.value)}
              error={errors.endTime}
            />
          </div>
        </div>

        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Close
          </button>

          <button
            type="button"
            onClick={onSubmit}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100 disabled:opacity-60"
          >
            {loading ? "Updating..." : "Update Interview"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CancelInterviewModal({
  interview,
  notice,
  noticeType,
  loading,
  onClose,
  onConfirm
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center px-4 py-6">
      <div className="w-full max-w-lg rounded-3xl border border-gray-200 bg-white shadow-2xl overflow-hidden">
        <div className="border-b px-6 py-5 flex items-start justify-between">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Cancel Interview</h3>
            <p className="mt-1 text-sm text-gray-500">
              This will remove the interview from the current interview flow.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-6 space-y-5">
          {notice && (
            <div
              className={`rounded-2xl border px-4 py-3 text-sm ${
                noticeType === "error"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-green-200 bg-green-50 text-green-700"
              }`}
            >
              {notice}
            </div>
          )}

          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
            <div className="text-sm text-gray-700">
              Are you sure you want to cancel this interview?
            </div>

            <div className="mt-4 grid gap-3">
              <DetailRow label="Interview ID" value={interview?.id || "-"} />
              <DetailRow
                label="Round Name"
                value={interview?.panel_round_name || "-"}
              />
              <DetailRow
                label="Date"
                value={formatDate(interview?.start_time)}
              />
              <DetailRow
                label="Time"
                value={`${formatTime(interview?.start_time)} - ${formatTime(
                  interview?.end_time
                )}`}
              />
            </div>
          </div>
        </div>

        <div className="border-t bg-white px-6 py-4 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Close
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="inline-flex items-center rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:opacity-60"
          >
            {loading ? "Cancelling..." : "Confirm Cancel"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
        {label}
      </div>
      <div className="text-sm text-gray-800 break-words">{value || "-"}</div>
    </div>
  );
}

function FormField({ label, error, type = "text", value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition ${
          error
            ? "border-red-300 focus:border-red-400"
            : "border-gray-300 focus:border-gray-400"
        }`}
      />
      {error ? <p className="mt-1 text-xs text-red-500">{error}</p> : null}
    </div>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
      </label>
      <div className="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-700">
        {value}
      </div>
    </div>
  );
}

function StatusBadge({ value }) {
  const normalized = String(value || "").toLowerCase();

  let styles = "bg-gray-100 text-gray-700 border-gray-200";

  if (normalized.includes("scheduled")) {
    styles = "bg-blue-50 text-blue-700 border-blue-200";
  } else if (normalized.includes("completed")) {
    styles = "bg-green-50 text-green-700 border-green-200";
  } else if (normalized.includes("cancel")) {
    styles = "bg-red-50 text-red-700 border-red-200";
  } else if (normalized.includes("resched")) {
    styles = "bg-amber-50 text-amber-700 border-amber-200";
  }

  return (
    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${styles}`}>
      {value}
    </span>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white text-xl shadow-sm">
        📅
      </div>
      <h3 className="text-sm font-semibold text-gray-900">No interview activity yet</h3>
      <p className="mt-1 text-sm text-gray-500">
        Once an interview is scheduled for this candidate, it will appear here.
      </p>
    </div>
  );
}

function SkeletonSummary() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"
        >
          <div className="animate-pulse space-y-3">
            <div className="h-3 w-24 rounded bg-gray-100" />
            <div className="h-6 w-12 rounded bg-gray-200" />
          </div>
        </div>
      ))}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="animate-pulse space-y-3">
        <div className="h-4 w-48 rounded bg-gray-200" />
        <div className="h-3 w-64 rounded bg-gray-100" />
        <div className="h-3 w-56 rounded bg-gray-100" />
      </div>
    </div>
  );
}

function safeDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function buildLocalDateTime(dateValue, timeValue) {
  if (!dateValue || !timeValue) return "";
  return `${dateValue}T${timeValue}`;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatDateInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatTimeInput(date) {
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}