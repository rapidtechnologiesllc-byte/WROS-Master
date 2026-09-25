/**
 * Queue Monitoring Dashboard
 * Displays real-time queue statistics and performance metrics
 */
import { useEffect, useState } from 'react';
import { Activity, TrendingUp, AlertCircle } from 'lucide-react';
import { Card, Button } from './ui';
import { apiRequest } from '../services/api/client';

export default function QueueMonitoring() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchQueueStats = async () => {
    try {
      setLoading(true);
      const response = await apiRequest('/message-queue/stats', {
        method: 'GET',
      });

      if (response?.data) {
        setStats(response.data);
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Failed to fetch queue stats:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueueStats();

    if (autoRefresh) {
      const interval = setInterval(fetchQueueStats, 10000); // Refresh every 10 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  if (!stats) {
    return (
      <Card title="Queue Monitoring" icon={<Activity className="h-4 w-4" />}>
        <div className="flex items-center justify-center py-8">
          <p className="text-gray-500">Loading queue statistics...</p>
        </div>
      </Card>
    );
  }

  const getHealthStatus = () => {
    if (stats.pending > 100) return { status: 'warning', label: 'High Load' };
    if (stats.failed > 10) return { status: 'error', label: 'High Error Rate' };
    return { status: 'healthy', label: 'Healthy' };
  };

  const health = getHealthStatus();

  return (
    <Card
      title="Queue Monitoring"
      icon={<Activity className="h-4 w-4" />}
      right={
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            {autoRefresh ? 'Auto: On' : 'Auto: Off'}
          </Button>
          <Button
            size="sm"
            onClick={fetchQueueStats}
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </Button>
        </div>
      }
    >
      {/* Health Status */}
      <div className="mb-6 rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2">
          <div className={`h-3 w-3 rounded-full ${
            health.status === 'healthy' ? 'bg-green-500' :
            health.status === 'warning' ? 'bg-yellow-500' :
            'bg-red-500'
          }`} />
          <span className="font-medium">Status: {health.label}</span>
        </div>
        {lastUpdate && (
          <p className="mt-2 text-xs text-gray-500">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </p>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Total Messages */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Messages</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_messages || 0}</p>
            </div>
            <TrendingUp className="h-6 w-6 text-blue-500" />
          </div>
        </div>

        {/* Pending */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Pending</p>
              <p className="text-2xl font-bold text-yellow-600">{stats.pending || 0}</p>
            </div>
            <Activity className="h-6 w-6 text-yellow-500" />
          </div>
          <p className="mt-2 text-xs text-gray-500">
            {stats.pending > 0 ? `${stats.pending} waiting to process` : 'Queue empty'}
          </p>
        </div>

        {/* Processing */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Processing</p>
              <p className="text-2xl font-bold text-blue-600">{stats.processing || 0}</p>
            </div>
            <Activity className="h-6 w-6 text-blue-500" />
          </div>
        </div>

        {/* Completed */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Completed</p>
              <p className="text-2xl font-bold text-green-600">{stats.completed || 0}</p>
            </div>
            <TrendingUp className="h-6 w-6 text-green-500" />
          </div>
        </div>

        {/* Failed */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Failed</p>
              <p className="text-2xl font-bold text-red-600">{stats.failed || 0}</p>
            </div>
            <AlertCircle className="h-6 w-6 text-red-500" />
          </div>
          {stats.failed > 0 && (
            <p className="mt-2 text-xs text-red-500">Action required</p>
          )}
        </div>

        {/* Success Rate */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Success Rate</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats.total_messages > 0
                  ? (((stats.total_messages - (stats.failed || 0)) / stats.total_messages) * 100).toFixed(1)
                  : 'N/A'
                }%
              </p>
            </div>
            <TrendingUp className="h-6 w-6 text-gray-400" />
          </div>
        </div>
      </div>

      {/* Queue Type Breakdown */}
      {stats.by_queue && Object.keys(stats.by_queue).length > 0 && (
        <div className="mt-6 rounded-lg border border-gray-200 p-4">
          <h3 className="mb-4 font-medium text-gray-900">Queue Types</h3>
          <div className="grid gap-2 md:grid-cols-2">
            {Object.entries(stats.by_queue).map(([queueType, count]) => (
              <div key={queueType} className="flex justify-between text-sm">
                <span className="text-gray-600">{queueType}</span>
                <span className="font-medium text-gray-900">{count} messages</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts */}
      {stats.pending > 50 && (
        <div className="mt-4 rounded-lg border-l-4 border-yellow-500 bg-yellow-50 p-3">
          <p className="text-sm font-medium text-yellow-800">
            ⚠️ High queue backlog: {stats.pending} pending messages
          </p>
        </div>
      )}

      {stats.failed > 5 && (
        <div className="mt-2 rounded-lg border-l-4 border-red-500 bg-red-50 p-3">
          <p className="text-sm font-medium text-red-800">
            🚨 High error rate: {stats.failed} failed messages
          </p>
        </div>
      )}
    </Card>
  );
}
