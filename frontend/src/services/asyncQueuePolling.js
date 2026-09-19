/**
 * Async Queue Polling Utility
 * Handles polling for async operations that return immediately with queued status.
 */

/**
 * Poll for status of an async operation (job or candidate creation).
 * Polls every 2 seconds until status reaches terminal state (PROCESSING, COMPLETED, ERROR, etc.).
 *
 * @param {Object} options - Polling configuration
 * @param {string} options.entityType - 'job' or 'candidate'
 * @param {string} options.entityId - ID of the created entity
 * @param {function} options.fetchStatus - Async function that returns { status, ... }
 * @param {function} options.onStatusChange - Callback when status changes: (status, data) => {}
 * @param {number} options.pollIntervalMs - Poll interval in ms (default 2000)
 * @param {number} options.maxWaitMs - Max time to poll (default 5 minutes)
 * @returns {Promise<Object>} Final status response
 */
export const pollAsyncQueueStatus = async ({
  entityType = "job",
  entityId,
  fetchStatus,
  onStatusChange,
  pollIntervalMs = 2000,
  maxWaitMs = 5 * 60 * 1000, // 5 minutes
}) => {
  if (!entityId) {
    throw new Error("Entity ID is required for polling");
  }

  const startTime = Date.now();
  let lastStatus = null;
  let pollCount = 0;

  console.debug(`[AsyncQueuePolling] Starting poll for ${entityType} ${entityId}`);

  while (Date.now() - startTime < maxWaitMs) {
    try {
      pollCount++;
      const statusData = await fetchStatus();
      const currentStatus = statusData?.status;

      // Notify on status change
      if (currentStatus !== lastStatus) {
        console.debug(
          `[AsyncQueuePolling] ${entityType} ${entityId} status: ${currentStatus} (poll #${pollCount})`
        );
        if (onStatusChange) {
          onStatusChange(currentStatus, statusData);
        }
        lastStatus = currentStatus;
      }

      // Terminal states - stop polling
      if (
        currentStatus === "PROCESSING" ||
        currentStatus === "COMPLETED" ||
        currentStatus === "ERROR" ||
        currentStatus === "FAILED" ||
        currentStatus === "SUBMITTED" ||
        currentStatus === "ACTIVE"
      ) {
        console.debug(
          `[AsyncQueuePolling] ${entityType} ${entityId} reached terminal state: ${currentStatus}`
        );
        return statusData;
      }

      // Wait before next poll
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    } catch (error) {
      console.error(
        `[AsyncQueuePolling] Error polling ${entityType} ${entityId}:`,
        error
      );
      throw error;
    }
  }

  // Timeout
  const timeoutError = new Error(
    `Operation timed out after ${maxWaitMs / 1000} seconds. Your ${entityType} is still being processed. Please refresh the page to check status.`
  );
  timeoutError.isPollingTimeout = true;
  throw timeoutError;
};

/**
 * Create a polling function for a specific entity.
 * Handles the fetch logic transparently.
 */
export const createJobStatusPoller = (jobId, apiRequest) => {
  return async () => {
    try {
      const { data } = await apiRequest(`/jobs/${jobId}/status`, {
        method: "GET",
      });
      return data;
    } catch (err) {
      console.error(`[createJobStatusPoller] Failed to fetch job ${jobId} status:`, err);
      throw err;
    }
  };
};

export const createCandidateStatusPoller = (candidateId, apiRequest) => {
  return async () => {
    try {
      const { data } = await apiRequest(`/candidates/${candidateId}/status`, {
        method: "GET",
      });
      return data;
    } catch (err) {
      console.error(`[createCandidateStatusPoller] Failed to fetch candidate ${candidateId} status:`, err);
      throw err;
    }
  };
};

/**
 * Detect if a response indicates async queuing.
 * Job/candidate creation should return:
 * - { status: "QUEUED", job_id: "...", message: "Job queued..." }
 * - OR { status: "PENDING", candidate_id: "...", message: "..." }
 */
export const isAsyncQueuedResponse = (response) => {
  const status = response?.status;
  return (
    status === "QUEUED" ||
    status === "PENDING" ||
    status === "PROCESSING" ||
    status === "ENQUEUED"
  );
};
