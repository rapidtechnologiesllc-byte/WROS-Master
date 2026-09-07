import React, { useState, useEffect } from 'react';

export default function MessageQueueDashboard() {
  const [workers, setWorkers] = useState([]);
  const [queues, setQueues] = useState([]);
  const [selectedQueue, setSelectedQueue] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  useEffect(() => {
    fetchWorkers();
    fetchQueues();
    fetchStats();
    const interval = setInterval(() => {
      fetchWorkers();
      fetchQueues();
      fetchStats();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedQueue) {
      fetchQueueTasks(selectedQueue);
    }
  }, [selectedQueue]);

  const fetchWorkers = () => {
    const token = localStorage.getItem('hrms_token');
    fetch('http://localhost:8080/api/v1/celery/workers', {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    }).then(r => r.json()).then(data => {
      setWorkers(data.workers || []);
    }).catch(err => {
      console.error('Failed to fetch workers:', err);
      setWorkers([]);
    });
  };

  const fetchQueues = () => {
    const token = localStorage.getItem('hrms_token');
    fetch('http://localhost:8080/api/v1/celery/queues', {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    }).then(r => r.json()).then(data => {
      setQueues(data.queues || []);
    }).catch(err => {
      console.error('Failed to fetch queues:', err);
      setQueues([]);
    });
  };

  const fetchStats = () => {
    const token = localStorage.getItem('hrms_token');
    fetch('http://localhost:8080/api/v1/celery/stats', {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    }).then(r => r.json()).then(data => {
      setStats(data);
      setLastUpdate(new Date());
    }).catch(err => {
      console.error('Failed to fetch stats:', err);
      setStats(null);
      setLastUpdate(new Date());
    });
  };

  const fetchQueueTasks = (queueName) => {
    const token = localStorage.getItem('hrms_token');
    fetch(`http://localhost:8080/api/v1/celery/queue/${queueName}/tasks`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    }).then(r => r.json()).then(data => {
      setTasks(data.tasks || []);
    }).catch(err => {
      console.error(`Failed to fetch ${queueName} tasks:`, err);
      setTasks([]);
    });
  };

  return (
    <div className="h-full w-full bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Message Queue</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">Celery task queue monitoring</p>
          <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">Updated: {lastUpdate.toLocaleTimeString()}</p>
        </div>

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm">
              <p className="text-gray-600 dark:text-gray-400 text-sm">Pending</p>
              <p className="text-3xl font-bold text-amber-600">{stats.pending}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm">
              <p className="text-gray-600 dark:text-gray-400 text-sm">Active</p>
              <p className="text-3xl font-bold text-blue-600">{stats.active}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm">
              <p className="text-gray-600 dark:text-gray-400 text-sm">Reserved</p>
              <p className="text-3xl font-bold text-purple-600">{stats.reserved}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm">
              <p className="text-gray-600 dark:text-gray-400 text-sm">Scheduled</p>
              <p className="text-3xl font-bold text-green-600">{stats.scheduled}</p>
            </div>
          </div>
        )}

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Queues ({queues.length})</h2>
          </div>
          {queues.length === 0 ? (
            <p className="text-gray-500">No queues found</p>
          ) : (
            <div className="space-y-2">
              {queues.map((q) => (
                <button
                  key={q.key}
                  onClick={() => setSelectedQueue(q.name)}
                  className={`w-full text-left p-4 rounded transition-colors ${
                    selectedQueue === q.name
                      ? 'bg-blue-100 dark:bg-blue-900/30'
                      : 'bg-gray-50 dark:bg-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <div className="flex justify-between">
                    <span className="font-mono text-sm">{q.name}</span>
                    <span className="font-bold text-amber-600">{q.pending} pending</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Worker Status */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold mb-4">Worker Status</h2>
          {workers.length === 0 ? (
            <p className="text-gray-500">No workers running</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {workers.map((w, i) => (
                <div key={i} className={`p-4 rounded border-2 ${w.status === 'working' ? 'border-green-500 bg-green-50 dark:bg-green-900' : 'border-gray-300 bg-gray-50 dark:bg-gray-700'}`}>
                  <p className="font-semibold text-sm">{w.name}</p>
                  <p className={`text-sm font-bold ${w.status === 'working' ? 'text-green-600' : 'text-gray-600'}`}>{w.status.toUpperCase()}</p>
                  <p className="text-xs text-gray-600 mt-2">Active: {w.active_tasks} | Pool: {w.pool_size}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Queue metrics table */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">Queue Task States</h2>
          {queues.length === 0 ? (
            <p className="text-gray-500">No queues</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b-2 bg-gray-50 dark:bg-gray-700">
                  <tr>
                    <th className="text-left py-3 px-4 font-semibold">Queue</th>
                    <th className="text-center py-3 px-4 font-semibold">Idle</th>
                    <th className="text-center py-3 px-4 font-semibold text-amber-600">Pending</th>
                    <th className="text-center py-3 px-4 font-semibold text-blue-600">Active</th>
                    <th className="text-center py-3 px-4 font-semibold text-purple-600">Reserved</th>
                    <th className="text-center py-3 px-4 font-semibold text-red-600">Failed</th>
                    <th className="text-center py-3 px-4 font-semibold text-green-600">Finished</th>
                  </tr>
                </thead>
                <tbody>
                  {queues.map((q, i) => (
                    <tr
                      key={i}
                      className="border-b hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition-colors"
                      onClick={() => setSelectedQueue(q.name)}
                    >
                      <td className="py-3 px-4 font-semibold text-orange-600">{q.name.toUpperCase()}</td>
                      <td className="text-center py-3 px-4">
                        <span className="inline-block px-2 py-1 bg-gray-300 text-gray-900 text-xs font-bold rounded">Idle</span>
                      </td>
                      <td className="text-center py-3 px-4">
                        <span className="inline-block px-3 py-1 bg-amber-100 text-amber-900 font-semibold rounded">{q.pending}</span>
                      </td>
                      <td className="text-center py-3 px-4">
                        <span className="inline-block px-3 py-1 bg-blue-100 text-blue-900 font-semibold rounded">{q.active}</span>
                      </td>
                      <td className="text-center py-3 px-4">
                        <span className="inline-block px-3 py-1 bg-purple-100 text-purple-900 font-semibold rounded">{q.reserved}</span>
                      </td>
                      <td className="text-center py-3 px-4">
                        <span className="inline-block px-3 py-1 bg-red-100 text-red-900 font-semibold rounded">{q.failed || 0}</span>
                      </td>
                      <td className="text-center py-3 px-4">
                        <span className="inline-block px-3 py-1 bg-green-100 text-green-900 font-semibold rounded">{q.completed || 0}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {selectedQueue && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-6 mt-6">
            <div className="flex justify-between mb-4">
              <h2 className="text-lg font-semibold">
                Messages in <code className="text-blue-600">{selectedQueue}</code>
              </h2>
              <button
                onClick={() => setSelectedQueue(null)}
                className="text-sm text-gray-500 hover:text-gray-700 font-bold"
              >
                ✕
              </button>
            </div>
            {tasks.length === 0 ? (
              <p className="text-center py-8 text-gray-500">No tasks in queue</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b-2">
                  <tr>
                    <th className="text-left py-2 px-4">Task Name</th>
                    <th className="text-left py-2 px-4">Reason</th>
                    <th className="text-left py-2 px-4">Task ID</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t, i) => (
                    <tr key={i} className="border-b hover:bg-gray-50">
                      <td className="py-2 px-4 font-semibold">{t.name}</td>
                      <td className="py-2 px-4 text-gray-700">{t.reason || 'Processing...'}</td>
                      <td className="py-2 px-4 font-mono text-xs truncate">{t.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
