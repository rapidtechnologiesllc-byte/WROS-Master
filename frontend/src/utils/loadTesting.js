/**
 * Load Testing Utility
 * Stress tests the candidate creation endpoint with concurrent requests
 */

import { apiRequest } from '../services/api/client';

export const LoadTestRunner = {
  /**
   * Run concurrent candidate creation requests
   * @param {number} concurrency - Number of concurrent requests
   * @param {number} iterations - Number of iterations per concurrent request
   * @returns {Promise} Results including success/failure counts and timing
   */
  async runCandidateCreationTest(concurrency = 10, iterations = 10) {
    const results = {
      total: concurrency * iterations,
      succeeded: 0,
      failed: 0,
      errors: [],
      totalTimeMs: 0,
      avgTimeMs: 0,
      minTimeMs: Infinity,
      maxTimeMs: 0,
      successRate: 0,
      timestamps: []
    };

    const startTime = performance.now();

    // Create concurrent batches
    const batches = [];
    for (let batch = 0; batch < concurrency; batch++) {
      const batchPromises = [];

      for (let i = 0; i < iterations; i++) {
        const timestamp = Date.now();
        const requestStart = performance.now();

        const candidateData = {
          candidate_email: `loadtest-${batch}-${i}-${timestamp}@example.com`,
          candidate_first_name: `LoadTest${batch}`,
          candidate_last_name: `User${i}`,
          candidate_current_location: 'New York, NY, USA',
          candidate_mobile: '5550000' + String(i).padStart(3, '0'),
          candidate_gender: 'Not Specified',
          candidate_source: 'Load Testing'
        };

        batchPromises.push(
          (async () => {
            try {
              await apiRequest('/candidates/create', {
                method: 'POST',
                body: JSON.stringify(candidateData),
              });

              const requestEnd = performance.now();
              const duration = requestEnd - requestStart;

              results.timestamps.push({
                batch,
                index: i,
                duration,
                timestamp,
                status: 'success'
              });

              results.succeeded++;
              results.minTimeMs = Math.min(results.minTimeMs, duration);
              results.maxTimeMs = Math.max(results.maxTimeMs, duration);

              return { success: true, duration };
            } catch (error) {
              const requestEnd = performance.now();
              const duration = requestEnd - requestStart;

              results.timestamps.push({
                batch,
                index: i,
                duration,
                timestamp,
                status: 'failed',
                error: error.message
              });

              results.failed++;
              results.errors.push({
                batch,
                index: i,
                error: error.message
              });

              return { success: false, duration, error: error.message };
            }
          })()
        );
      }

      batches.push(Promise.all(batchPromises));
    }

    // Execute all batches
    await Promise.all(batches);

    const endTime = performance.now();
    results.totalTimeMs = endTime - startTime;
    results.avgTimeMs = results.totalTimeMs / results.total;
    results.successRate = (results.succeeded / results.total) * 100;

    return results;
  },

  /**
   * Format results for display
   */
  formatResults(results) {
    return `
Load Test Results
=================
Total Requests: ${results.total}
Successful: ${results.succeeded} (${results.successRate.toFixed(1)}%)
Failed: ${results.failed}

Performance Metrics:
- Total Time: ${results.totalTimeMs.toFixed(2)}ms
- Average: ${results.avgTimeMs.toFixed(2)}ms per request
- Min: ${results.minTimeMs === Infinity ? 'N/A' : results.minTimeMs.toFixed(2)}ms
- Max: ${results.maxTimeMs.toFixed(2)}ms

${results.failed > 0 ? `\nErrors:\n${results.errors.map(e => `- Batch ${e.batch} Index ${e.index}: ${e.error}`).join('\n')}` : 'No errors!'}
    `.trim();
  }
};

export default LoadTestRunner;
