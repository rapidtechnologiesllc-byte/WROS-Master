import { useState, useEffect, useCallback } from "react";
import { Plus, Loader, CheckCircle, AlertCircle, RefreshCw, X } from "lucide-react";
import {
  completeLinkedInImport,
  listLinkedInPipeline,
  queueLinkedInCandidate,
  updateLinkedInPipelineStatus,
} from "../services/api/linkedinPipeline";

export default function LinkedInPipelineScreen() {
  const [linkedInUrl, setLinkedInUrl] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [pipelineItems, setPipelineItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [phoneInput, setPhoneInput] = useState({});
  const [emailInput, setEmailInput] = useState({});
  const [statusFilter, setStatusFilter] = useState("all");

  // Page-level error/warning state
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const loadPipeline = useCallback(async () => {
    setFetching(true);
    setError(null);
    try {
      const data = await listLinkedInPipeline(statusFilter);
      setPipelineItems(data?.items || []);
    } catch (error) {
      console.error(`[LinkedIn Pipeline] Failed to load: ${error.message}`);
      setError(error.message || "Failed to load pipeline items");
    } finally {
      setFetching(false);
    }
  }, [statusFilter]);

  // Load on mount and whenever the status filter changes
  useEffect(() => {
    loadPipeline();
  }, [loadPipeline]);

  const handleQueueCandidate = async (e) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);

    if (!linkedInUrl.trim()) {
      setActionError("Please enter a LinkedIn URL");
      return;
    }

    setLoading(true);
    try {
      const result = await queueLinkedInCandidate({
        linkedinUrl: linkedInUrl.trim(),
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim(),
      });

      if (result.status === "QUEUED") {
        setActionSuccess("✅ Added to your pipeline. The candidate record is being created and a follow-up task is on My Tasks.");
        setLinkedInUrl("");
        setFirstName("");
        setLastName("");
        setEmail("");
        loadPipeline();
      } else if (result.status === "ALREADY_EXISTS") {
        setActionError(`⚠️ Candidate already in system: ${result.candidate?.name}`);
      } else if (result.status === "ALREADY_QUEUED") {
        const st = (result.pipeline_item?.status || "").replace(/_/g, " ");
        setActionError(`📋 ${result.message} (status: ${st})`);
      }
    } catch (error) {
      setActionError(error.message || "Failed to queue candidate");
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteImport = async (pipelineId) => {
    setActionError(null);
    setActionSuccess(null);

    const item = pipelineItems.find((i) => i.id === pipelineId);
    const phone = phoneInput[pipelineId];
    const importEmail = (emailInput[pipelineId] ?? item?.email ?? "").trim();
    if (!phone?.trim()) {
      setActionError("Please enter a phone number");
      return;
    }
    if (!importEmail) {
      setActionError("Please enter an email address");
      return;
    }

    try {
      await completeLinkedInImport(pipelineId, {
        linkedinUrl: item.linkedin_url, phoneNumber: phone, email: importEmail,
      });

      setActionSuccess("✅ Candidate imported! Ready for Thunder autonomous loop.");
      setPhoneInput({ ...phoneInput, [pipelineId]: "" });
      setEmailInput({ ...emailInput, [pipelineId]: "" });
      setExpandedId(null);
      loadPipeline();
    } catch (error) {
      setActionError(error.message || "Failed to complete import");
    }
  };

  const handleUpdateStatus = async (pipelineId, newStatus) => {
    setActionError(null);
    setActionSuccess(null);

    try {
      await updateLinkedInPipelineStatus(pipelineId, newStatus);
      setActionSuccess("✅ Status updated. Your next follow-up task is on My Tasks.");
      loadPipeline();
    } catch (error) {
      setActionError(error.message || "Failed to update status");
    }
  };

  const getStatusBadgeColor = (status) => {
    const colors = {
      PENDING_CONNECTION: "bg-yellow-100 text-yellow-800",
      CONNECTED: "bg-blue-100 text-blue-800",
      PHONE_COLLECTED: "bg-purple-100 text-purple-800",
      IMPORTED_TO_THUNDER: "bg-green-100 text-green-800",
    };
    return colors[status] || "bg-gray-100 text-gray-800";
  };

  // Forward-only manual steps (mirrors the backend). Imported to Thunder is
  // reached through Import, which creates the candidate.
  const NEXT_STATUS = {
    PENDING_CONNECTION: "CONNECTED",
    CONNECTED: "PHONE_COLLECTED",
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">LinkedIn Candidate Pipeline</h1>
        <p className="text-gray-600">Queue LinkedIn profiles for manual recruiter outreach</p>
      </div>

      {/* Load Error Banner */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-900">Failed to Load Pipeline</h3>
              <p className="text-red-700 text-sm mt-1">{error}</p>
              <button
                onClick={loadPipeline}
                className="mt-3 px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 transition"
              >
                Try Again
              </button>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Action Error Banner */}
      {actionError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-700 text-sm font-medium">{actionError}</p>
            </div>
            <button
              onClick={() => setActionError(null)}
              className="text-red-600 hover:text-red-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Action Success Banner */}
      {actionSuccess && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-green-700 text-sm font-medium">{actionSuccess}</p>
            </div>
            <button
              onClick={() => setActionSuccess(null)}
              className="text-green-600 hover:text-green-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Queue Form */}
      <form onSubmit={handleQueueCandidate} className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Paste LinkedIn URL (e.g., https://linkedin.com/in/profile-slug)"
            value={linkedInUrl}
            onChange={(e) => setLinkedInUrl(e.target.value)}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <input
            type="text"
            placeholder="First name (optional)"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            placeholder="Last name (optional)"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="email"
            placeholder="Email (optional, if known)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
            {loading ? "Adding..." : "Add to Queue"}
          </button>
        </div>
      </form>

      {/* Status Filter */}
      <div className="mb-4 flex gap-2 flex-wrap">
        {["all", "PENDING_CONNECTION", "CONNECTED", "PHONE_COLLECTED", "IMPORTED_TO_THUNDER"].map(
          (status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                statusFilter === status
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }`}
            >
              {status === "all" ? "All" : status.replace(/_/g, " ")}
            </button>
          )
        )}
        <button
          onClick={loadPipeline}
          disabled={fetching}
          className="px-4 py-2 rounded-lg font-medium bg-gray-200 text-gray-700 hover:bg-gray-300 flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${fetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Pipeline Items List */}
      {fetching ? (
        <div className="flex justify-center py-12">
          <Loader className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      ) : pipelineItems.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-12 text-center">
          <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 text-lg">No candidates in pipeline</p>
          <p className="text-gray-400">Add a LinkedIn URL to get started</p>
        </div>
      ) : (
        <div className="space-y-4">
          {pipelineItems.map((item) => (
            <div key={item.id} className="bg-white rounded-lg shadow-md overflow-hidden">
              {/* Header */}
              <div
                className="p-4 cursor-pointer hover:bg-gray-50 flex items-center justify-between"
                onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
              >
                <div className="flex-1 flex items-center gap-4">
                  <div>
                    <p className="font-semibold text-gray-900">
                      {item.candidate_name || item.linkedin_profile_slug}
                    </p>
                    <a
                      href={item.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      linkedin.com/in/{item.linkedin_profile_slug}
                    </a>
                    <p className="text-sm text-gray-500">
                      {item.email || "Email not collected"} · {item.phone_number || "Phone not collected"}
                    </p>
                    <p className="text-xs text-gray-400">
                      Added {new Date(item.created_at).toLocaleDateString()} · {item.days_in_pipeline ?? 0}d in pipeline · Next: {item.pending_action}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusBadgeColor(item.status)}`}>
                    {item.status?.replace(/_/g, " ") || "Unknown"}
                  </span>
                  {expandedId === item.id ? "▼" : "▶"}
                </div>
              </div>

              {/* Expanded Details */}
              {expandedId === item.id && (
                <div className="border-t border-gray-200 p-4 bg-gray-50">
                  {/* Current Info */}
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="text-sm font-medium text-gray-700">Name</label>
                      <p className="text-gray-900 mt-1">
                        {item.candidate_id ? (
                          <a href={`/candidates/${item.candidate_id}`} className="text-blue-600 hover:underline">
                            {item.candidate_name}
                          </a>
                        ) : (
                          <span>
                            {item.candidate_name || "—"}
                            {item.candidate_pending && (
                              <span className="ml-2 text-xs text-gray-500">(candidate record being created…)</span>
                            )}
                          </span>
                        )}
                      </p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700">Email</label>
                      <p className="text-gray-900 mt-1">{item.email || "—"}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700">Phone Number</label>
                      <p className="text-gray-900 mt-1">{item.phone_number || "—"}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700">Status</label>
                      <p className="text-gray-900 mt-1">{item.status?.replace(/_/g, " ")}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700">Assigned To</label>
                      <p className="text-gray-900 mt-1">{item.assigned_to || "—"}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700">Next Action</label>
                      <p className="text-gray-900 mt-1">{item.pending_action}</p>
                    </div>
                    {item.notes && (
                      <div>
                        <label className="text-sm font-medium text-gray-700">Notes</label>
                        <p className="text-gray-900 mt-1">{item.notes}</p>
                      </div>
                    )}
                  </div>

                  {/* Status Transitions */}
                  {NEXT_STATUS[item.status] && (
                    <div className="mb-4 p-3 bg-white border border-gray-200 rounded">
                      <label className="text-sm font-medium text-gray-700 block mb-2">
                        Update Status:
                      </label>
                      <div className="flex gap-2 flex-wrap">
                        <button
                          onClick={() => handleUpdateStatus(item.id, NEXT_STATUS[item.status])}
                          className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition"
                        >
                          → {NEXT_STATUS[item.status].replace(/_/g, " ")}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Import Action */}
                  {item.status === "PHONE_COLLECTED" && (
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded">
                      <label className="text-sm font-medium text-blue-900 block mb-2">
                        Ready to import? Add phone number and email:
                      </label>
                      <div className="flex gap-2 flex-wrap">
                        <input
                          type="email"
                          placeholder="Email address"
                          value={emailInput[item.id] ?? item.email ?? ""}
                          onChange={(e) =>
                            setEmailInput({ ...emailInput, [item.id]: e.target.value })
                          }
                          className="flex-1 px-3 py-2 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <input
                          type="tel"
                          placeholder="Phone number"
                          value={phoneInput[item.id] || ""}
                          onChange={(e) =>
                            setPhoneInput({ ...phoneInput, [item.id]: e.target.value })
                          }
                          className="flex-1 px-3 py-2 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <button
                          onClick={() => handleCompleteImport(item.id)}
                          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
                        >
                          <CheckCircle className="w-4 h-4" />
                          Import
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Success State */}
                  {item.status === "IMPORTED_TO_THUNDER" && (
                    <div className="p-3 bg-green-50 border border-green-200 rounded flex items-center gap-2">
                      <CheckCircle className="w-5 h-5 text-green-600" />
                      <div>
                        <p className="font-medium text-green-900">Imported to Thunder</p>
                        <p className="text-sm text-green-700">
                          {item.candidate_name} is ready for Thunder autonomous outreach
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="mt-8 p-4 bg-gray-50 rounded-lg">
        <h3 className="font-medium text-gray-900 mb-3">Pipeline Status Guide</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="inline-block px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-medium mr-2">
              PENDING_CONNECTION
            </span>
            <span className="text-gray-700">Waiting for manual connection on LinkedIn</span>
          </div>
          <div>
            <span className="inline-block px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium mr-2">
              CONNECTED
            </span>
            <span className="text-gray-700">LinkedIn connection accepted</span>
          </div>
          <div>
            <span className="inline-block px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium mr-2">
              PHONE_COLLECTED
            </span>
            <span className="text-gray-700">Phone and email collected, ready to import</span>
          </div>
          <div>
            <span className="inline-block px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium mr-2">
              IMPORTED_TO_THUNDER
            </span>
            <span className="text-gray-700">Candidate created, Thunder loop active</span>
          </div>
        </div>
      </div>
    </div>
  );
}
