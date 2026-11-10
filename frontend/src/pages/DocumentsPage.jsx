import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { UploadCloud, FileText, Trash2, RefreshCw, CheckCircle2, AlertCircle, Users, Lock, Globe, Loader2 } from 'lucide-react';

export default function DocumentsPage({ user }) {
  const [documents, setDocuments] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form state
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [visibility, setVisibility] = useState('private');
  const [teamId, setTeamId] = useState('');

  const loadData = async () => {
    setError('');
    try {
      const [docsData, teamsData] = await Promise.all([
        api.listDocuments(),
        api.listTeams(),
      ]);
      setDocuments(docsData);
      setTeams(teamsData);
    } catch (err) {
      setError(err.message || 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to upload');
      return;
    }

    if (visibility === 'team' && !teamId) {
      setError('Please select a team for team visibility');
      return;
    }

    setError('');
    setSuccess('');
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (title.trim()) formData.append('title', title.trim());
      formData.append('visibility', visibility);
      if (teamId && visibility === 'team') formData.append('team_id', teamId);

      const res = await api.uploadDocument(formData);
      setSuccess(`Document "${res.title || file.name}" uploaded and indexed successfully (${res.chunk_count} chunks).`);
      setFile(null);
      setTitle('');
      // reset file input
      const fileInput = document.getElementById('file-upload-input');
      if (fileInput) fileInput.value = '';
      await loadData();
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId, docTitle) => {
    if (!window.confirm(`Are you sure you want to delete "${docTitle}"?`)) return;
    try {
      await api.deleteDocument(docId);
      setSuccess(`Document deleted successfully.`);
      setDocuments(documents.filter((d) => d.id !== docId));
    } catch (err) {
      setError(err.message || 'Failed to delete document');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title & Info */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Documents</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage your knowledge base with strict retrieval-time visibility filters (Private, Team, Org).
          </p>
        </div>
        <button
          onClick={loadData}
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

      {/* Upload Box */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
          <UploadCloud className="h-5 w-5 text-indigo-600" />
          <span>Upload Document</span>
        </h2>

        <form onSubmit={handleUpload} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          {/* File input */}
          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
              Select File (TXT, MD, PDF)
            </label>
            <input
              id="file-upload-input"
              type="file"
              accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
              required
              onChange={(e) => setFile(e.target.files[0] || null)}
              className="w-full text-xs text-gray-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 border border-gray-300 rounded-lg cursor-pointer"
            />
          </div>

          {/* Title */}
          <div>
            <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
              Title (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. Q3 Security Plan"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Visibility */}
          <div>
            <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
              Visibility
            </label>
            <select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            >
              <option value="private">Private (Owner Only)</option>
              <option value="team">Team (Selected Team)</option>
              <option value="org">Org (All Members)</option>
            </select>
          </div>

          {/* Team Selector (only when visibility is team) */}
          {visibility === 'team' && (
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold uppercase text-gray-600 mb-1">
                Select Team
              </label>
              <select
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
              >
                <option value="">-- Choose Team --</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Submit button */}
          <div className="lg:col-span-4 flex justify-end">
            <button
              type="submit"
              disabled={uploading || !file}
              className="flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 shadow-sm"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Ingesting Chunks & Embeddings...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="h-4 w-4" />
                  <span>Upload & Ingest</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Documents List */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-base font-semibold text-gray-900">Accessible Documents</h2>
          <span className="text-xs font-medium text-gray-500">{documents.length} total</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-indigo-600 mb-2" />
            <p className="text-sm">Loading accessible documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            <FileText className="h-10 w-10 mx-auto text-gray-300 mb-2" />
            <p className="text-sm font-medium text-gray-600">No documents found</p>
            <p className="text-xs text-gray-400 mt-1">
              Upload a PDF, TXT or MD document above to begin querying.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3">Document</th>
                  <th className="px-6 py-3">Visibility</th>
                  <th className="px-6 py-3">Team</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Version</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {documents.map((doc) => {
                  const teamObj = teams.find((t) => t.id === doc.team_id);
                  return (
                    <tr key={doc.id} className="hover:bg-gray-50/70 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-gray-900">{doc.title || doc.filename}</div>
                        <div className="text-xs text-gray-400 font-mono">{doc.filename}</div>
                      </td>

                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                            doc.visibility === 'org'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : doc.visibility === 'team'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-gray-100 text-gray-700 border border-gray-200'
                          }`}
                        >
                          {doc.visibility === 'org' && <Globe className="h-3 w-3" />}
                          {doc.visibility === 'team' && <Users className="h-3 w-3" />}
                          {doc.visibility === 'private' && <Lock className="h-3 w-3" />}
                          <span className="capitalize">{doc.visibility}</span>
                        </span>
                      </td>

                      <td className="px-6 py-4 text-xs font-medium text-gray-600">
                        {teamObj ? teamObj.name : doc.team_id ? doc.team_id.slice(0, 8) : '—'}
                      </td>

                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-100">
                          {doc.status}
                        </span>
                      </td>

                      <td className="px-6 py-4 text-xs text-gray-500 font-mono">
                        v{doc.version}
                      </td>

                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleDelete(doc.id, doc.title || doc.filename)}
                          className="text-gray-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50 transition-colors"
                          title="Delete Document"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
