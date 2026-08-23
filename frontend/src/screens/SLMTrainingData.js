import React, { useState, useEffect } from 'react';
import { Database, Download, Upload, RefreshCw, AlertCircle, CheckCircle, Zap } from 'lucide-react';

export default function SLMTrainingData() {
  const [trainingBatch, setTrainingBatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  useEffect(() => {
    loadTrainingBatch();
  }, []);

  const loadTrainingBatch = async () => {
    try {
      setLoading(true);
      const resp = await fetch('/api/v1/slm/feedback/training-batch?min_examples=20');
      if (resp.ok) {
        setTrainingBatch(await resp.json());
      }
    } catch (error) {
      console.error('Failed to load training batch:', error);
    } finally {
      setLoading(false);
    }
  };

  const copyPromptToClipboard = () => {
    if (trainingBatch?.claude_prompt) {
      navigator.clipboard.writeText(trainingBatch.claude_prompt);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <RefreshCw className="animate-spin mx-auto mb-4" size={32} />
          <p>Loading training data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-purple-700 text-white p-6 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Database size={32} /> SLM Training Data
            </h1>
            <p className="text-purple-100 mt-2">Collect, validate, and prepare training data for model improvement</p>
          </div>
        </div>
      </div>

      {/* Three-Stage Pipeline */}
      <div className="grid grid-cols-3 gap-4">
        {/* Stage 1: Collect Real Examples */}
        <div className="bg-white rounded-lg shadow p-6 border-t-4 border-blue-500">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <span className="bg-blue-500 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm">1</span>
            Collect Real Examples
          </h2>

          <div className="space-y-4">
            <div className="text-sm text-gray-600">
              <p className="mb-2"><strong>Goal:</strong> Collect 50-100 validated resume examples</p>
              <p className="mb-2"><strong>Time:</strong> 2-3 hours (interactive)</p>
              <p className="mb-2"><strong>Process:</strong> Extract text, parse with SLM, validate</p>
            </div>

            <div className="bg-blue-50 p-4 rounded font-mono text-xs border border-blue-200">
              <div className="text-gray-600 mb-2">$ Run this command:</div>
              <div className="text-blue-700 break-all">
                python collect_training_data.py --resume-dir "C:\\...\\Resumes" --output training_data.json
              </div>
            </div>

            <div className="bg-blue-50 p-3 rounded text-xs text-blue-700 border border-blue-200">
              📝 You'll be prompted to validate each resume extraction interactively
            </div>
          </div>
        </div>

        {/* Stage 2: Generate Synthetic Examples */}
        <div className="bg-white rounded-lg shadow p-6 border-t-4 border-purple-500">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <span className="bg-purple-500 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm">2</span>
            Generate Synthetic
          </h2>

          <div className="space-y-4">
            <div className="text-sm text-gray-600">
              <p className="mb-2"><strong>Goal:</strong> Expand 50-100 real → 5000+ synthetic</p>
              <p className="mb-2"><strong>Time:</strong> 15-30 minutes</p>
              <p className="mb-2"><strong>Method:</strong> Claude API variations</p>
            </div>

            <div className="bg-purple-50 p-4 rounded font-mono text-xs border border-purple-200">
              <div className="text-gray-600 mb-2">$ Run this command:</div>
              <div className="text-purple-700 break-all">
                python generate_synthetic_examples.py --input training_data.json --output synthetic_data.json
              </div>
            </div>

            <div className="bg-purple-50 p-3 rounded text-xs text-purple-700 border border-purple-200">
              🤖 Claude generates realistic variations (different names, companies, dates, skills)
            </div>
          </div>
        </div>

        {/* Stage 3: Fine-Tune BERT */}
        <div className="bg-white rounded-lg shadow p-6 border-t-4 border-green-500">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <span className="bg-green-500 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm">3</span>
            Fine-Tune BERT
          </h2>

          <div className="space-y-4">
            <div className="text-sm text-gray-600">
              <p className="mb-2"><strong>Goal:</strong> Train ML model on 5000+ examples</p>
              <p className="mb-2"><strong>Time:</strong> 30-120 minutes</p>
              <p className="mb-2"><strong>Result:</strong> 92%+ accuracy model</p>
            </div>

            <div className="bg-green-50 p-4 rounded font-mono text-xs border border-green-200">
              <div className="text-gray-600 mb-2">$ Run this command:</div>
              <div className="text-green-700 break-all">
                python fine_tune_bert.py --training-data training_data.json --synthetic-data synthetic_data.json
              </div>
            </div>

            <div className="bg-green-50 p-3 rounded text-xs text-green-700 border border-green-200">
              ⚡ Trains with GPU (1 hour) or CPU (2+ hours)
            </div>
          </div>
        </div>
      </div>

      {/* Training Batch Status */}
      {trainingBatch && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Training Batch Status</h2>

          {trainingBatch.status === 'insufficient_data' ? (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded">
              <div className="flex items-start gap-3">
                <AlertCircle className="text-yellow-600 mt-1" size={20} />
                <div>
                  <h3 className="font-semibold text-yellow-700 mb-1">Need More Training Data</h3>
                  <p className="text-sm text-yellow-600">
                    Collect at least 20 real examples before generating synthetic data. Currently have:{' '}
                    <strong>{trainingBatch.versions_available || 0}</strong> examples.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-blue-50 p-4 rounded border border-blue-200">
                  <div className="text-sm text-blue-600">Total Examples</div>
                  <div className="text-3xl font-bold text-blue-700">{trainingBatch.total_examples}</div>
                </div>

                <div className="bg-purple-50 p-4 rounded border border-purple-200">
                  <div className="text-sm text-purple-600">By Field</div>
                  <div className="text-3xl font-bold text-purple-700">
                    {Object.keys(trainingBatch.by_field_summary || {}).length}
                  </div>
                </div>

                <div className="bg-green-50 p-4 rounded border border-green-200">
                  <div className="text-sm text-green-600">Ready to Send</div>
                  <div className="text-3xl font-bold text-green-700">✓</div>
                </div>
              </div>

              {/* Field Breakdown */}
              <div>
                <h3 className="font-semibold text-gray-700 mb-3">Training Data by Field</h3>
                <div className="grid grid-cols-3 gap-4">
                  {Object.entries(trainingBatch.by_field_summary || {}).map(([field, count]) => (
                    <div key={field} className="bg-gray-50 p-3 rounded border border-gray-200">
                      <div className="text-sm text-gray-600 capitalize">{field}</div>
                      <div className="text-2xl font-bold text-gray-700">{count}</div>
                      <div className="text-xs text-gray-500">examples</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Claude Prompt */}
              <div className="bg-blue-50 p-4 rounded border border-blue-200">
                <h3 className="font-semibold text-blue-700 mb-3 flex items-center gap-2">
                  <Zap size={18} /> Ready for Claude
                </h3>

                <p className="text-sm text-blue-600 mb-3">
                  Send this prompt to Claude to analyze the training data and suggest improvements:
                </p>

                <div className="bg-white p-3 rounded border border-blue-300 font-mono text-xs mb-3 max-h-48 overflow-y-auto">
                  <pre className="whitespace-pre-wrap text-gray-700">{trainingBatch.claude_prompt}</pre>
                </div>

                <button
                  onClick={copyPromptToClipboard}
                  className={`w-full py-2 px-4 rounded font-semibold transition ${
                    copiedPrompt
                      ? 'bg-green-500 text-white'
                      : 'bg-blue-500 text-white hover:bg-blue-600'
                  }`}
                >
                  {copiedPrompt ? '✓ Copied!' : 'Copy Prompt'}
                </button>
              </div>

              {/* Next Steps */}
              <div className="bg-green-50 p-4 rounded border border-green-200">
                <h3 className="font-semibold text-green-700 mb-2 flex items-center gap-2">
                  <CheckCircle size={18} /> Next Step
                </h3>
                <p className="text-sm text-green-600 mb-3">
                  You now have enough training data to fine-tune the BERT model! Run this command to start training:
                </p>
                <div className="bg-white p-3 rounded border border-green-300 font-mono text-xs text-green-700">
                  python fine_tune_bert.py --training-data training_data.json --synthetic-data synthetic_data.json
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Documentation */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Documentation</h2>

        <div className="space-y-4">
          <div className="p-4 bg-gray-50 rounded border border-gray-200">
            <h3 className="font-semibold text-gray-700 mb-2">Full Training Guide</h3>
            <p className="text-sm text-gray-600 mb-3">
              See <code className="bg-white px-2 py-1 rounded border border-gray-300">BERT_TRAINING_GUIDE.md</code> for complete instructions,
              expected results, troubleshooting, and deployment steps.
            </p>
            <button className="text-blue-600 hover:text-blue-700 text-sm font-semibold">
              View Guide →
            </button>
          </div>

          <div className="p-4 bg-gray-50 rounded border border-gray-200">
            <h3 className="font-semibold text-gray-700 mb-2">Accuracy Improvements</h3>
            <div className="text-sm text-gray-600 space-y-1">
              <div>• <strong>Current (SLM):</strong> 70% accuracy</div>
              <div>• <strong>Expected (BERT):</strong> 92% accuracy</div>
              <div>• <strong>Improvement:</strong> +22% absolute increase</div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 border border-blue-200">
        <h3 className="font-bold text-gray-700 mb-3">Timeline Estimate</h3>
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-gray-600">Collect Real</div>
            <div className="font-bold text-blue-600">2-3 hrs</div>
          </div>
          <div>
            <div className="text-gray-600">Generate Synthetic</div>
            <div className="font-bold text-purple-600">30 min</div>
          </div>
          <div>
            <div className="text-gray-600">Fine-Tune BERT</div>
            <div className="font-bold text-green-600">30-120 min</div>
          </div>
          <div>
            <div className="text-gray-600">Deploy</div>
            <div className="font-bold text-orange-600">15 min</div>
          </div>
        </div>
        <div className="mt-3 text-xs text-gray-600">
          Total time investment: ~4-5 hours. Payback: Saves 1-2 hours per 100 resumes (~$5,500/month for typical recruiting team)
        </div>
      </div>
    </div>
  );
}
