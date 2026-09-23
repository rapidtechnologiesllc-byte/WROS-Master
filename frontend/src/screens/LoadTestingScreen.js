/**
 * Load Testing Screen
 * UI for running stress tests on candidate creation endpoint
 */
import { useState } from 'react';
import { Zap, TrendingUp } from 'lucide-react';
import { Card, Button, Input } from '../components/ui';
import LoadTestRunner from '../utils/loadTesting';
import { useScreenBanner, ScreenLevelBanner } from '../components/ScreenLevelBanner';

export default function LoadTestingScreen() {
  const { banner, showSuccess, showError, dismiss } = useScreenBanner();
  const [concurrency, setConcurrency] = useState('10');
  const [iterations, setIterations] = useState('5');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);

  const handleRunTest = async () => {
    const concNum = parseInt(concurrency, 10);
    const iterNum = parseInt(iterations, 10);

    if (isNaN(concNum) || concNum < 1 || isNaN(iterNum) || iterNum < 1) {
      showError('Please enter valid positive numbers for concurrency and iterations');
      return;
    }

    if (concNum * iterNum > 1000) {
      showError('Maximum 1000 total requests per test. Reduce concurrency or iterations.');
      return;
    }

    setIsRunning(true);
    setResults(null);

    try {
      showSuccess(`Starting load test: ${concNum} concurrent × ${iterNum} iterations = ${concNum * iterNum} total requests...`);

      const testResults = await LoadTestRunner.runCandidateCreationTest(concNum, iterNum);
      setResults(testResults);

      showSuccess(`Load test completed! Success rate: ${testResults.successRate.toFixed(1)}%`);
    } catch (error) {
      showError(`Load test failed: ${error.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Load Testing"
        icon={<Zap className="h-4 w-4" />}
      >
        {banner && (
          <ScreenLevelBanner
            type={banner.type}
            message={banner.message}
            onDismiss={dismiss}
          />
        )}

        {/* Test Configuration */}
        <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <h3 className="mb-4 font-medium text-gray-900">Test Configuration</h3>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Input
                label="Concurrent Requests"
                type="number"
                value={concurrency}
                onChange={setConcurrency}
                disabled={isRunning}
                placeholder="10"
                min="1"
                max="100"
              />
              <p className="mt-1 text-xs text-gray-600">
                Number of simultaneous requests
              </p>
            </div>

            <div>
              <Input
                label="Iterations Per Request"
                type="number"
                value={iterations}
                onChange={setIterations}
                disabled={isRunning}
                placeholder="5"
                min="1"
                max="100"
              />
              <p className="mt-1 text-xs text-gray-600">
                How many times to repeat each concurrent request
              </p>
            </div>
          </div>

          <div className="mt-4 text-sm">
            <p className="text-gray-600">
              Total Requests: <span className="font-bold">{parseInt(concurrency, 10) * parseInt(iterations, 10) || 0}</span>
            </p>
          </div>

          <Button
            onClick={handleRunTest}
            disabled={isRunning}
            className="mt-4 w-full"
          >
            {isRunning ? 'Running Test...' : 'Start Load Test'}
          </Button>
        </div>

        {/* Results Display */}
        {results && (
          <div className="rounded-lg border border-gray-200 p-4">
            <h3 className="mb-4 flex items-center gap-2 font-medium text-gray-900">
              <TrendingUp className="h-4 w-4" />
              Test Results
            </h3>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {/* Summary */}
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-600">Total Requests</p>
                <p className="text-2xl font-bold text-gray-900">{results.total}</p>
              </div>

              <div className="rounded-lg bg-green-50 p-3">
                <p className="text-xs text-gray-600">Successful</p>
                <p className="text-2xl font-bold text-green-600">{results.succeeded}</p>
              </div>

              <div className="rounded-lg bg-red-50 p-3">
                <p className="text-xs text-gray-600">Failed</p>
                <p className="text-2xl font-bold text-red-600">{results.failed}</p>
              </div>

              {/* Performance */}
              <div className="rounded-lg bg-blue-50 p-3">
                <p className="text-xs text-gray-600">Success Rate</p>
                <p className="text-2xl font-bold text-blue-600">{results.successRate.toFixed(1)}%</p>
              </div>

              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-600">Avg Response Time</p>
                <p className="text-2xl font-bold text-gray-900">{results.avgTimeMs.toFixed(0)}ms</p>
              </div>

              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-600">Total Duration</p>
                <p className="text-2xl font-bold text-gray-900">{(results.totalTimeMs / 1000).toFixed(2)}s</p>
              </div>

              {/* Timing Details */}
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-600">Min Response Time</p>
                <p className="text-lg font-bold text-gray-900">
                  {results.minTimeMs === Infinity ? 'N/A' : results.minTimeMs.toFixed(2)}ms
                </p>
              </div>

              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-600">Max Response Time</p>
                <p className="text-lg font-bold text-gray-900">{results.maxTimeMs.toFixed(2)}ms</p>
              </div>

              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-600">Requests/Second</p>
                <p className="text-lg font-bold text-gray-900">
                  {(results.total / (results.totalTimeMs / 1000)).toFixed(2)}
                </p>
              </div>
            </div>

            {/* Errors */}
            {results.errors.length > 0 && (
              <div className="mt-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-3">
                <p className="font-medium text-red-900">Errors ({results.errors.length})</p>
                <div className="mt-2 max-h-40 overflow-y-auto text-xs font-mono text-red-700">
                  {results.errors.slice(0, 5).map((err, idx) => (
                    <div key={idx}>Batch {err.batch} #{err.index}: {err.error}</div>
                  ))}
                  {results.errors.length > 5 && (
                    <div className="mt-1 text-red-600">... and {results.errors.length - 5} more</div>
                  )}
                </div>
              </div>
            )}

            {/* Interpretation */}
            <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3">
              <p className="text-sm font-medium text-gray-900">Performance Assessment</p>
              <ul className="mt-2 space-y-1 text-xs text-gray-600">
                <li>
                  • Average response time: {results.avgTimeMs < 500 ? '✓ Excellent' : results.avgTimeMs < 1000 ? '△ Good' : '✗ Needs optimization'}
                </li>
                <li>
                  • Success rate: {results.successRate >= 99 ? '✓ Excellent' : results.successRate >= 95 ? '△ Good' : '✗ Needs investigation'}
                </li>
                <li>
                  • Throughput: {(results.total / (results.totalTimeMs / 1000)).toFixed(2)} req/sec
                </li>
              </ul>
            </div>
          </div>
        )}

        {/* Info Box */}
        <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <h4 className="font-medium text-gray-900">About Load Testing</h4>
          <ul className="mt-2 space-y-1 text-xs text-gray-600">
            <li>• Simulates multiple concurrent candidate creation requests</li>
            <li>• Each request creates a unique candidate with test email</li>
            <li>• Measures response times and success rates</li>
            <li>• Maximum 1000 total requests per test (to prevent overwhelming the backend)</li>
            <li>• Results help identify performance bottlenecks and scalability limits</li>
          </ul>
        </div>
      </Card>
    </div>
  );
}
