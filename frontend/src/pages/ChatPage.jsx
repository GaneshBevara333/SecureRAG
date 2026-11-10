import React, { useState } from 'react';
import { api } from '../api';
import { Send, ThumbsUp, ThumbsDown, Zap, Clock, FileText, CheckCircle2, AlertCircle, Bot, User, Loader2, Sparkles, SlidersHorizontal } from 'lucide-react';

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Settings
  const [mode, setMode] = useState('standard'); // 'standard' | 'agentic'
  const [retrievalMode, setRetrievalMode] = useState('hybrid+rerank'); // 'dense' | 'hybrid' | 'hybrid+rerank'
  const [feedbackComment, setFeedbackComment] = useState({});
  const [activeFeedbackId, setActiveFeedbackId] = useState(null);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputQuery.trim() || loading) return;

    const userQuestion = inputQuery.trim();
    setInputQuery('');
    setError('');

    // Append user message
    const userMsg = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      text: userQuestion,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await api.runQuery({
        question: userQuestion,
        mode,
        retrieval_mode: retrievalMode,
      });

      const assistantMsg = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        text: res.answer,
        citations: res.citations || [],
        latencyMs: res.latency_ms,
        cacheHit: res.cache_hit,
        queryLogId: res.query_log_id,
        mode,
        retrievalMode,
        feedback: null, // null | 1 | -1
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err.message || 'Query execution failed');
      const errorMsg = {
        id: `err_${Date.now()}`,
        sender: 'assistant',
        text: `Error: ${err.message || 'Failed to generate response'}`,
        citations: [],
        latencyMs: 0,
        cacheHit: false,
        isError: true,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (msgId, queryLogId, rating) => {
    if (!queryLogId) return;
    try {
      const comment = feedbackComment[msgId] || null;
      await api.submitFeedback({
        query_log_id: queryLogId,
        rating,
        comment,
      });

      setMessages((prev) =>
        prev.map((m) => (m.id === msgId ? { ...m, feedback: rating, feedbackSaved: true } : m))
      );
      setActiveFeedbackId(null);
    } catch (err) {
      alert(`Feedback submission failed: ${err.message}`);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col h-[calc(100vh-5rem)]">
      {/* Header & Controls Bar */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 mb-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <span>RAG Query Console</span>
          </h1>
          <p className="text-xs text-gray-500">
            Answers are strictly grounded in permitted chunks via retrieval-time ACLs.
          </p>
        </div>

        {/* Configuration Selectors */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Mode: Standard vs Agentic */}
          <div className="flex items-center bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setMode('standard')}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                mode === 'standard' ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Standard
            </button>
            <button
              onClick={() => setMode('agentic')}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                mode === 'agentic' ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Agentic
            </button>
          </div>

          {/* Retrieval Mode: dense, hybrid, hybrid+rerank */}
          <div className="flex items-center space-x-1.5 bg-gray-50 border border-gray-200 px-2.5 py-1 rounded-lg">
            <SlidersHorizontal className="h-3.5 w-3.5 text-gray-500" />
            <select
              value={retrievalMode}
              onChange={(e) => setRetrievalMode(e.target.value)}
              className="text-xs font-medium text-gray-700 bg-transparent focus:outline-none cursor-pointer"
            >
              <option value="hybrid+rerank">Hybrid + Cross-Encoder</option>
              <option value="hybrid">Hybrid (Dense + Sparse RRF)</option>
              <option value="dense">Dense Only (pgvector)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-400">
            <div className="h-12 w-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3">
              <Sparkles className="h-6 w-6" />
            </div>
            <h3 className="text-base font-semibold text-gray-800">Ask a question over your documents</h3>
            <p className="text-xs text-gray-500 max-w-sm mt-1">
              Documents visible to your role, teams, and org will be searched. Inaccessible content is filtered directly inside SQL.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              {/* Message Bubble */}
              <div
                className={`max-w-2xl rounded-2xl px-5 py-4 ${
                  msg.sender === 'user'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : msg.isError
                    ? 'bg-red-50 border border-red-200 text-red-900'
                    : 'bg-gray-50 border border-gray-200/80 text-gray-900'
                }`}
              >
                <div className="flex items-center space-x-2 mb-1.5">
                  {msg.sender === 'user' ? (
                    <User className="h-4 w-4 text-indigo-200" />
                  ) : (
                    <Bot className="h-4 w-4 text-indigo-600" />
                  )}
                  <span className="text-xs font-semibold opacity-75">
                    {msg.sender === 'user' ? 'You' : 'SecureRAG Assistant'}
                  </span>
                  <span className="text-[10px] opacity-50">{msg.timestamp}</span>
                </div>

                <div className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</div>

                {/* Assistant Metadata Badges */}
                {msg.sender === 'assistant' && !msg.isError && (
                  <div className="mt-4 pt-3 border-t border-gray-200 flex flex-wrap items-center gap-2">
                    {/* Latency Badge */}
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100 text-gray-700">
                      <Clock className="h-3 w-3 text-gray-500" />
                      <span>{Math.round(msg.latencyMs)} ms</span>
                    </span>

                    {/* Cache Badge */}
                    {msg.cacheHit ? (
                      <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <Zap className="h-3 w-3 fill-emerald-600 text-emerald-600" />
                        <span>Cache Hit</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
                        <span>Live Retrieval</span>
                      </span>
                    )}

                    {/* Retrieval Mode Badge */}
                    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200">
                      {msg.retrievalMode}
                    </span>

                    {/* Feedback buttons */}
                    {msg.queryLogId && (
                      <div className="ml-auto flex items-center space-x-1">
                        <button
                          onClick={() => handleFeedback(msg.id, msg.queryLogId, 1)}
                          title="Thumbs Up"
                          className={`p-1 rounded hover:bg-gray-200 transition-colors ${
                            msg.feedback === 1 ? 'text-green-600 font-bold' : 'text-gray-400'
                          }`}
                        >
                          <ThumbsUp className="h-3.5 w-3.5" />
                        </button>

                        <button
                          onClick={() => {
                            setActiveFeedbackId(activeFeedbackId === msg.id ? null : msg.id);
                            handleFeedback(msg.id, msg.queryLogId, -1);
                          }}
                          title="Thumbs Down"
                          className={`p-1 rounded hover:bg-gray-200 transition-colors ${
                            msg.feedback === -1 ? 'text-red-600 font-bold' : 'text-gray-400'
                          }`}
                        >
                          <ThumbsDown className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Feedback Comment Drawer */}
                {activeFeedbackId === msg.id && (
                  <div className="mt-3 p-3 bg-white rounded-lg border border-gray-200 space-y-2">
                    <label className="block text-xs font-semibold text-gray-700">
                      Add details about what was wrong with this answer:
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Missed confidential policy update..."
                      value={feedbackComment[msg.id] || ''}
                      onChange={(e) =>
                        setFeedbackComment({ ...feedbackComment, [msg.id]: e.target.value })
                      }
                      className="w-full text-xs px-2.5 py-1.5 border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
                    />
                    <div className="flex justify-end">
                      <button
                        onClick={() => handleFeedback(msg.id, msg.queryLogId, -1)}
                        className="px-2.5 py-1 text-xs bg-indigo-600 text-white rounded font-medium hover:bg-indigo-700"
                      >
                        Submit Feedback
                      </button>
                    </div>
                  </div>
                )}

                {/* Citations List */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200/60 space-y-1.5">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 block">
                      Citations ({msg.citations.length})
                    </span>
                    <div className="space-y-1">
                      {msg.citations.map((c, idx) => (
                        <div
                          key={c.chunk_id || idx}
                          className="flex items-center justify-between text-xs bg-white/70 border border-gray-200/50 px-2.5 py-1.5 rounded-lg"
                        >
                          <div className="flex items-center space-x-1.5 truncate">
                            <FileText className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                            <span className="font-medium text-gray-800 truncate">
                              {c.filename || `Document ${c.document_id.slice(0, 8)}`}
                            </span>
                            {c.page && (
                              <span className="text-gray-500 text-[10px]">p. {c.page}</span>
                            )}
                            <span className="text-gray-400 text-[10px]">chunk #{c.chunk_index}</span>
                          </div>
                          <span className="text-[10px] font-mono text-gray-500 ml-2">
                            score: {c.score}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex items-center space-x-2 text-gray-400 text-sm">
            <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
            <span>Retrieving permitted chunks & generating answer...</span>
          </div>
        )}
      </div>

      {/* Query Input Box */}
      <form onSubmit={handleSend} className="mt-4 flex space-x-3">
        <input
          type="text"
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          placeholder="Ask a question across permitted documents..."
          disabled={loading}
          className="flex-1 px-4 py-3 bg-white text-sm border border-gray-300 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={loading || !inputQuery.trim()}
          className="px-5 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium text-sm transition-colors disabled:opacity-50 flex items-center space-x-1.5 shadow-sm"
        >
          <Send className="h-4 w-4" />
          <span className="hidden sm:inline">Send</span>
        </button>
      </form>
    </div>
  );
}
