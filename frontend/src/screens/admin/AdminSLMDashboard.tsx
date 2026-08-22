import React, { useState, useEffect } from 'react';
import {
  Container,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
  Badge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Alert,
  AlertDescription,
  Progress,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from '@/components/ui';
import { api } from '@/services/api';
import { formatDate, formatNumber } from '@/utils/helpers';

interface Pattern {
  id: number;
  pattern: string;
  lookup_type: string;
  usage_count: number;
  accuracy: number;
  created_at: string;
  last_used: string | null;
  enabled: boolean;
  added_by: string;
}

interface Analytics {
  total_patterns: number;
  simple_patterns: number;
  moderate_patterns: number;
  complex_patterns: number;
  total_questions_30days: number;
  slm_answered: number;
  claude_answered: number;
  local_slm_percentage: number;
  estimated_savings_usd: number;
  top_patterns: Pattern[];
}

interface HistoryItem {
  id: number;
  pattern_id: number;
  action: string;
  changes: Record<string, any>;
  added_by: string;
  created_at: string;
}

interface UnmatchedQuestion {
  question: string;
  suggested_pattern: string;
  suggested_complexity: string;
  count: number;
  confidence: string;
}

export const AdminSLMDashboard: React.FC = () => {
  const [patterns, setPatterns] = useState<{ simple: Pattern[]; moderate: Pattern[]; complex: Pattern[] }>({
    simple: [],
    moderate: [],
    complex: [],
  });
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [unmatchedQuestions, setUnmatchedQuestions] = useState<UnmatchedQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Dialog states
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editingPattern, setEditingPattern] = useState<Pattern | null>(null);
  const [newPatternData, setNewPatternData] = useState({
    pattern: '',
    complexity: 'simple',
    lookup_type: '',
  });

  // Load dashboard data with auto-refresh
  useEffect(() => {
    loadDashboard();
    // Auto-refresh every 30 seconds for real-time updates
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboard = async () => {
    try {
      setLoading(true);

      // Fetch all data in parallel
      const [patternsRes, analyticsRes, historyRes, unmatchedRes] = await Promise.all([
        api.get('/admin/slm/patterns').catch(() => ({ simple: [], moderate: [], complex: [] })),
        api.get('/admin/slm/analytics').catch(() => null),
        api.get('/admin/slm/history').catch(() => []),
        api.get('/admin/slm/unmatched-questions?hours=24').catch(() => ({ suggest_patterns: [] }))
      ]);

      setPatterns(patternsRes);
      setAnalytics(analyticsRes);
      setHistory(historyRes);
      setUnmatchedQuestions(unmatchedRes.suggest_patterns || []);
      setError('');
    } catch (err) {
      setError('Failed to load SLM dashboard');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddPattern = async () => {
    if (!newPatternData.pattern || !newPatternData.lookup_type) {
      setError('Please fill in all fields');
      return;
    }

    try {
      await api.post('/admin/slm/patterns', {
        pattern: newPatternData.pattern,
        complexity: newPatternData.complexity,
        lookup_type: newPatternData.lookup_type,
      });

      setAddDialogOpen(false);
      setNewPatternData({ pattern: '', complexity: 'simple', lookup_type: '' });
      await loadDashboard();
    } catch (err) {
      setError('Failed to add pattern');
    }
  };

  const handleUpdatePattern = async () => {
    if (!editingPattern) return;

    try {
      await api.put(`/admin/slm/patterns/${editingPattern.id}`, {
        pattern: editingPattern.pattern,
        lookup_type: editingPattern.lookup_type,
        enabled: editingPattern.enabled,
      });

      setEditingPattern(null);
      await loadDashboard();
    } catch (err) {
      setError('Failed to update pattern');
    }
  };

  const handleDeletePattern = async (patternId: number) => {
    if (!window.confirm('Disable this pattern?')) return;

    try {
      await api.delete(`/admin/slm/patterns/${patternId}`);
      await loadDashboard();
    } catch (err) {
      setError('Failed to delete pattern');
    }
  };

  const handleQuickAddPattern = async (item: UnmatchedQuestion) => {
    try {
      await api.post('/admin/slm/patterns', {
        pattern: item.suggested_pattern,
        complexity: item.suggested_complexity,
        lookup_type: item.suggested_complexity === 'simple' ? 'job_list' : 'general',
      });

      setError('');
      await loadDashboard();
    } catch (err) {
      setError('Failed to add pattern');
    }
  };

  if (loading) {
    return <div className="p-8 text-center">Loading SLM Dashboard...</div>;
  }

  return (
    <Container className="py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">SLM Management Dashboard</h1>
        <p className="text-gray-600">Monitor and update Thunder's Small Language Model patterns</p>
      </div>

      {error && (
        <Alert className="mb-6 border-red-500 bg-red-50">
          <AlertDescription className="text-red-800">{error}</AlertDescription>
        </Alert>
      )}

      {/* Overview Cards */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Total Patterns</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.total_patterns}</div>
              <p className="text-xs text-gray-500 mt-1">Enabled patterns</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Local SLM Usage</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.local_slm_percentage}%</div>
              <p className="text-xs text-gray-500 mt-1">Of last 30 days</p>
              <Progress value={analytics.local_slm_percentage} className="mt-2 h-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Cost Savings</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">${analytics.estimated_savings_usd}</div>
              <p className="text-xs text-gray-500 mt-1">Last 30 days</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Questions Answered</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatNumber(analytics.total_questions_30days)}</div>
              <p className="text-xs text-gray-500 mt-1">Last 30 days</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="patterns" className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="patterns">Patterns</TabsTrigger>
          <TabsTrigger value="discover">Discover ({unmatchedQuestions.length})</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="import">Import</TabsTrigger>
        </TabsList>

        {/* PATTERNS TAB */}
        <TabsContent value="patterns" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">SLM Patterns</h2>
            <Button onClick={() => setAddDialogOpen(true)} className="bg-blue-600 hover:bg-blue-700">
              + Add Pattern
            </Button>
          </div>

          {/* Simple Patterns */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                Simple Patterns
                <Badge className="ml-2 bg-green-100 text-green-800">
                  {patterns.simple.length}
                </Badge>
              </CardTitle>
              <CardDescription>Database lookups - no external API calls</CardDescription>
            </CardHeader>
            <CardContent>
              <PatternsTable patterns={patterns.simple} onEdit={setEditingPattern} onDelete={handleDeletePattern} />
            </CardContent>
          </Card>

          {/* Moderate Patterns */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                Moderate Patterns
                <Badge className="ml-2 bg-yellow-100 text-yellow-800">
                  {patterns.moderate.length}
                </Badge>
              </CardTitle>
              <CardDescription>Local reasoning - light SLM processing</CardDescription>
            </CardHeader>
            <CardContent>
              <PatternsTable patterns={patterns.moderate} onEdit={setEditingPattern} onDelete={handleDeletePattern} />
            </CardContent>
          </Card>

          {/* Complex Patterns */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                Complex Patterns
                <Badge className="ml-2 bg-red-100 text-red-800">
                  {patterns.complex.length}
                </Badge>
              </CardTitle>
              <CardDescription>Route to Claude - requires advanced reasoning</CardDescription>
            </CardHeader>
            <CardContent>
              <PatternsTable patterns={patterns.complex} onEdit={setEditingPattern} onDelete={handleDeletePattern} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* DISCOVER PATTERNS TAB */}
        <TabsContent value="discover" className="space-y-6">
          <h2 className="text-xl font-semibold">Discover Patterns</h2>

          <Card>
            <CardHeader>
              <CardTitle>
                Unmatched Questions
                <Badge className="ml-2 bg-amber-100 text-amber-800">
                  {unmatchedQuestions.length}
                </Badge>
              </CardTitle>
              <CardDescription>
                Questions your SLM didn't match - candidates for new patterns
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Question</TableHead>
                    <TableHead>Suggested Pattern</TableHead>
                    <TableHead>Complexity</TableHead>
                    <TableHead className="text-right">Count</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {unmatchedQuestions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-gray-500">
                        No unmatched questions yet
                      </TableCell>
                    </TableRow>
                  ) : (
                    unmatchedQuestions.map((item, idx) => (
                      <TableRow key={idx} className="hover:bg-gray-50">
                        <TableCell className="font-mono text-sm max-w-xs truncate">
                          {item.question}
                        </TableCell>
                        <TableCell className="font-mono text-sm font-semibold">
                          "{item.suggested_pattern}"
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              item.suggested_complexity === 'simple'
                                ? 'default'
                                : 'secondary'
                            }
                          >
                            {item.suggested_complexity}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-bold">{item.count}</TableCell>
                        <TableCell>
                          <Badge
                            className={
                              item.confidence === 'HIGH'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-yellow-100 text-yellow-800'
                            }
                          >
                            {item.confidence}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button
                            size="sm"
                            className="bg-green-600 hover:bg-green-700"
                            onClick={() => handleQuickAddPattern(item)}
                          >
                            Add
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ANALYTICS TAB */}
        <TabsContent value="analytics" className="space-y-6">
          <h2 className="text-xl font-semibold">Performance Analytics</h2>

          {analytics && (
            <>
              {/* Distribution Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Pattern Distribution</CardTitle>
                </CardHeader>
                <CardContent className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[analytics]}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="simple_patterns" fill="#10b981" name="Simple" />
                      <Bar dataKey="moderate_patterns" fill="#f59e0b" name="Moderate" />
                      <Bar dataKey="complex_patterns" fill="#ef4444" name="Complex" />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Source Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle>Answers by Source (Last 30 Days)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="flex justify-between mb-2">
                      <span className="font-medium">Local SLM</span>
                      <span className="font-bold">{analytics.slm_answered}</span>
                    </div>
                    <Progress value={(analytics.slm_answered / analytics.total_questions_30days) * 100} />
                  </div>
                  <div>
                    <div className="flex justify-between mb-2">
                      <span className="font-medium">Claude API</span>
                      <span className="font-bold">{analytics.claude_answered}</span>
                    </div>
                    <Progress value={(analytics.claude_answered / analytics.total_questions_30days) * 100} className="bg-gray-200" />
                  </div>
                </CardContent>
              </Card>

              {/* Top Patterns */}
              <Card>
                <CardHeader>
                  <CardTitle>Top 5 Patterns by Usage</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Pattern</TableHead>
                        <TableHead>Complexity</TableHead>
                        <TableHead className="text-right">Usage</TableHead>
                        <TableHead className="text-right">Accuracy</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {analytics.top_patterns.map((p, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-mono text-sm">{p.pattern}</TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                p.complexity === 'simple'
                                  ? 'default'
                                  : p.complexity === 'moderate'
                                    ? 'secondary'
                                    : 'destructive'
                              }
                            >
                              {p.complexity}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">{p.usage_count}</TableCell>
                          <TableCell className="text-right">{p.accuracy}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* HISTORY TAB */}
        <TabsContent value="history" className="space-y-6">
          <h2 className="text-xl font-semibold">Learning History</h2>

          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Pattern</TableHead>
                    <TableHead>Changes</TableHead>
                    <TableHead>Admin</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-gray-500">
                        No updates yet
                      </TableCell>
                    </TableRow>
                  ) : (
                    history.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="text-sm text-gray-600">
                          {formatDate(item.created_at)}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              item.action === 'added'
                                ? 'default'
                                : item.action === 'updated'
                                  ? 'secondary'
                                  : 'destructive'
                            }
                          >
                            {item.action}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{item.pattern_id || 'N/A'}</TableCell>
                        <TableCell className="text-sm text-gray-600">
                          {JSON.stringify(item.changes).slice(0, 50)}...
                        </TableCell>
                        <TableCell className="text-sm">{item.added_by}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* IMPORT TAB */}
        <TabsContent value="import" className="space-y-6">
          <h2 className="text-xl font-semibold">Bulk Import</h2>

          <Card>
            <CardHeader>
              <CardTitle>Import Patterns from JSON</CardTitle>
              <CardDescription>
                Import multiple patterns at once. Format: [{"pattern": "...", "complexity": "simple", "lookup_type": "..."}]
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BulkImportForm onSuccess={loadDashboard} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Add Pattern Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Pattern</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Pattern Text</label>
              <Input
                value={newPatternData.pattern}
                onChange={(e) => setNewPatternData({ ...newPatternData, pattern: e.target.value })}
                placeholder="e.g., 'what jobs', 'available positions'"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Complexity</label>
              <Select value={newPatternData.complexity} onValueChange={(value) => setNewPatternData({ ...newPatternData, complexity: value })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="simple">Simple (Database Lookup)</SelectItem>
                  <SelectItem value="moderate">Moderate (Local Reasoning)</SelectItem>
                  <SelectItem value="complex">Complex (Route to Claude)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Lookup Type</label>
              <Select value={newPatternData.lookup_type} onValueChange={(value) => setNewPatternData({ ...newPatternData, lookup_type: value })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="job_list">Job List</SelectItem>
                  <SelectItem value="candidate_status">Candidate Status</SelectItem>
                  <SelectItem value="job_location">Job Location</SelectItem>
                  <SelectItem value="job_requirements">Job Requirements</SelectItem>
                  <SelectItem value="general">General</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleAddPattern} className="bg-blue-600 hover:bg-blue-700">
                Add Pattern
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Pattern Dialog */}
      <Dialog open={!!editingPattern} onOpenChange={(open) => !open && setEditingPattern(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Pattern</DialogTitle>
          </DialogHeader>
          {editingPattern && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Pattern Text</label>
                <Input
                  value={editingPattern.pattern}
                  onChange={(e) => setEditingPattern({ ...editingPattern, pattern: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Lookup Type</label>
                <Input
                  value={editingPattern.lookup_type}
                  onChange={(e) => setEditingPattern({ ...editingPattern, lookup_type: e.target.value })}
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="enabled"
                  checked={editingPattern.enabled}
                  onChange={(e) => setEditingPattern({ ...editingPattern, enabled: e.target.checked })}
                />
                <label htmlFor="enabled" className="text-sm font-medium">
                  Enabled
                </label>
              </div>

              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => setEditingPattern(null)}>
                  Cancel
                </Button>
                <Button onClick={handleUpdatePattern} className="bg-blue-600 hover:bg-blue-700">
                  Save Changes
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Container>
  );
};

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

interface PatternsTableProps {
  patterns: Pattern[];
  onEdit: (pattern: Pattern) => void;
  onDelete: (id: number) => void;
}

const PatternsTable: React.FC<PatternsTableProps> = ({ patterns, onEdit, onDelete }) => {
  if (patterns.length === 0) {
    return <div className="text-center py-8 text-gray-500">No patterns yet</div>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Pattern</TableHead>
          <TableHead>Lookup Type</TableHead>
          <TableHead className="text-right">Usage</TableHead>
          <TableHead className="text-right">Accuracy</TableHead>
          <TableHead>Last Used</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {patterns.map((pattern) => (
          <TableRow key={pattern.id}>
            <TableCell className="font-mono text-sm">{pattern.pattern}</TableCell>
            <TableCell className="text-sm">{pattern.lookup_type}</TableCell>
            <TableCell className="text-right font-medium">{pattern.usage_count}</TableCell>
            <TableCell className="text-right">
              <span className={pattern.accuracy >= 95 ? 'text-green-600' : pattern.accuracy >= 80 ? 'text-yellow-600' : 'text-red-600'}>
                {pattern.accuracy}%
              </span>
            </TableCell>
            <TableCell className="text-sm text-gray-600">
              {pattern.last_used ? formatDate(pattern.last_used) : 'Never'}
            </TableCell>
            <TableCell>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onEdit(pattern)}
                  className="text-xs"
                >
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => onDelete(pattern.id)}
                  className="text-xs"
                >
                  Disable
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

interface BulkImportFormProps {
  onSuccess: () => void;
}

const BulkImportForm: React.FC<BulkImportFormProps> = ({ onSuccess }) => {
  const [jsonData, setJsonData] = useState('');
  const [importing, setImporting] = useState(false);

  const handleImport = async () => {
    try {
      setImporting(true);
      const patterns = JSON.parse(jsonData);
      await api.post('/admin/slm/patterns/bulk-import', { patterns });
      setJsonData('');
      onSuccess();
    } catch (err) {
      alert('Invalid JSON format');
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-4">
      <Textarea
        value={jsonData}
        onChange={(e) => setJsonData(e.target.value)}
        placeholder={`[
  {"pattern": "available jobs", "complexity": "simple", "lookup_type": "job_list"},
  {"pattern": "my status", "complexity": "simple", "lookup_type": "candidate_status"}
]`}
        className="font-mono text-sm h-64"
      />
      <Button onClick={handleImport} disabled={importing} className="w-full bg-blue-600 hover:bg-blue-700">
        {importing ? 'Importing...' : 'Import Patterns'}
      </Button>
    </div>
  );
};
