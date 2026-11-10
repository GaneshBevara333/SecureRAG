import React, { useState, useEffect } from 'react';
import { api } from '../api';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { BarChart3, Play, RefreshCw, AlertCircle, CheckCircle2, ChevronRight, X, Loader2 } from 'lucide-react';

export default function MetricsPage({ user }) {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form state to trigger run
  const [runLabel, setRunLabel] = useState('');
  const [retrievalMode, setRetrievalMode] = useState('hybrid+rerank');

  const isAdmin = user?.role === 'admin';

  const loadRuns = async () => {
    setError('');
    try {
      const data = await api.listEvalRuns();
      setRuns(data);
    } catch (err) {
      setError(err.message || 'Failed to load evaluation runs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  const handleRunEval = async (e) => {
    e.preventDefault();
    if (!runLabel.trim()) {
      setError('Please provide a label for this evaluation run');
      return;
    }

    setRunning(true);
    setError('');
    setSuccess('');

    try {
      const newRun = await api.runEval({
        label: runLabel.trim(),
        config: { retrieval_mode: retrievalMode },
      });
      setSuccess(`Evaluation run "${newRun.label}" completed successfully!`);
      setRunLabel('');
      await loadRuns();
    } catch (err) {
      setError(err.message || 'Evaluation run execution failed');
    } finally {
      setRunning(false);
    }
  };

  const loadRunDetail = async (runId) => {
    try {
      const detail = await api.getEvalRunDetail(runId);
      setSelectedRun(detail);
      setRunDetail(detail);
    } catch (err) {
      alert(`Failed to load run details: ${err.message}`);
    }
  };

  // Prepare chart data from runs (in chronological order)
  const chartData = [...runs].reverse().map((r) => ({
    name: r.label.length > 14 ? r.label.slice(0, 14) + '...' : r.label,
    fullLabel: r.label,
    mode: r.config?.retrieval_mode || 'standard',
    'Hit@k': Number((r.hit_at_k * 100).toFixed(1)),
    MRR: Number((r.mrr * 100).toFixed(1)),
    Faithfulness: Number((r.faithfulness * 100).toFixed(1)),
    'p50 Latency (ms)': Number(r.p50_ms.toFixed(1)),
    'p95 Latency (ms)': Number(r.p95_ms.toFixed(1)),
  }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <BarChart3 className="h-6 w-6 text-indigo-600" />
            <span>Evaluation Metrics & Quality Benchmarks</span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Compare Hit@k, Mean Reciprocal Rank (MRR), Faithfulness (LLM-as-judge), and latency across retrieval modes.
          </p>
        </div>
        <button
          onClick={loadRuns}
          disabled={loading}
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 shadow-sm"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="flex items-center space-x-2 p-4 text-sm rounded-xl bg-red-50 text-red-700 border border-red-200">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="flex items-center space-x-2 p-4 text-sm rounded-xl bg-green-50 text-green-700 border border-green-200">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* Run Eval Trigger (Admin Only) */}
      {isAdmin && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-3 flex items-center space-x-2">
            <Play className="h-4 w-4 text-indigo-600" />
            <span>Launch Evaluation Suite</span>
          </h2>
          <form onSubmit={handleRunEval} className="flex flex-col sm:flex-row gap-3 items-end">
            <div className="flex-1 w-full">
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                Run Label
              </label>
              <input
                type="text"
                placeholder="e.g. v2-hybrid-rerank"
                value={runLabel}
                onChange={(e) => setRunLabel(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="w-full sm:w-64">
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                Retrieval Mode
              </label>
              <select
                value={retrievalMode}
                onChange={(e) => setRetrievalMode(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
              >
                <option value="dense">Dense (pgvector)</option>
                <option value="hybrid">Hybrid (Dense + Sparse)</option>
                <option value="hybrid+rerank">Hybrid + Reranker (Cross-Encoder)</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={running}
              className="w-full sm:w-auto px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center space-x-2 shadow-sm"
            >
              {running ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Evaluating cases with LLM Judge...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  <span>Run Eval</span>
                </>
              )}
            </button>
          </form>
        </div>
      )}

      {/* Recharts Charts Grid */}
      {runs.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chart 1: Quality Metrics */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">
              Quality Metrics Comparison (% Score)
            </h3>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Hit@k" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="MRR" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Faithfulness" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Latency */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">
              Latency Benchmarks (p50 vs p95 in ms)
            </h3>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="p50 Latency (ms)" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="p95 Latency (ms)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Eval Runs Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-base font-semibold text-gray-900">Historical Evaluation Runs</h2>
          <span className="text-xs text-gray-500">{runs.length} runs</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-indigo-600 mb-2" />
            <p className="text-sm">Loading runs...</p>
          </div>
        ) : runs.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            <p className="text-sm font-medium text-gray-600">No evaluation runs recorded yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Trigger an eval run above to measure Hit@k, MRR, Faithfulness and Latency.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3">Label</th>
                  <th className="px-6 py-3">Mode</th>
                  <th className="px-6 py-3">Hit@k</th>
                  <th className="px-6 py-3">MRR</th>
                  <th className="px-6 py-3">Faithfulness</th>
                  <th className="px-6 py-3">p50 / p95</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 font-semibold text-gray-900">{r.label}</td>
                    <td className="px-6 py-4">
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                        {r.config?.retrieval_mode || 'standard'}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono font-medium text-indigo-700">
                      {(r.hit_at_k * 100).toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 font-mono font-medium text-blue-700">
                      {(r.mrr * 100).toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 font-mono font-medium text-emerald-700">
                      {(r.faithfulness * 100).toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 text-xs font-mono text-gray-500">
                      {r.p50_ms.toFixed(1)}ms / {r.p95_ms.toFixed(1)}ms
                    </td>
                    <td className="px-6 py-4 text-xs text-gray-400">
                      {new Date(r.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => loadRunDetail(r.id)}
                        className="inline-flex items-center space-x-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                      >
                        <span>Cases</span>
                        <ChevronRight className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Selected Run Details Modal */}
      {selectedRun && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
              <div>
                <h3 className="font-bold text-gray-900">{selectedRun.label}</h3>
                <p className="text-xs text-gray-500">
                  Mode: {selectedRun.config?.retrieval_mode} • Hit@k: {(selectedRun.hit_at_k * 100).toFixed(1)}% • Faithfulness: {(selectedRun.faithfulness * 100).toFixed(1)}%
                </p>
              </div>
              <button
                onClick={() => setSelectedRun(null)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {runDetail?.results && runDetail.results.length > 0 ? (
                runDetail.results.map((res, i) => (
                  <div key={res.id || i} className="p-4 bg-gray-50 border border-gray-200 rounded-xl space-y-2 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-gray-800">Case #{i + 1}</span>
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded font-semibold ${res.hit ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {res.hit ? `Hit (Rank ${res.rank || 1})` : 'Miss'}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-semibold">
                          Faithfulness: {(res.faithfulness * 100).toFixed(0)}%
                        </span>
                        <span className="text-gray-400 font-mono">
                          {Math.round(res.latency_ms)}ms
                        </span>
                      </div>
                    </div>
                    {res.answer && (
                      <p className="text-gray-600 bg-white p-2.5 rounded border border-gray-200/60">
                        {res.answer}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500 text-center py-8">No per-case breakdown available.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
